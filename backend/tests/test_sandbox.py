"""V04 Be Sharma ji sandbox: cached audio only (0 Gnani calls), guards, and the real story stays untouched."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import func, select

from app import config, db, gnani, sandbox_core as core, tts_cache
from app.main import app
from app.models import Case, Employer, Worker
from app.sandbox_models import SandboxSession

REAL_MANIFEST = Path(__file__).resolve().parents[1] / "seed_cache" / "demo_manifest.json"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_limits():
    core.reset_limits()
    yield
    core.reset_limits()


@pytest.fixture
def cached_clips(short_ogg):
    """Put the committed manifest's clips (polite note + paid alert) into this test's seed cache, using the
    manifest's own keys, so the test also proves the sandbox's sentences hit the committed cache."""
    d = config.SEED_CACHE_DIR / "tts"
    d.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    (config.SEED_CACHE_DIR / "demo_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False),
                                                             encoding="utf-8")
    for clip in manifest["clips"]:
        if clip["purpose"].startswith(("polite", "paid alert")):
            (d / f"{clip['key']}.ogg").write_bytes(short_ogg)
    return manifest


def _stats():
    return dataclasses.asdict(gnani.STATS), tts_cache.SYNTH_CALLS["count"]


def _no_secrets(body: dict, token: str) -> None:
    raw = json.dumps(body, ensure_ascii=False)
    assert token not in raw and "employer_token" not in raw
    assert "upi://" not in raw and "@upi" not in raw and "/e/" not in raw


def _token_of(sid: str) -> str:
    with db.session() as s:
        return s.get(SandboxSession, sid).case_token


def test_full_flow_reuses_cached_audio_with_zero_gnani(client, mock_gnani, cached_clips):
    before = _stats()
    r = client.post("/api/sandbox")
    assert r.status_code == 201, r.text
    b = r.json()
    sid = b["sandbox_id"]
    assert b["banner"] == "Synthetic demo. Lakshmi is fictional." and b["synthetic"]
    assert b["total_due"] == 12692 and b["balance_display"] == "₹12,692"
    assert b["employer"]["name"] == "Sharma ji" and b["worker"]["name"] == "Lakshmi"
    assert any("अगस्त" in i["label"] for i in b["items"])
    assert b["upi"] == {"enabled": False, "label": "Demo: UPI is switched off"}
    assert b["reply"]["enabled"] is False
    assert b["voice_note"]["available"] and b["voice_note"]["audio_url"] == f"/api/sandbox/{sid}/audio/note"
    assert b["message"]["text"].startswith("यह एक AI वॉइस संदेश है")
    _no_secrets(b, _token_of(sid))

    a = client.get(f"/api/sandbox/{sid}/audio/note")
    assert a.status_code == 200 and a.headers["content-type"].startswith("audio/ogg") and a.content[:4] == b"OggS"

    w = client.get(f"/api/sandbox/{sid}/worker").json()
    assert not w["paid"] and w["alert"] is None and not w["played"]
    assert client.post(f"/api/sandbox/{sid}/played").json()["played"] is True
    assert client.get(f"/api/sandbox/{sid}/worker").json()["played"] is True

    p = client.post(f"/api/sandbox/{sid}/paid")
    assert p.status_code == 200, p.text
    pb = p.json()
    assert pb["fully_paid"] and pb["balance"] == 0 and pb["paid"] == 12692 and pb["status"] == "paid"
    assert pb["badge"]["title"] == "Fair Employer"
    assert pb["alert"]["headline"] == "Paisa aa gaya!" and "₹12,692" in pb["alert"]["text"]
    assert pb["alert"]["audio_url"] == f"/api/sandbox/{sid}/audio/paid"
    _no_secrets(pb, _token_of(sid))
    assert client.get(f"/api/sandbox/{sid}/audio/paid").content[:4] == b"OggS"

    w = client.get(f"/api/sandbox/{sid}/worker").json()
    assert w["paid"] and w["balance"] == 0 and w["alert"]["audio_url"]
    again = client.post(f"/api/sandbox/{sid}/paid").json()  # idempotent
    assert again["already_paid"] and again["balance"] == 0

    assert mock_gnani.requests == []
    assert _stats() == before


def test_no_cached_audio_degrades_without_calling_gnani(client, mock_gnani):
    before = _stats()
    b = client.post("/api/sandbox").json()
    sid = b["sandbox_id"]
    assert b["voice_note"] == {"available": False, "audio_url": None, "label": "Voice note unavailable",
                               "reason": "No cached audio for this note on this server. The text is below."}
    assert b["message"]["text"]
    assert client.get(f"/api/sandbox/{sid}/audio/note").status_code == 404
    pb = client.post(f"/api/sandbox/{sid}/paid").json()
    assert pb["fully_paid"] and pb["alert"]["audio_url"] is None and pb["alert"]["headline"] == "Paisa aa gaya!"
    assert client.get(f"/api/sandbox/{sid}/audio/paid").status_code == 404
    assert mock_gnani.requests == [] and _stats() == before


def test_real_demo_story_is_untouched(client, mock_gnani, cached_clips):
    ids = client.post("/api/demo/reset").json()
    lakshmi = ids["workers"]["lakshmi"]
    dash_before = client.get(f"/api/workers/{lakshmi}/dashboard").json()
    sid = client.post("/api/sandbox").json()["sandbox_id"]
    client.post(f"/api/sandbox/{sid}/played")
    client.post(f"/api/sandbox/{sid}/paid")
    dash_after = client.get(f"/api/workers/{lakshmi}/dashboard").json()
    assert dash_after["totals"] == dash_before["totals"] and len(dash_after["cards"]) == 3
    real = client.get(f"/api/e/{ids['employer_tokens']['sharma']}").json()
    assert real["balance"] == 12692 and real["status"] == "confirmed" and real["badge"] is None
    with db.session() as s:
        row = s.get(SandboxSession, sid)
        assert row.worker_id not in ids["workers"].values() and row.employer_id not in ids["employers"].values()
        assert s.get(Worker, row.worker_id).upi_vpa is None


def test_empty_database_bootstraps_the_story_first(client, mock_gnani):
    sid = client.post("/api/sandbox").json()["sandbox_id"]
    with db.session() as s:
        assert s.get(Worker, 1).name == "Lakshmi" and s.get(Worker, 1).upi_vpa == "lakshmi.demo@upi"
        assert s.get(SandboxSession, sid).worker_id > 2
    assert len(client.get("/api/workers/1/dashboard").json()["cards"]) == 3


def test_rate_limit_per_ip(client, mock_gnani):
    for _ in range(core.RATE_MAX):
        assert client.post("/api/sandbox", headers={"x-forwarded-for": "203.0.113.7"}).status_code == 201
    r = client.post("/api/sandbox", headers={"x-forwarded-for": "203.0.113.7"})
    assert r.status_code == 429 and r.json()["error"] == "rate_limited" and int(r.headers["Retry-After"]) > 0
    assert client.post("/api/sandbox", headers={"x-forwarded-for": "198.51.100.9"}).status_code == 201


def test_expiry_and_cleanup(client, mock_gnani, monkeypatch):
    sid = client.post("/api/sandbox").json()["sandbox_id"]
    with db.session() as s:
        row = s.get(SandboxSession, sid)
        old_token = row.case_token
        n_workers = s.exec(select(func.count()).select_from(Worker)).one()
    t0 = core._now()
    monkeypatch.setattr(core, "_now", lambda: t0 + core.TTL_S + 5)
    assert client.get(f"/api/sandbox/{sid}").status_code == 410
    assert client.post(f"/api/sandbox/{sid}/paid").json()["error"] == "expired"
    client.post("/api/sandbox")  # creation runs the cleanup
    with db.session() as s:
        assert s.get(SandboxSession, sid) is None
        assert s.exec(select(Case).where(Case.employer_token == old_token)).first() is None
        assert s.exec(select(func.count()).select_from(Worker)).one() == n_workers  # one gone, one new
    assert client.get(f"/api/sandbox/{sid}").status_code == 404


def test_cap_evicts_the_oldest(client, mock_gnani, monkeypatch):
    monkeypatch.setattr(core, "MAX_SANDBOXES", 2)
    sids = [client.post("/api/sandbox", headers={"x-forwarded-for": f"192.0.2.{i}"}).json()["sandbox_id"]
            for i in range(3)]
    assert client.get(f"/api/sandbox/{sids[0]}").status_code == 404
    assert all(client.get(f"/api/sandbox/{x}").status_code == 200 for x in sids[1:])
    assert client.get("/api/sandbox").json()["active"] == 2


def test_cleanup_after_demo_reset_never_deletes_recycled_ids(client, mock_gnani, monkeypatch):
    client.post("/api/demo/reset")
    old = client.post("/api/sandbox").json()["sandbox_id"]
    client.post("/api/demo/reset")  # wipes the core tables; the sandbox row survives with stale ids
    assert client.get(f"/api/sandbox/{old}").status_code == 410
    new = client.post("/api/sandbox").json()["sandbox_id"]  # very likely reuses the same case id
    with db.session() as s:
        row_old = s.get(SandboxSession, old)
        row_old.expires_ts = 0
        s.add(row_old)
        s.commit()
    client.get("/api/sandbox")
    client.post("/api/sandbox", headers={"x-forwarded-for": "192.0.2.77"})  # cleanup runs here
    assert client.get(f"/api/sandbox/{new}").status_code == 200
    with db.session() as s:
        assert s.get(SandboxSession, old) is None
        assert s.exec(select(func.count()).select_from(Employer).where(Employer.name == "Reddy garu")).one() == 1


def test_reply_is_disabled_and_unknown_ids_404(client, mock_gnani):
    sid = client.post("/api/sandbox").json()["sandbox_id"]
    r = client.post(f"/api/sandbox/{sid}/reply")
    assert r.status_code == 403 and r.json()["error"] == "reply_disabled"
    for path in ("", "/worker", "/audio/note"):
        assert client.get(f"/api/sandbox/nope{path}").status_code == 404
    assert client.post("/api/sandbox/nope/paid").status_code == 404
    assert mock_gnani.requests == []
