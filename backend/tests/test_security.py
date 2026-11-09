"""F3 access control and Gnani budget (BAAKI_PUBLIC). Offline: mocked Gnani, synthetic people only.

Without BAAKI_PUBLIC the rest of the suite is the "behaves as before" test; here public mode is switched on
per test with monkeypatch.
"""
from __future__ import annotations

import asyncio
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from app import audio, config, consent_flow, db, gnani, security
from app.main import app
from app.models import Case, Employer, Message, Worker

from .b_data import make_case, tts_ok
from .conftest import make_wav

ADMIN = "test-admin-token"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_counters():
    security.BUDGET.reset()
    security.ONBOARD_LIMIT.reset()
    consent_flow._ATTEMPTS.clear()
    yield
    security.BUDGET.reset()
    security.ONBOARD_LIMIT.reset()


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setenv("BAAKI_PUBLIC", "1")
    monkeypatch.setenv("BAAKI_ADMIN_TOKEN", ADMIN)
    monkeypatch.delenv("BAAKI_DEMO_OPEN", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY", raising=False)
    for k in ("GNANI_BUDGET_STT", "GNANI_BUDGET_TTS", "GNANI_BUDGET_VC", "GNANI_BUDGET_PER_IP", "TTS_LIVE_ROUTES"):
        monkeypatch.delenv(k, raising=False)


def _onboard(client, name="Savitri", language="te-IN") -> tuple[int, str]:
    r = client.post("/api/onboard", json={"name": name, "language": language})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["key"].startswith("bk_") and len(b["key"]) > 30
    return b["worker_id"], b["key"]


def _case_for(worker_id: int, employer="Kapoor ji") -> Case:
    with db.session() as s:
        e = Employer(name=employer, language="hi-en")
        s.add(e)
        s.commit()
        c = Case(worker_id=worker_id, employer_id=e.id, monthly_wage=4000, total_due=8000, months_unpaid=2,
                 status="confirmed")
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def _h(key: str) -> dict:
    return {"X-Baaki-Key": key}


# --------------------------------------------------------------------------- worker keys
def test_key_stored_as_hash_only(client, public):
    wid, key = _onboard(client)
    with db.session() as s:
        row = s.get(security.WorkerKey, wid)
        assert row.key_hash == security.hash_key(key) and key not in row.key_hash


def test_worker_routes_need_her_key(client, public):
    wid, key = _onboard(client)
    other_wid, other_key = _onboard(client, name="Padma")
    case = _case_for(wid)
    for path in (f"/api/workers/{wid}", f"/api/workers/{wid}/dashboard", f"/api/cases/{case.id}",
                 f"/api/cases/{case.id}/messages", f"/api/story/{case.id}", f"/api/diary?worker_id={wid}",
                 f"/api/voice-profile?worker_id={wid}", f"/api/raise/summary?worker_id={wid}"):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=_h(other_key)).status_code == 403, path
        assert client.get(path, headers=_h("bk_wrong")).status_code == 403, path
        assert client.get(path, headers=_h(key)).status_code not in (401, 403), path
    # body-carried ids: a key cannot write into another worker's data
    r = client.post("/api/diary", data={"worker_id": str(wid), "text": "worked today"}, headers=_h(other_key))
    assert r.status_code == 403
    r = client.post("/api/diary", data={"worker_id": str(wid), "text": "worked today"}, headers=_h(key))
    assert r.status_code == 200
    # mixing her worker_id with another worker's case is refused
    other_case = _case_for(other_wid, "Rao garu")
    r = client.post("/api/diary", data={"worker_id": str(wid), "case_id": str(other_case.id), "text": "x"},
                    headers=_h(key))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "mixed_workers"
    r = client.post("/api/consent/withdraw", json={"worker_id": wid})
    assert r.status_code == 401


def test_employer_cannot_read_her_case(client, public):
    wid, key = _onboard(client)
    case = _case_for(wid)
    # the employer page is public by its token ...
    assert client.get(f"/api/e/{case.employer_token}").status_code == 200
    # ... but her case, messages and legal pack are not (he has no key)
    assert client.get(f"/api/cases/{case.id}").status_code == 401
    assert client.get(f"/api/cases/{case.id}/legal-pack").status_code == 401
    assert client.post(f"/api/cases/{case.id}/confirm", json={"confirmed": True}).status_code == 401
    assert client.get(f"/api/cases/{case.id}", headers=_h(key)).status_code == 200


