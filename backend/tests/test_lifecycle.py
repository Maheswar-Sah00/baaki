"""Data lifecycle and user flows (GAP_AUDIT R5): reset registry, seed on boot, drafts and re-telling, onboarding
error code, home match across scripts, reminders, dues scoping, inbox duplicate scope, session use under load,
seed consistency and the clock. Offline: no Gnani, no LLM."""
from __future__ import annotations

import asyncio
import datetime as dt
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, Float, Integer, func, select as sa_select
from sqlmodel import select

from app import clock, db, seed
from app.main import app
from app.models import Case, Employer, Message, Payment, Worker


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("BAAKI_SEED_ON_BOOT", "0")  # these tests seed explicitly
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo(client):
    r = client.post("/api/demo/reset")
    assert r.status_code == 200, r.text
    return r.json()


def _counts() -> dict[str, int]:
    with db.session() as s:
        return {t.name: s.execute(sa_select(func.count()).select_from(t)).scalar_one() for t in db.all_tables()}


def _fill_row(s, t, n: int) -> None:
    """One synthetic row in any table: every NOT NULL column without a default gets a placeholder."""
    vals = {}
    for c in t.columns:
        auto_pk = c.primary_key and isinstance(c.type, Integer) and len(t.primary_key.columns) == 1
        if auto_pk:
            continue
        if c.nullable and not c.primary_key:
            continue
        if c.default is not None or c.server_default is not None:
            continue
        if isinstance(c.type, Boolean):
            vals[c.name] = False
        elif isinstance(c.type, Integer):
            vals[c.name] = 9000 + n
        elif isinstance(c.type, Float):
            vals[c.name] = 1.0
        else:
            vals[c.name] = f"fill-{t.name}-{n}"
    s.execute(t.insert().values(**vals))


# --------------------------------------------------------------------------- 1. reset registry
def test_registry_has_every_feature_table():
    names = {t.name for t in db.all_tables()}
    for expected in ("worker", "employer", "case", "caseitem", "message", "payment", "diaryentry", "voiceprofile",
                     "inboxcard", "inboxpromise", "duesaccount", "duesitem", "duespromise", "dueslog", "duesowner",
                     "raiseask", "raiseevent", "hisaabproposal", "exit_kit", "sandbox_session"):
        assert expected in names, expected


def test_reset_wipes_every_table_and_ids_restart(client, demo):
    baseline = _counts()
    with db.session() as s:
        for i, t in enumerate(db.all_tables()):
            _fill_row(s, t, i)
            _fill_row(s, t, i + 500)
        s.commit()
    filled = _counts()
    assert all(filled[n] >= baseline[n] + 2 for n in filled)
    again = client.post("/api/demo/reset").json()
    assert _counts() == baseline  # every feature row is gone; only the seed's own rows are back
    assert again["cases"] == demo["cases"] and again["workers"] == demo["workers"]
    # a new inbox reply after a reset is card 1 of the new case 1, and the same text can be filmed again
    cid = again["cases"]["sharma"]
    r = client.post(f"/api/inbox/{cid}", data={"text": "agle hafte de denge", "speak": "false", "use_llm": "false"})
    assert r.status_code == 200, r.text
    assert r.json()["duplicate"] is False and r.json()["id"] == 1


