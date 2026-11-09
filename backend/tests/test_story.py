"""V12 Case Replay (GET /api/story/{case_id}). Offline, synthetic data, 0 Gnani calls."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import db, storage, verify_guard
from app.inbox_models import InboxCard, InboxPromise
from app.main import app
from app.models import Case, DiaryEntry, Message, Payment
from app.story_core import balance_after, parse_at

from .b_data import make_case


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _full_case() -> dict:
    """Lakshmi vs Sharma ji (fictional): Rs 13,000 due, a polite note, a reply, then two payments."""
    info = make_case(diary_days=0)  # total 13,000 = 3 x 4,000 + 1,000
    cid = info["case_id"]
    key = storage.get_storage().put(f"c{cid}/polite.ogg", b"OggS-fake-polite-note")
    with db.session() as s:
        c = s.get(Case, cid)
        c.created_at = "2026-11-09T03:32:00.000000Z"
        c.readback_confirmed, c.confirmed_at = True, "2026-11-09T03:33:10.000000Z"
        c.updated_at = "2026-11-09T03:33:10.000000Z"
        s.add(c)
        for i, day in enumerate(("2026-10-30", "2026-10-31")):
            s.add(DiaryEntry(worker_id=info["worker_id"], employer_id=info["employer_id"], case_id=cid,
                             timestamp=f"{day}T04:30:00.000000Z", text=f"Sharma ji ke ghar, do ghante {i}",
                             hash=f"h{i}" * 8))
        polite = Message(case_id=cid, step="polite", direction="to_employer", language="hi-en",
                         text="AI note for Lakshmi", audio_path=key, status="played",
                         created_at="2026-11-09T03:35:00.000000Z", sent_at="2026-11-09T03:36:30.000000Z")
        s.add(polite)
        s.add(Message(case_id=cid, step="reply", direction="from_employer", language="hi-en",
                      text="Agle hafte 5,000 de dunga", audio_path=f"c{cid}/reply_in.webm", status="replied",
                      created_at="2026-11-09T14:12:00.000000Z", sent_at="2026-11-09T14:12:00.000000Z"))
        s.add(Message(case_id=cid, step="reply", direction="to_worker", language="te-IN", text="వచ్చే వారం",
                      audio_path=f"c{cid}/reply_out.ogg", status="sent",
                      created_at="2026-11-09T14:12:00.000000Z", sent_at="2026-11-09T14:12:00.000000Z"))
        # a scheduled reminder and a planned instalment have not happened: never on the timeline
        s.add(Message(case_id=cid, step="reminder", direction="to_employer", status="scheduled",
                      created_at="2026-11-09T14:20:00.000000Z", text="reminder"))
        s.add(Payment(case_id=cid, amount=4000, status="planned", due_date="2026-12-01", instalment_no=2,
                      instalments_total=2, created_at="2026-11-09T14:20:00.000000Z"))
        # payment 1 and its alert share one instant (as POST /pay writes them); payment 2 is stored with +05:30
        s.add(Payment(case_id=cid, amount=5000, method="upi", status="paid", paid_at="2026-11-09T14:40:00Z",
                      created_at="2026-11-09T14:40:00Z"))
        s.add(Message(case_id=cid, step="paid_alert", direction="to_worker", language="te-IN", text="డబ్బులు",
                      audio_path=f"c{cid}/alert.ogg", status="sent",
                      created_at="2026-11-09T14:40:00Z", sent_at="2026-11-09T14:40:00Z"))
        s.add(Payment(case_id=cid, amount=8000, method="cash", status="paid", paid_at="2026-11-10T09:00:00+05:30",
                      created_at="2026-11-10T03:30:01.000000Z"))
        c.amount_paid = 13000
        s.add(c)
        s.commit()
        s.refresh(polite)
        pid = polite.id
    sha = verify_guard.audio_sha256(b"OggS-fake-polite-note")
    verify_guard.write_cache(pid, sha, {"verified": True, "amounts_heard": [13000], "disclosure_heard": True,
                                        "checked_at": "2026-11-09T03:36:05.000000Z"})
    return {**info, "polite_id": pid}


def test_full_case_order_times_and_balance(client):
    info = _full_case()
    r = client.get(f"/api/story/{info['case_id']}")
    assert r.status_code == 200, r.text
    out = r.json()
    kinds = [e["kind"] for e in out["events"]]
    assert kinds == ["work_logged", "work_logged", "spoke", "readback_confirmed", "note_made", "listen_twice",
                     "sent", "employer_replied", "reply_translated", "paid", "paid_alert", "paid"]
    # every time is the stored string, unchanged, in stored-time order
    ats = [e["at"] for e in out["events"]]
    assert ats == ["2026-10-30T04:30:00.000000Z", "2026-10-31T04:30:00.000000Z", "2026-11-09T03:32:00.000000Z",
                   "2026-11-09T03:33:10.000000Z", "2026-11-09T03:35:00.000000Z", "2026-11-09T03:36:05.000000Z",
                   "2026-11-09T03:36:30.000000Z", "2026-11-09T14:12:00.000000Z", "2026-11-09T14:12:00.000000Z",
                   "2026-11-09T14:40:00Z", "2026-11-09T14:40:00Z", "2026-11-10T09:00:00+05:30"]
    times = [parse_at(a) for a in ats]
    assert times == sorted(times)
    assert [e["seq"] for e in out["events"]] == list(range(1, 13))
    # the meter: 13,000 -> 8,000 -> 0, via Case.balance
    pays = [e for e in out["events"] if e["kind"] == "paid"]
    assert [p["amount_delta"] for p in pays] == [-5000, -8000]
    assert [p["balance_after"] for p in pays] == [8000, 0]
    assert pays[1]["at_field"] == "payment.paid_at"
    assert out["total_due"] == 13000 and out["balance"] == 0 and out["paid_in_full"] is True
    assert out["payments_match_case"] is True
    # audio chips point at the stored files
    ev = {e["kind"]: e for e in out["events"]}
    assert ev["note_made"]["audio_url"] == f"/api/media/c{info['case_id']}/polite.ogg"
    assert ev["employer_replied"]["audio_url"].endswith("reply_in.webm")
    assert ev["paid_alert"]["audio_url"].endswith("alert.ogg")
    assert ev["note_made"]["step"] == "polite" and ev["note_made"]["title"]["en"] == "Voice note made (Polite)"
    assert set(ev["paid_alert"]["title"]) == {"en", "te", "hi"}
    assert ev["listen_twice"]["at_field"] == "verify_cache.checked_at" and ev["listen_twice"]["verified"] is True
    # "played" has no stored time: untimed, not invented
    assert [u["kind"] for u in out["untimed"]] == ["employer_listened"]
    assert out["untimed"][0]["source_id"] == info["polite_id"]
    # scheduled reminder and planned instalment never appear
    assert "reminder" not in str(kinds) and all(e.get("amount") != 4000 for e in out["events"])


def test_times_equal_db_rows(client):
    info = _full_case()
    out = client.get(f"/api/story/{info['case_id']}").json()
    with db.session() as s:
        for e in out["events"]:
            if e["source_table"] == "payment":
                assert e["at"] == s.get(Payment, e["source_id"]).paid_at
            elif e["source_table"] == "message" and e["kind"] in ("sent", "employer_replied", "paid_alert"):
                assert e["at"] == s.get(Message, e["source_id"]).sent_at
            elif e["source_table"] == "message" and e["kind"] == "note_made":
                assert e["at"] == s.get(Message, e["source_id"]).created_at
            elif e["source_table"] == "diaryentry":
                assert e["at"] == s.get(DiaryEntry, e["source_id"]).timestamp


def test_read_only(client):
    info = _full_case()
    with db.session() as s:
        before = s.get(Case, info["case_id"]).model_dump()
        n_msgs = len(s.exec(select(Message)).all())
    client.get(f"/api/story/{info['case_id']}")
    with db.session() as s:
        assert s.get(Case, info["case_id"]).model_dump() == before
        assert len(s.exec(select(Message)).all()) == n_msgs


def test_live_pay_flow_matches_case_screen(client):
    """Payments in parts through the real employer endpoints: the replay's balance equals the case screen's."""
    info = make_case(diary_days=0)
    tok = info["token"]
    r1 = client.post(f"/api/e/{tok}/pay", json={"amount": 3000, "method": "cash", "alert_audio": False})
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"/api/e/{tok}/pay", json={"amount": 2500, "alert_audio": False})
    out = client.get(f"/api/story/{info['case_id']}").json()
    case_screen = client.get(f"/api/cases/{info['case_id']}").json()
    pays = [e for e in out["events"] if e["kind"] == "paid"]
    assert [p["balance_after"] for p in pays] == [r1.json()["balance"], r2.json()["balance"]] == [10000, 7500]
    assert out["balance"] == case_screen["balance"] == 7500
    alerts = [e for e in out["events"] if e["kind"] == "paid_alert"]
    assert len(alerts) == 2 and "audio_url" not in alerts[0]   # no audio was made, so no chip
    # each payment comes right before its own alert (same stored instant)
    kinds = [e["kind"] for e in out["events"] if e["kind"] in ("paid", "paid_alert")]
    assert kinds == ["paid", "paid_alert", "paid", "paid_alert"]
    assert out["paid_in_full"] is False


def test_empty_case_minimal_timeline(client):
    info = make_case(diary_days=0)
    out = client.get(f"/api/story/{info['case_id']}").json()
    assert [e["kind"] for e in out["events"]] == ["spoke"]   # not confirmed, nothing sent, nothing paid
    assert out["balance"] == out["total_due"] == 13000
    assert out["untimed"] == [] and out["skipped"] == []


def test_unknown_case_404(client):
    assert client.get("/api/story/999999").status_code == 404


def test_unreadable_time_is_skipped_not_guessed(client):
    info = make_case(diary_days=0)
    with db.session() as s:
        s.add(Payment(case_id=info["case_id"], amount=100, status="paid", paid_at="last tuesday",
                      created_at="2026-11-09T10:00:00Z"))
        s.commit()
    out = client.get(f"/api/story/{info['case_id']}").json()
    assert "paid" not in [e["kind"] for e in out["events"]]
    assert out["skipped"][0]["source_table"] == "payment"


def test_inbox_reply_and_promise(client):
    info = make_case(diary_days=0)
    cid = info["case_id"]
    with db.session() as s:
        c = s.get(Case, cid)
        c.created_at = "2026-11-09T03:00:00.000000Z"
        s.add(c)
        d = DiaryEntry(worker_id=info["worker_id"], employer_id=info["employer_id"], case_id=cid, kind="evidence",
                       timestamp="2026-11-09T12:00:00.000000Z", text="reply", hash="e" * 64)
        s.add(d)
        s.flush()
        card = InboxCard(case_id=cid, worker_id=info["worker_id"], employer_id=info["employer_id"],
                         transcript="agle hafte de dungi", translation="వచ్చే వారం ఇస్తాను", said_on="2026-11-09",
                         audio_path=f"c{cid}/tr.ogg", diary_entry_id=d.id, created_at="2026-11-09T12:00:00.000000Z")
        s.add(card)
        s.flush()
        s.add(InboxPromise(card_id=card.id, case_id=cid, amount=5000, due_date="2026-11-15", status="broken",
                           status_at="2026-11-16T05:00:00.000000Z", created_at="2026-11-09T12:00:00.000000Z"))
        s.commit()
    out = client.get(f"/api/story/{cid}").json()
    kinds = [e["kind"] for e in out["events"]]
    assert kinds == ["spoke", "reply_saved", "promised", "promise_broken"]  # the diary copy of the card is not doubled
    assert out["events"][-1]["at"] == "2026-11-16T05:00:00.000000Z"


def test_balance_after_uses_case_balance():
    c = Case(worker_id=1, employer_id=1, total_due=12692)
    assert balance_after(c, 5000) == 7692
    assert balance_after(c, 13000) == 0   # never negative, like the case screen


def test_seeded_demo(client):
    seeded = client.post("/api/demo/reset").json()
    cid = seeded["cases"]["sharma"]
    out = client.get(f"/api/story/{cid}").json()
    kinds = [e["kind"] for e in out["events"]]
    assert kinds[:5] == ["work_logged"] * 5
    assert kinds[5:] == ["spoke", "readback_confirmed"]
    assert out["total_due"] == seeded["totals"]["sharma"] and out["balance"] == out["total_due"]
    assert out["case"]["worker"]["name"] == "Lakshmi" and out["case"]["employer"]["name"] == "Sharma ji"
    # the seed stamps confirmed_at microseconds before created_at: same second, intake order kept
    times = [parse_at(e["at"]).replace(microsecond=0) for e in out["events"]]
    assert times == sorted(times)
    # Reddy garu's October salary (stored 5 Nov) shows as a payment; his case total is already 0
    reddy = client.get(f"/api/story/{seeded['cases']['reddy']}").json()
    paid = [e for e in reddy["events"] if e["kind"] == "paid"]
    assert len(paid) == 1 and paid[0]["at"] == "2026-11-05T10:12:00Z" and paid[0]["balance_after"] == 0


def test_feature_rows_older_than_the_case_are_skipped(client):
    """Inbox / Exit Kit rows survive a demo reset and SQLite reuses ids: a row older than the case is not its own."""
    from app.exit_kit import ExitKit

    info = make_case(diary_days=0)
    cid = info["case_id"]
    with db.session() as s:
        c = s.get(Case, cid)
        c.created_at = "2026-11-09T10:00:00.000000Z"
        s.add(c)
        s.add(ExitKit(worker_id=info["worker_id"], case_id=cid, last_day="2026-11-08", due_by="2026-11-11",
                      total=13768, created_at="2026-11-09T09:00:00.000000Z"))   # older: another case's
        s.add(ExitKit(worker_id=info["worker_id"], case_id=cid, last_day="2026-11-08", due_by="2026-11-11",
                      total=13768, created_at="2026-11-09T11:00:00.000000Z"))
        s.commit()
    out = client.get(f"/api/story/{cid}").json()
    assert [e["kind"] for e in out["events"]] == ["spoke", "exit_kit"]
    assert out["events"][1]["at"] == "2026-11-09T11:00:00.000000Z"
    assert out["skipped"][0]["source_table"] == "exit_kit"