def test_cookie_key_only_for_reads(client, public):
    wid, key = _onboard(client)
    client.cookies.set("baaki_key", key)
    try:
        assert client.get(f"/api/workers/{wid}").status_code == 200
        r = client.post("/api/diary", data={"worker_id": str(wid), "text": "x"})
        assert r.status_code == 401  # no CSRF through the cookie
    finally:
        client.cookies.clear()


def test_demo_workers_open_only_with_demo_open(client, public, monkeypatch):
    seeded = client.post("/api/demo/reset", headers={"X-Admin-Token": ADMIN}).json()
    wid = seeded["workers"]["lakshmi"] if isinstance(seeded.get("workers"), dict) else 1
    assert client.get(f"/api/workers/{wid}/dashboard").status_code == 200
    assert client.post("/api/cases/meter", json={"text": "naaku 4000 baaki"}).status_code == 200
    monkeypatch.setenv("BAAKI_DEMO_OPEN", "0")
    assert client.get(f"/api/workers/{wid}/dashboard").status_code == 401
    assert client.post("/api/cases/meter", json={"text": "naaku 4000 baaki"}).status_code == 401
    _, key = _onboard(client)
    assert client.post("/api/cases/meter", json={"text": "naaku 4000 baaki"}, headers=_h(key)).status_code == 200


def test_unknown_route_template_fails_closed_and_every_route_is_classified(public):
    missing = []
    for path in app.openapi()["paths"]:
        if security.rule_for(path) is None and security.rule_for(path.replace("{key}", "{key:path}")) is None:
            missing.append(path)
    assert missing == [], f"classify these in security.ROUTE_RULES: {missing}"


# --------------------------------------------------------------------------- admin-only demo routes
def test_demo_routes_need_admin_token(client, public, mock_gnani):
    for path in ("/api/demo/reset", "/api/raise/demo", "/api/dues/demo"):
        assert client.post(path).status_code == 404, path
        assert client.post(path, headers={"X-Admin-Token": "nope"}).status_code == 404, path
    r = client.post("/api/demo/reset", headers={"X-Admin-Token": ADMIN})
    assert r.status_code == 200


def test_reset_wipes_keys_so_reused_ids_stay_demo(client, public):
    wid, key = _onboard(client)
    client.post("/api/demo/reset", headers={"X-Admin-Token": ADMIN})
    with db.session() as s:
        assert s.get(security.WorkerKey, wid) is None


def test_stale_key_for_reused_id_is_ignored(client, public):
    wid, _ = _onboard(client)
    with db.session() as s:  # simulate a wipe that forgot the key table: a new worker gets the old id
        w = s.get(Worker, wid)
        w.created_at = "9999-01-01T00:00:00.000000Z"
        s.add(w)
        s.commit()
        assert security.is_demo_worker(s, wid)


def test_admin_routes_open_on_localhost(client):
    assert client.post("/api/demo/reset").status_code == 200


def test_raw_tts_stt_off_in_public(client, public, short_ogg):
    assert client.post("/api/tts", json={"text": "namaste", "lang": "hi-en"}).status_code == 404
    assert client.post("/api/stt", files={"audio": ("x.ogg", short_ogg, "audio/ogg")}).status_code == 404


# --------------------------------------------------------------------------- media
def test_media_rule(client, public):
    from app import storage

    wid, key = _onboard(client)
    case = _case_for(wid)
    st = storage.get_storage()
    private = st.put(f"c{case.id}/reply_abc.ogg", b"OggS-private")
    sent = st.put(f"c{case.id}/note_def.ogg", b"OggS-sent")
    with db.session() as s:
        s.add(Message(case_id=case.id, direction="to_employer", status="sent", audio_path=sent, text="x"))
        s.add(Message(case_id=case.id, direction="to_employer", status="draft",
                      audio_path=st.put(f"c{case.id}/draft_x.ogg", b"OggS-draft"), text="y"))
        s.commit()
    assert client.get(f"/api/media/{private}").status_code == 404
    assert client.get(f"/api/media/{private}", headers=_h(key)).status_code == 200
    assert client.get(f"/api/media/{sent}").status_code == 200          # the employer plays what was sent
    assert client.get(f"/api/media/c{case.id}/draft_x.ogg").status_code == 404   # never an unsent draft
    client.cookies.set("baaki_key", key)
    try:
        assert client.get(f"/api/media/{private}").status_code == 200   # <audio src> with the cookie
    finally:
        client.cookies.clear()
    # synthetic demo worker media stays viewable
    ids = make_case()
    demo_key = st.put(f"c{ids['case_id']}/demo.ogg", b"OggS-demo")
    assert client.get(f"/api/media/{demo_key}").status_code == 200