def test_reset_clears_sqlite_sequence(tmp_path):
    eng = db._make_engine(f"sqlite:///{(tmp_path / 'seq.db').as_posix()}")
    db.set_engine(eng)
    db.init_db(eng)
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE IF NOT EXISTS t_auto (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
        c.exec_driver_sql("INSERT INTO t_auto (v) VALUES ('a')")
    with db.session() as s:
        db.wipe_all(s)
        s.commit()
    with eng.begin() as c:
        assert c.exec_driver_sql("SELECT count(*) FROM sqlite_sequence").scalar_one() == 0


# --------------------------------------------------------------------------- 2. seed on boot
def test_ensure_seeded_only_on_an_empty_database(monkeypatch):
    from app.raise_models import RaiseAsk
    from app.dues_models import DuesOwner

    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("BAAKI_SEED_ON_BOOT", "1")
    out = seed.ensure_seeded()
    assert out is not None and out["workers"]["lakshmi"] == 1
    with db.session() as s:
        assert s.exec(select(func.count()).select_from(Worker)).one() == 2
        assert s.exec(select(func.count()).select_from(RaiseAsk)).one() == 1
        owners = {o.worker_id for o in s.exec(select(DuesOwner))}
        assert owners == {out["workers"]["lakshmi"]}
    assert seed.ensure_seeded() is None  # never touches a database with workers


def test_ensure_seeded_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("BAAKI_SEED_ON_BOOT", "0")
    assert seed.ensure_seeded() is None
    assert not seed.has_workers()


# --------------------------------------------------------------------------- 3. drafts and duplicates
def _new_home_draft(client, demo, name="Gupta ji"):
    body = {"worker_id": demo["workers"]["lakshmi"], "use_llm": False, "lang": "hinglish",
            "transcript": f"{name} ne do mahine ki salary nahi di, teen hazaar mahina",
            "employer": {"name": name, "language": "hi-en"}}
    r = client.post("/api/cases", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_drafts_never_count_and_can_be_deleted(client, demo):
    lid = demo["workers"]["lakshmi"]
    before = client.get(f"/api/workers/{lid}/dashboard").json()
    d = _new_home_draft(client, demo)
    assert d["status"] == "draft" and d["updated"] is False and d["total_due"] == 6000
    dash = client.get(f"/api/workers/{lid}/dashboard").json()
    assert dash["totals"] == before["totals"] and len(dash["cards"]) == len(before["cards"])
    assert [x["case_id"] for x in dash["drafts"]] == [d["id"]]
    r = client.delete(f"/api/cases/{d['id']}")
    assert r.status_code == 200 and r.json()["employer_removed"] is True
    assert client.get(f"/api/cases/{d['id']}").status_code == 404
    assert client.get(f"/api/workers/{lid}/dashboard").json()["drafts"] == []
    conf = client.delete(f"/api/cases/{demo['cases']['sharma']}")
    assert conf.status_code == 409 and conf.json()["detail"]["error"] == "not_draft"


def test_filming_story_ends_with_one_sharma_card(client, demo):
    """She tells the Sharma ji story again (picks the home, or types the Telugu name): ONE case is updated."""
    lid, sharma = demo["workers"]["lakshmi"], demo["employers"]["sharma"]
    cid = demo["cases"]["sharma"]
    told = "శర్మ గారు నాలుగు నెలలుగా జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు."
    r = client.post("/api/cases", json={"worker_id": lid, "employer_id": sharma, "transcript": told, "lang": "te",
                                        "use_llm": False}).json()
    assert r["id"] == cid and r["updated"] is True and r["previous_total"] == demo["totals"]["sharma"]
    assert r["readback_confirmed"] is False and r["status"] == "confirmed"
    # a "new home" typed in Telugu script is the same home, not a second Sharma ji
    r2 = client.post("/api/cases", json={"worker_id": lid, "transcript": told, "lang": "te", "use_llm": False,
                                         "employer": {"name": "శర్మ గారు", "language": "hi-en"}}).json()
    assert r2["id"] == cid and r2["updated"] is True and r2["home_match"] == "script_table"
    c = client.post(f"/api/cases/{cid}/confirm", json={"confirmed": True}).json()
    assert c["readback_confirmed"] is True
    dash = client.get(f"/api/workers/{lid}/dashboard").json()
    sharma_cards = [x for x in dash["cards"] if x["employer"]["name"] == "Sharma ji"]
    assert len(sharma_cards) == 1 and sharma_cards[0]["total_due"] == c["total_due"]
    with db.session() as s:
        assert s.exec(select(func.count()).select_from(Employer).where(Employer.name == "Sharma ji")).one() == 1
        assert s.exec(select(func.count()).select_from(Employer).where(Employer.name == "శర్మ గారు")).one() == 0


def test_nahi_undoes_a_retelling(client, demo):
    lid, sharma, cid = demo["workers"]["lakshmi"], demo["employers"]["sharma"], demo["cases"]["sharma"]
    for months in ("do", "paanch"):  # told twice before confirming: undo still returns to the confirmed case
        client.post("/api/cases", json={"worker_id": lid, "employer_id": sharma, "use_llm": False, "lang": "hinglish",
                                        "transcript": f"{months} mahine ki salary nahi di, chaar hazaar mahina"})
    r = client.post(f"/api/cases/{cid}/undo-retell")
    assert r.status_code == 200, r.text
    back = r.json()
    assert back["total_due"] == demo["totals"]["sharma"] and back["readback_confirmed"] is True
    assert client.post(f"/api/cases/{cid}/undo-retell").status_code == 409


def test_paid_home_starts_a_new_case(client, demo):
    lid, reddy = demo["workers"]["lakshmi"], demo["employers"]["reddy"]
    r = client.post("/api/cases", json={"worker_id": lid, "employer_id": reddy, "use_llm": False, "lang": "hinglish",
                                        "transcript": "November ki salary nahi di, paanch hazaar mahina"}).json()
    assert r["updated"] is False and r["id"] != demo["cases"]["reddy"]


# --------------------------------------------------------------------------- 4. onboarding error code
def test_empty_database_says_no_worker(client):
    r = client.get("/api/workers/1/dashboard")
    assert r.status_code == 404 and r.json()["detail"]["error"] == "no_worker"
    assert client.get("/api/workers/1").json()["detail"]["error"] == "no_worker"
    assert client.post("/api/cases", json={"worker_id": 1, "facts": {"monthly_wage": 4000}}).json()[
        "detail"]["error"] == "no_worker"


# --------------------------------------------------------------------------- 5. home match (LLM off)
@pytest.mark.parametrize("spoken,expected", [
    ("శర్మ గారు", "Sharma ji"), ("शर्मा जी", "Sharma ji"), ("sharma garu", "Sharma ji"), ("శర్మగారు", "Sharma ji"),
    ("రెడ్డి గారు", "Reddy garu"), ("मेहता मैडम", "Mehta madam"), ("Gupta ji", None), ("అమ్మగారు", None),
])
def test_match_home_across_scripts(client, demo, spoken, expected):
    r = client.get(f"/api/workers/{demo['workers']['lakshmi']}/match-home", params={"name": spoken}).json()
    assert (r["match"]["name"] if r["match"] else None) == expected
    if expected == "Sharma ji":
        assert r["open_case_id"] == demo["cases"]["sharma"]


def test_match_home_unit():
    from types import SimpleNamespace as N

    from app.home_match import match_home, skeleton

    homes = [N(id=1, name="Verma ji"), N(id=2, name="Rao garu")]
    assert match_home("వర్మ గారు", homes)[0].id == 1          # not in the demo table: consonant skeleton
    assert match_home("राव गारु", homes)[0].id == 2
    assert skeleton("Sharma ji") == skeleton("శర్మ గారు") == skeleton("शर्मा जी") == "srm"


# --------------------------------------------------------------------------- 6. reminders
def _plan(cid: int, first_due: dt.date, n: int = 2) -> None:
    from app import ledger

    with db.session() as s:
        case = s.get(Case, cid)
        ledger.create_plan(s, case, instalments=n, first_due=first_due, every_days=30,
                           worker=s.get(Worker, case.worker_id), employer=s.get(Employer, case.employer_id))
        s.commit()


def test_instalment_reminders_come_due_and_stop_when_shared(client, demo):
    cid = demo["cases"]["sharma"]
    first = clock.today() + dt.timedelta(days=7)
    _plan(cid, first)
    assert client.get(f"/api/cases/{cid}/reminders").json()["reminders"] == []  # nothing due yet
    r = client.get(f"/api/cases/{cid}/reminders", params={"as_of": (first + dt.timedelta(days=31)).isoformat()}).json()
    inst = [c for c in r["reminders"] if c["kind"] == "instalment"]
    assert len(inst) == 2 and all(c["auto_send"] is False for c in inst)
    assert inst[0]["message"] and inst[0]["text"] and inst[0]["share_text"].startswith(inst[0]["message"])
    assert "/e/" in inst[0]["share_text"] and inst[0]["whatsapp_url"].startswith("https://wa.me/?text=")
    client.post(inst[0]["mark_sent"]["path"])  # she shared it herself
    left = client.get(f"/api/cases/{cid}/reminders", params={"as_of": (first + dt.timedelta(days=31)).isoformat()}).json()
    assert [c["payment_id"] for c in left["reminders"] if c["kind"] == "instalment"] == [inst[1]["payment_id"]]


def test_cancelled_instalment_reminder_is_not_shown(client, demo):
    cid = demo["cases"]["sharma"]
    first = clock.today() + dt.timedelta(days=7)
    _plan(cid, first)
    with db.session() as s:
        for m in s.exec(select(Message).where(Message.case_id == cid, Message.step == "reminder")):
            m.status = "cancelled"  # what the ledger does once she is paid in full
            s.add(m)
        s.commit()
    r = client.get(f"/api/cases/{cid}/reminders", params={"as_of": (first + dt.timedelta(days=40)).isoformat()}).json()
    assert [c for c in r["reminders"] if c["kind"] == "instalment"] == []


def _sent_step(cid: int, step: str, days_ago: int) -> int:
    at = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with db.session() as s:
        m = Message(case_id=cid, step=step, direction="to_employer", language="hi-en", text="(synthetic)",
                    status="sent", sent_at=at, created_at=at)
        s.add(m)
        s.commit()
        return m.id


def test_next_ladder_step_suggested_after_seven_days(client, demo):
    cid = demo["cases"]["sharma"]
    _sent_step(cid, "polite", 3)
    assert [c for c in client.get(f"/api/cases/{cid}/reminders").json()["reminders"] if c["kind"] == "next_step"] == []
    with db.session() as s:  # the same step, sent 8 days ago instead
        for m in s.exec(select(Message).where(Message.case_id == cid, Message.step == "polite")):
            s.delete(m)
        s.commit()
    _sent_step(cid, "polite", 8)
    cards = [c for c in client.get(f"/api/cases/{cid}/reminders").json()["reminders"] if c["kind"] == "next_step"]
    assert len(cards) == 1 and cards[0]["next_step"] == "firm" and cards[0]["action"]["path"].endswith("/messages/firm")
    assert cards[0]["text"] and cards[0]["auto_send"] is False
    # a reply since then: no nudge
    with db.session() as s:
        s.add(Message(case_id=cid, step="reply", direction="from_employer", language="hi-en", text="agle hafte",
                      status="sent"))
        s.commit()
    assert [c for c in client.get(f"/api/cases/{cid}/reminders").json()["reminders"] if c["kind"] == "next_step"] == []


def test_formal_then_silence_points_to_free_legal_aid(client, demo):
    cid = demo["cases"]["sharma"]
    _sent_step(cid, "formal", 10)
    cards = [c for c in client.get(f"/api/cases/{cid}/reminders").json()["reminders"] if c["kind"] == "next_step"]
    assert cards[0]["next_step"] == "legal_aid" and "DLSA" in cards[0]["text"]
    assert cards[0]["action"]["path"].endswith("/legal-pack")


def test_reminders_404_and_draft_quiet(client, demo):
    assert client.get("/api/cases/9999/reminders").status_code == 404
    d = _new_home_draft(client, demo)
    assert client.get(f"/api/cases/{d['id']}/reminders").json()["reminders"] == []


# --------------------------------------------------------------------------- 8. dues scoping
def test_dues_belong_to_a_worker(client, demo):
    lak, raf = demo["workers"]["lakshmi"], demo["workers"]["rafiq"]
    body = {"kind": "vendor", "party_name": "Mohan", "items": [{"label": "milk", "amount": 900}]}
    a = client.post("/api/dues", json={**body, "worker_id": raf}).json()["account"]["id"]
    lak_list = client.get("/api/dues", params={"worker_id": lak}).json()
    raf_list = client.get("/api/dues", params={"worker_id": raf}).json()
    assert {x["id"] for x in raf_list["accounts"]} == {a}
    assert a not in {x["id"] for x in lak_list["accounts"]}
    assert set(demo["dues"].values()) <= {x["id"] for x in lak_list["accounts"]}  # the demo accounts are hers
    assert client.get("/api/dues").json()["accounts"] == []  # no worker: only accounts that belong to nobody
    assert client.get(f"/api/dues/{a}", params={"worker_id": lak}).status_code == 404
    assert client.get("/api/dues", params={"worker_id": 999}).status_code == 404
    assert client.delete(f"/api/dues/{a}").status_code == 200
    with db.session() as s:
        from app.dues_models import DuesOwner

        assert s.get(DuesOwner, a) is None


# --------------------------------------------------------------------------- 9. inbox duplicate scope
def test_inbox_duplicate_is_per_case(client, demo):
    words = {"text": "Rao garu: agle mahine de denge", "speak": "false", "use_llm": "false"}
    a = client.post(f"/api/inbox/{demo['cases']['sharma']}", data=words).json()
    b = client.post(f"/api/inbox/{demo['cases']['rao']}", data=words).json()
    again = client.post(f"/api/inbox/{demo['cases']['sharma']}", data=words).json()
    assert a["duplicate"] is False and b["duplicate"] is False and again["duplicate"] is True and again["id"] == a["id"]


# --------------------------------------------------------------------------- db: sessions under load
def test_slow_stt_uploads_do_not_starve_other_requests(tmp_path, monkeypatch):
    """20 concurrent voice-note uploads wait on a slow (mocked) STT. The engine here has a TINY pool (2
    connections, no overflow, 2 s timeout): if any upload held its session across the STT await, the pool would
    be exhausted and the GET would block and fail. No session is held, so all succeed and the GET is fast."""
    from sqlmodel import create_engine

    from app.routes import inbox as inbox_routes

    monkeypatch.setenv("LLM_PROVIDER", "none")
    eng = create_engine(f"sqlite:///{(tmp_path / 'load.db').as_posix()}", connect_args={"check_same_thread": False},
                        pool_size=2, max_overflow=0, pool_timeout=2)
    db.set_engine(eng)
    ids = seed.reset()
    cid = ids["cases"]["sharma"]

    async def slow_stt(data, filename, lang=None, mode=None):
        await asyncio.sleep(2.0)
        return {"transcript": f"agle hafte de denge {len(data)}", "language_code": "hi-IN,en-IN",
                "detected_language_code": "hi-IN", "mode": mode}

    monkeypatch.setattr(inbox_routes, "transcribe_upload", slow_stt)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            posts = [asyncio.create_task(ac.post(f"/api/inbox/{cid}", data={"speak": "false", "use_llm": "false"},
                                                 files={"audio": (f"n{i}.ogg", b"OggS" + bytes([i]) * (i + 1),
                                                                  "audio/ogg")}))
                     for i in range(20)]
            await asyncio.sleep(1.0)  # every upload is now waiting inside the slow STT
            t0 = time.perf_counter()
            g = await ac.get(f"/api/cases/{cid}")
            took = time.perf_counter() - t0
            still_waiting = sum(not p.done() for p in posts)
            res = await asyncio.gather(*posts)
            return g, took, still_waiting, res

    g, took, still_waiting, res = asyncio.run(run())
    assert g.status_code == 200 and took < 1.5 and still_waiting > 0
    assert [r.status_code for r in res] == [200] * 20
    assert len({r.json()["id"] for r in res}) == 20
    assert eng.pool.checkedout() == 0
    with db.session() as s:
        from app.models import DiaryEntry
        from app.routes.cases import verify_chain

        entries = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == ids["workers"]["lakshmi"])
                              .order_by(DiaryEntry.id)))
        assert verify_chain(entries)["valid"]  # 20 appends, one chain, no fork