# --------------------------------------------------------------------------- Gnani budget
def test_budget_exhausted_gives_text_fallback(client, public, mock_gnani, short_ogg, monkeypatch):
    monkeypatch.setenv("GNANI_BUDGET_TTS", "0")
    mock_gnani.default[gnani.TTS_PATH] = tts_ok(short_ogg)
    ids = make_case()  # synthetic demo worker: open, but still within the budget
    r = client.post(f"/api/cases/{ids['case_id']}/readback", json={"audio": True})
    assert r.status_code == 200
    b = r.json()
    assert b["audio_url"] is None and b["text"]
    assert b["tts_error"]["status"] == 429 and b["tts_error"]["code"] == "budget"
    assert mock_gnani.requests == []


def test_per_ip_budget(client, public, mock_gnani, short_ogg, monkeypatch):
    monkeypatch.setenv("GNANI_BUDGET_PER_IP", "1")
    mock_gnani.default[gnani.TTS_PATH] = tts_ok(short_ogg)
    ids = make_case()
    r1 = client.post(f"/api/cases/{ids['case_id']}/readback", json={"audio": True}).json()
    assert r1["tts_error"] is None and r1["audio_url"]
    r2 = client.post(f"/api/cases/{ids['case_id']}/readback", json={"audio": True, "lang": "hi-en"}).json()
    assert r2["tts_error"]["code"] == "budget"
    assert len(mock_gnani.requests) == 1


def test_tts_cache_only_outside_allowlist(client, public, mock_gnani, short_ogg):
    mock_gnani.default[gnani.TTS_PATH] = tts_ok(short_ogg)
    r = client.post("/api/exit/checklist", json={"lang": "te-IN"})
    assert r.status_code == 200 and r.json()["fallback"] == "text"
    assert mock_gnani.requests == []


def test_budget_unlimited_on_localhost(client, mock_gnani, short_ogg, monkeypatch):
    monkeypatch.setenv("GNANI_BUDGET_TTS", "0")  # ignored without BAAKI_PUBLIC
    mock_gnani.default[gnani.TTS_PATH] = tts_ok(short_ogg)
    ids = make_case()
    r = client.post(f"/api/cases/{ids['case_id']}/readback", json={"audio": True}).json()
    assert r["tts_error"] is None and r["audio_url"]