def test_file_sqlite_uses_wal_and_nullpool(tmp_path):
    from sqlalchemy.pool import NullPool

    eng = db._make_engine(f"sqlite:///{(tmp_path / 'w.db').as_posix()}")
    assert isinstance(eng.pool, NullPool)
    with eng.connect() as c:
        assert c.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert c.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == db.SQLITE_BUSY_TIMEOUT_MS


def test_db_run_helper_commits_and_closes():
    db.init_db(db.get_engine())
    def add(s):
        w = Worker(name="Asha")
        s.add(w)
        s.flush()
        return w.id

    wid = db.run(add)
    assert db.run(lambda s: s.get(Worker, wid).name, commit=False) == "Asha"


# --------------------------------------------------------------------------- 11. seed consistency + clock
def test_seed_payment_rows_match_amount_paid(client, demo):
    with db.session() as s:
        for c in s.exec(select(Case)):
            paid = sum(p.amount for p in s.exec(select(Payment).where(Payment.case_id == c.id, Payment.status == "paid")))
            assert abs(paid - c.amount_paid) < 0.01, c.id
    reddy = client.get(f"/api/cases/{demo['cases']['reddy']}").json()
    assert reddy["status"] == "paid" and reddy["amount_paid"] == 0 and reddy["payments"] == []