# --------------------------------------------------------------------------- STT duration cap
@pytest.fixture(scope="module")
def hour_ogg(tmp_path_factory) -> bytes:
    out = tmp_path_factory.mktemp("long") / "hour.ogg"
    subprocess.run([audio.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=8000:cl=mono", "-t", "3600", "-c:a", "libopus", "-b:a", "6k", str(out)],
                   check=True, timeout=120)
    return out.read_bytes()


def test_hour_long_upload_is_413_before_any_gnani_call(client, mock_gnani, hour_ogg):
    """Applies always, also on localhost."""
    r = client.post("/api/cases/listen", files={"audio": ("long.ogg", hour_ogg, "audio/ogg")},
                    data={"lang": "te", "use_llm": "false"})
    assert r.status_code == 413
    d = r.json()["detail"]
    assert d["error"] == "audio_too_long" and d["max_s"] == config.stt_max_seconds() and d["duration_s"] > 3000
    assert mock_gnani.requests == []


def test_hour_long_upload_public_too(client, public, mock_gnani, hour_ogg):
    ids = make_case()
    r = client.post(f"/api/inbox/{ids['case_id']}", files={"audio": ("long.ogg", hour_ogg, "audio/ogg")},
                    data={"use_llm": "false", "speak": "false"})
    assert r.status_code == 413 and mock_gnani.requests == []


# --------------------------------------------------------------------------- Gnani client chokepoint
def _run(coro):
    return asyncio.run(coro)


def test_402_opens_breaker(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(402, json={"detail": {"error_code": "INSUFFICIENT_CREDITS", "message": "top up"}})

    c = gnani.GnaniClient(api_key="k", base_url="https://mock.gnani.local", transport=httpx.MockTransport(handler),
                          backoff_s=0.0)
    with pytest.raises(gnani.GnaniError) as e1:
        _run(c.tts("namaste", "hi-en"))
    assert e1.value.status == 402 and c.breaker_state()["open"]
    with pytest.raises(gnani.GnaniError) as e2:
        _run(c.tts("namaste", "hi-en"))
    assert e2.value.code == "voice_unavailable" and len(seen) == 1  # failed fast, no second request


def test_read_timeout_is_not_retried_connect_error_is():
    seen = []

    def slow(request):
        seen.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    c = gnani.GnaniClient(api_key="k", base_url="https://mock.gnani.local", transport=httpx.MockTransport(slow),
                          backoff_s=0.0)
    with pytest.raises(gnani.GnaniError) as e:
        _run(c.tts("namaste", "hi-en"))
    assert e.value.code == "TIMEOUT" and len(seen) == 1

    calls = []

    def flaky(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, content=b"OggS", headers={"content-type": "audio/ogg"})

    c2 = gnani.GnaniClient(api_key="k", base_url="https://mock.gnani.local", transport=httpx.MockTransport(flaky),
                           backoff_s=0.0)
    assert _run(c2.tts("namaste", "hi-en")) == b"OggS" and len(calls) == 2


def test_500_is_not_retried():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(500, json={"detail": {"error_code": "X", "message": "down"}})

    c = gnani.GnaniClient(api_key="k", base_url="https://mock.gnani.local", transport=httpx.MockTransport(handler),
                          backoff_s=0.0)
    with pytest.raises(gnani.GnaniError):
        _run(c.tts("namaste", "hi-en"))
    assert len(seen) == 1


def test_deadline_includes_lock_wait():
    async def scenario():
        c = gnani.GnaniClient(api_key="k", base_url="https://mock.gnani.local", deadline_s=0.2,
                              transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x",
                                                                                     headers={"content-type": "audio/ogg"})))
        lock = gnani._lock()
        await lock.acquire()  # someone else holds the 1-request lock
        try:
            with pytest.raises(gnani.GnaniError) as e:
                await c.tts("namaste", "hi-en")
            return e.value
        finally:
            lock.release()

    err = _run(scenario())
    assert err.code == "BUSY" and err.status == 503


# --------------------------------------------------------------------------- voice clone consent
def test_cloning_disabled_in_public(client, public, mock_gnani):
    ids = make_case()
    clip = make_wav([("tone", 12.0)])
    r = client.post("/api/consent/attempt", data={"worker_id": str(ids["worker_id"]), "method": "spoken"},
                    files={"audio": ("c.wav", clip, "audio/wav")})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "cloning_disabled"
    r = client.post("/api/voice-profile", data={"worker_id": str(ids["worker_id"]), "consent": "true"},
                    files={"audio": ("c.wav", clip, "audio/wav")})
    assert r.status_code == 403
    assert mock_gnani.requests == []


def test_tap_needs_a_spoken_attempt_first(client, mock_gnani):
    ids = make_case()
    clip = make_wav([("tone", 12.0)])
    r = client.post("/api/consent/attempt", data={"worker_id": str(ids["worker_id"]), "method": "tap"},
                    files={"audio": ("c.wav", clip, "audio/wav")})
    assert r.status_code == 200 and r.json()["status"] == "spoken_first"
    assert mock_gnani.requests == []


# --------------------------------------------------------------------------- names, IP, headers, health
def test_employer_names_are_cleaned_before_they_are_spoken():
    assert security.clean_name("Sharma ji") == "Sharma ji"
    assert security.clean_name("శర్మ గారు") == "శర్మ గారు"
    assert security.clean_name("मेहता मैडम") == "मेहता मैडम"
    dirty = "Sharma ji call 9876543210 visit https://evil.example/pay or win.cash.xyz now"
    cleaned = security.clean_name(dirty)
    assert "http" not in cleaned and "9876" not in cleaned and ".xyz" not in cleaned
    assert cleaned.startswith("Sharma ji") and len(cleaned) <= security.MAX_NAME_CHARS
    with db.session() as s:
        e = Employer(name="Reddy garu +91 90000 12345 lakshmi.demo@upi", language="te-IN")
        s.add(e)
        s.commit()
        s.refresh(e)
        assert e.name == "Reddy garu"