def test_clock_override(monkeypatch):
    monkeypatch.setenv("BAAKI_TODAY", "2026-11-09")
    assert clock.today() == dt.date(2026, 11, 9) and clock.now().date() == dt.date(2026, 11, 9)
    monkeypatch.setenv("BAAKI_TODAY", "not-a-date")
    assert clock.today() == dt.datetime.now(clock.IST).date()


def test_server_start_seeds_an_empty_database(monkeypatch):
    """main.py's startup hook (SEED_ON_BOOT) calls seed.ensure_seeded(): a fresh server is not empty."""
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("SEED_ON_BOOT", "1")
    monkeypatch.setenv("BAAKI_SEED_ON_BOOT", "1")
    with TestClient(app) as c:
        d = c.get("/api/workers/1/dashboard")
        assert d.status_code == 200 and len(d.json()["cards"]) == 3


# --------------------------------------------------------------------------- F2 follow-up: money view in my views
def test_case_view_and_card_show_claims_overpaid_and_stale_notes(client, demo):
    """Employer "I've paid" waits as a claim: the card counts it; once she confirms, the note made for the old
    balance is flagged stale and the case view carries the ledger's overpaid figure."""
    from app import ledger

    cid, lid = demo["cases"]["sharma"], demo["workers"]["lakshmi"]
    token = demo["employer_tokens"]["sharma"]
    with db.session() as s:
        case = s.get(Case, cid)
        m = Message(case_id=cid, step="polite", direction="to_employer", language="hi-en", text="(synthetic)",
                    status="sent", sent_at=db.now_iso())
        s.add(m)
        s.flush()
        ledger.snapshot_message(s, m, case)
        s.commit()
        mid = m.id
    c0 = client.get(f"/api/cases/{cid}").json()
    assert c0["overpaid"] == 0 and c0["pending_claims"]["count"] == 0
    assert next(x for x in c0["messages"] if x["id"] == mid)["stale"] is False

    r = client.post(f"/api/e/{token}/pay", json={"amount": 3000, "alert_audio": False})
    assert r.status_code == 200, r.text
    card = next(x for x in client.get(f"/api/workers/{lid}/dashboard").json()["cards"] if x["case_id"] == cid)
    assert card["pending_claims"] == 1 and card["pending_claims_amount"] == 3000 and card["overpaid"] == 0
    c1 = client.get(f"/api/cases/{cid}").json()
    pid = c1["pending_claims"]["proposal_ids"][0]
    assert c1["amount_paid"] == 0  # a claim moves no money

    d = client.post(f"/api/hisaab/{pid}/decide", json={"decision": "accept"})
    assert d.status_code == 200, d.text
    c2 = client.get(f"/api/cases/{cid}").json()
    assert c2["amount_paid"] == 3000 and c2["pending_claims"]["count"] == 0
    note = next(x for x in c2["messages"] if x["id"] == mid)
    assert note["stale"] is True and note["balance_at_make"] == demo["totals"]["sharma"]
    card = next(x for x in client.get(f"/api/workers/{lid}/dashboard").json()["cards"] if x["case_id"] == cid)
    assert card["pending_claims"] == 0