def test_client_ip_rules(monkeypatch):
    hdr = {"x-forwarded-for": "6.6.6.6, 203.0.113.9", "cf-connecting-ip": ""}
    monkeypatch.delenv("BAAKI_PUBLIC", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY", raising=False)
    assert security.client_ip_from(hdr, "10.0.0.1") == "6.6.6.6"          # localhost: as before
    monkeypatch.setenv("BAAKI_PUBLIC", "1")
    assert security.client_ip_from(hdr, "10.0.0.1") == "10.0.0.1"         # public, no trusted proxy
    monkeypatch.setenv("TRUSTED_PROXY", "1")
    assert security.client_ip_from(hdr, "10.0.0.1") == "203.0.113.9"      # the hop the proxy added
    assert security.client_ip_from({"cf-connecting-ip": "198.51.100.4"}, "10.0.0.1") == "198.51.100.4"


def test_public_base_url_from_trusted_proxy(monkeypatch):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def probe(_request):
        return JSONResponse({"base": config.public_base_url(), "ip": security.current_ip()})

    mini = TestClient(security.RequestContextMiddleware(Starlette(routes=[Route("/p", probe)])))
    hdr = {"x-forwarded-host": "baaki.example.org", "x-forwarded-proto": "https",
           "x-forwarded-for": "203.0.113.9"}
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://fallback.local")
    monkeypatch.delenv("TRUSTED_PROXY", raising=False)
    assert mini.get("/p", headers=hdr).json()["base"] == "http://fallback.local"
    monkeypatch.setenv("TRUSTED_PROXY", "1")
    out = mini.get("/p", headers=hdr).json()
    assert out == {"base": "https://baaki.example.org", "ip": "203.0.113.9"}
    assert mini.get("/p", headers={"x-forwarded-host": "evil.com/x?"}).json()["base"] == "http://fallback.local"


def test_security_headers_and_request_id(client):
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer" and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-request-id"]
    ready = r.json()["readiness"]
    assert ready["db"] is True and "gnani_breaker" in ready and "gnani_budget" in ready
    assert "key" not in str(ready).lower().replace("breaker", "")


def test_onboard_works_on_localhost_and_is_rate_limited_in_public(client, public, monkeypatch):
    monkeypatch.setenv("ONBOARD_PER_IP_DAY", "2")
    _onboard(client)
    _onboard(client, name="Rani")
    assert client.post("/api/onboard", json={"name": "Third", "language": "hi-en"}).status_code == 429
    assert client.post("/api/onboard", json={"name": "1234", "language": "te-IN"}).status_code in (400, 429)


# --------------------------------------------------------------------------- seed on boot, dues ownership
def test_public_boot_seeds_a_fresh_database(public, monkeypatch):
    """One switch (BAAKI_SEED_ON_BOOT): unset, it is on in public mode; main.py's lifespan awaits the seed."""
    monkeypatch.delenv("BAAKI_SEED_ON_BOOT", raising=False)
    monkeypatch.delenv("SEED_ON_BOOT", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert config.seed_on_boot() is True
    with TestClient(app) as c:
        with db.session() as s:
            assert s.exec(__import__("sqlmodel").select(Worker)).first() is not None
        assert c.get("/api/health").json()["readiness"]["seeded"] is True


def test_localhost_boot_does_not_seed_unless_asked(monkeypatch):
    monkeypatch.delenv("BAAKI_PUBLIC", raising=False)
    monkeypatch.delenv("BAAKI_SEED_ON_BOOT", raising=False)
    monkeypatch.delenv("SEED_ON_BOOT", raising=False)
    assert config.seed_on_boot() is False
    monkeypatch.setenv("SEED_ON_BOOT", "1")  # legacy alias
    assert config.seed_on_boot() is True
    monkeypatch.setenv("BAAKI_SEED_ON_BOOT", "0")
    assert config.seed_on_boot() is False


def test_dues_accounts_follow_their_owner(client, public):
    wid, key = _onboard(client)
    _, other_key = _onboard(client, name="Padma")
    r = client.post("/api/dues", json={"worker_id": wid, "kind": "vendor", "party_name": "Ramu",
                                       "owner_name": "Savitri", "items": []}, headers=_h(key))
    assert r.status_code in (200, 201), r.text
    aid = r.json().get("account_id") or r.json().get("id") or r.json()["account"]["id"]
    assert client.get(f"/api/dues/{aid}").status_code == 401
    assert client.get(f"/api/dues/{aid}", headers=_h(other_key)).status_code == 403
    assert client.get(f"/api/dues/{aid}", headers=_h(key)).status_code == 200