# --------------------------------------------------------------------------- F1 follow-ups
def test_reply_card_shows_past_payment_for_her_to_check(client, demo):
    cid = demo["cases"]["sharma"]
    r = client.post(f"/api/inbox/{cid}", data={"text": "5 November ko 2000 diya tha, baaki agle hafte",
                                               "lang": "hi-en", "said_on": "2026-11-09", "speak": "false",
                                               "use_llm": "false"}).json()
    past = r["past_payments"]
    assert past and past[0]["amount"] == 2000 and past[0]["paid_on"] == "2026-11-05" and past[0]["recorded"] is False
    assert "₹2,000" in past[0]["line"] and past[0]["line_lang"] == "te-IN"
    assert client.get(f"/api/cases/{cid}").json()["amount_paid"] == 0  # read-only: no money recorded


def test_card_hours_unknown_stays_unknown(client, demo):
    lid = demo["workers"]["lakshmi"]
    d = _new_home_draft(client, demo, name="Kapoor ji")
    client.post(f"/api/cases/{d['id']}/confirm", json={"confirmed": True})
    card = next(c for c in client.get(f"/api/workers/{lid}/dashboard").json()["cards"] if c["case_id"] == d["id"])
    assert card["hours_per_day"] is None
    sharma = next(c for c in client.get(f"/api/workers/{lid}/dashboard").json()["cards"]
                  if c["case_id"] == demo["cases"]["sharma"])
    assert sharma["hours_per_day"] == 2
