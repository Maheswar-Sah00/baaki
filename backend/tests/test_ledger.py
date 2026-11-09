"""F2 ledger and trust: one money writer, derived status/badge/plan, "I've paid" as a claim she confirms.
Offline: mocked Gnani, no LLM, synthetic people only."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import db, ledger
from app.hisaab_models import HisaabClaim, HisaabProposal
from app.ledger_models import FairBadgeGrant, LedgerPlan
from app.main import app
from app.models import Case, Employer, Message, Payment

from .b_data import make_case, tts_ok


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _tts_log(ogg, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


def claim_and_confirm(client, token, amount=None, *, method="upi", alert_audio=False):
    """Sharma ji taps "I've paid", Lakshmi confirms. Returns (pay response, decide response)."""
    body = {"method": method, "alert_audio": alert_audio}
    if amount is not None:
        body["amount"] = amount
    r = client.post(f"/api/e/{token}/pay", json=body)
    assert r.status_code == 200, r.text
    d = client.post(f"/api/hisaab/{r.json()['claim']['id']}/decide", json={"decision": "accept"})
    assert d.status_code == 200, d.text
    return r.json(), d.json()


def _keys(obj) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _keys(v)
    return out


def _sent_polite(client, ids):
    m = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "audio": False}).json()
    client.post(f"/api/messages/{m['message_id']}/sent")
    return m


# --------------------------------------------------------------------------- claim -> confirm / dispute
def test_claim_records_nothing_until_she_confirms_then_alert_and_badge(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, seen)
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/pay", json={})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["pending_confirmation"] and not b["fully_paid"] and b["badge"] is None and b["alert"] is None
    assert b["balance"] == 13000 and b["claimed"] == 13000 and b["paid"] == 0
    assert "లక్ష్మి" not in b["message"] and "लक्ष्मी" in b["message"]       # his language (Hinglish)
    assert b["message_en"].startswith("Thank you. Lakshmi will confirm")
    assert seen == []                                                       # no Timbre call on his tap
    with db.session() as s:
        assert not list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))
        assert not list(s.exec(select(Message).where(Message.step == "paid_alert")))
        assert s.get(Employer, ids["employer_id"]).fair_employer is False
        assert s.get(Case, ids["case_id"]).status == "confirmed"
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["pending_confirmation"] and page["pending_claim"]["amount"] == 13000 and page["badge"] is None
    # a second tap returns the same claim, no duplicate
    again = client.post(f"/api/e/{ids['token']}/pay", json={}).json()
    assert again["already_claimed"] and again["claim"]["id"] == b["claim"]["id"]

    # she hears it in Telugu and sees it in her Hisaab list
    hers = client.get(f"/api/hisaab/case/{ids['case_id']}").json()
    p = hers["proposals"][0]
    assert p["type"] == "payment_claim" and p["readback"]["text"].startswith("శర్మ గారు అంటున్నారు")
    assert "మీకు డబ్బులు అందాయా?" in p["readback"]["text"] and hers["pending_claims"] == 1

    d = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "accept", }).json()
    assert d["balance"] == 0 and d["fully_paid"] and d["case_status"] == "paid"
    assert d["badge"]["title"] == "Fair Employer"
    assert d["alert"]["text"].startswith("డబ్బులు వచ్చేశాయి!") and "₹13,000" in d["alert"]["text"]
    assert d["alert"]["audio"]["url"] and len(seen) == 1 and seen[0]["text"].startswith("<excited>")
    with db.session() as s:
        pays = list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))
        assert len(pays) == 1 and pays[0].amount == 13000 and "confirmed by her" in pays[0].note
        alerts = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "paid_alert")))
        assert len(alerts) == 1 and alerts[0].audio_path
        assert s.get(Employer, ids["employer_id"]).fair_employer is True
        claim = s.exec(select(HisaabClaim)).first()
        assert claim.alert_message_id == alerts[0].id
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["badge"]["reason"] == "paid_in_full" and page["claims"][0]["status"] == "accepted"
    assert client.post(f"/api/e/{ids['token']}/pay", json={}).status_code == 409


def test_claim_rejected_is_disputed_and_nothing_changes(client):
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/pay", json={"amount": 5000, "method": "cash"}).json()
    d = client.post(f"/api/hisaab/{r['claim']['id']}/decide", json={"decision": "reject"}).json()
    assert d["proposal"]["display_state"] == "disputed" and not d["changed"] and d["balance"] == 13000
    assert d["alert"] is None and d["badge"] is None
    with db.session() as s:
        assert not list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))
        assert not list(s.exec(select(Message).where(Message.step == "paid_alert")))
        assert s.get(Case, ids["case_id"]).status == "confirmed"
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["claims"][0]["display_state"] == "disputed" and not page["pending_confirmation"]
    assert page["claims"][0]["status_text_en"].startswith("Lakshmi says the money has not arrived")
    assert page["balance"] == 13000
    # he can say it again (e.g. he sent it now)
    assert client.post(f"/api/e/{ids['token']}/pay", json={"amount": 5000}).json()["pending_confirmation"]


def test_partial_claims_are_capped_by_pending(client):
    ids = make_case()
    client.post(f"/api/e/{ids['token']}/pay", json={"amount": 8000})
    r = client.post(f"/api/e/{ids['token']}/pay", json={"amount": 6000})
    assert r.status_code == 400 and r.json()["detail"]["error"] == "too_much"
    ok = client.post(f"/api/e/{ids['token']}/pay", json={}).json()          # the rest
    assert ok["claimed"] == 5000


def test_employer_responses_never_carry_case_id(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    _sent_polite(client, ids)
    t = ids["token"]
    bodies = [client.get(f"/api/e/{t}").json(),
              client.post(f"/api/e/{t}/plan", json={"instalments": 2}).json(),
              client.post(f"/api/e/{t}/pay", json={"amount": 1000, "alert_audio": False}).json(),
              client.post(f"/api/hisaab/e/{t}", data={"text": "do hazaar cash diye", "readback_audio": "false"}).json(),
              client.get(f"/api/hisaab/e/{t}").json(),
              client.post(f"/api/e/{t}/reply", data={"text": "Shanivaar ko de dunga", "use_llm": "false"}).json(),
              client.get(f"/api/e/{t}").json()]
    for b in bodies:
        assert "case_id" not in _keys(b), b
    # the worker's own views still have it
    assert client.get(f"/api/hisaab/case/{ids['case_id']}").json()["case_id"] == ids["case_id"]


# --------------------------------------------------------------------------- plans
def test_pre_plan_payment_does_not_settle_an_instalment(client):
    ids = make_case()
    claim_and_confirm(client, ids["token"], 6000)                   # before the plan
    plan = client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 2}).json()
    assert [i["amount"] for i in plan["instalments"]] == [3500, 3500]
    claim_and_confirm(client, ids["token"], 1000)                   # after the plan
    page = client.get(f"/api/e/{ids['token']}").json()
    # the old rule (amount_paid 7000 covers both) settled everything; only the 1,000 counts
    assert [p["status"] for p in page["plan"]] == ["planned", "planned"] and page["balance"] == 6000
    assert page["status"] == "plan"
    claim_and_confirm(client, ids["token"], 2500)
    page = client.get(f"/api/e/{ids['token']}").json()
    assert [p["status"] for p in page["plan"]] == ["settled", "planned"] and page["balance"] == 3500
    with db.session() as s:
        rems = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "reminder")
                           .order_by(Message.id)))
        assert [r.status for r in rems] == ["cancelled", "scheduled"]


def test_correction_after_plan_resplits_instead_of_settling(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 2})       # 6500 + 6500
    p = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "October mein do hazaar cash diye the"}).json()
    d = client.post(f"/api/hisaab/{p['proposal']['id']}/decide", json={"decision": "accept"}).json()
    assert d["balance"] == 11000 and d["plan"]["resplit"]
    page = client.get(f"/api/e/{ids['token']}").json()
    assert [(x["amount"], x["status"]) for x in page["plan"]] == [(5500, "planned"), (5500, "planned")]
    with db.session() as s:
        rems = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "reminder")))
        assert all("₹5,500" in r.text and r.status == "scheduled" for r in rems)


def test_total_up_after_full_pay_reopens_and_removes_badge(client, monkeypatch):
    ids = make_case()
    _, d = claim_and_confirm(client, ids["token"])
    assert d["case_status"] == "paid" and d["badge"]
    # the worker adds a month she forgot: the calculation goes up by 4,000 (through apply_calc)
    from app.routes import cases

    calc = {"total": 17000.0, "min_wage_shortfall": 0.0, "inputs": {"unpaid_months": ["a", "b", "c", "d"],
                                                                     "category": "unskilled"}}
    monkeypatch.setattr(cases, "calc_from_facts", lambda facts, today=None: calc)
    monkeypatch.setattr(cases, "_write_items", lambda s, case, calc: None)
    with db.session() as s:
        c = s.get(Case, ids["case_id"])
        cases.apply_calc(s, c, {"monthly_wage": 4000})
        s.commit()
        assert c.status == "confirmed" and c.balance == 4000
        assert s.get(Employer, ids["employer_id"]).fair_employer is False
        assert not s.exec(select(FairBadgeGrant).where(FairBadgeGrant.active == True)).first()  # noqa: E712
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["badge"] is None and page["balance"] == 4000 and page["status"] == "confirmed"
    # paying the rest gives it back
    _, d = claim_and_confirm(client, ids["token"])
    assert d["badge"] and d["case_status"] == "paid"


def test_reopen_does_not_take_a_badge_this_case_did_not_give(client):
    ids = make_case()
    claim_and_confirm(client, ids["token"])
    with db.session() as s:
        e = s.get(Employer, ids["employer_id"])
        e.kaam_patta_signed = True          # badge also earned another way
        s.add(e)
        c = s.get(Case, ids["case_id"])
        c.total_due += 1000
        ledger.reconcile(s, c)
        s.commit()
        assert s.get(Employer, ids["employer_id"]).fair_employer is True


def test_total_below_paid_shows_overpaid_and_cancels_instalments(client):
    ids = make_case()
    client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 2})       # 6500 + 6500
    claim_and_confirm(client, ids["token"], 6500)
    with db.session() as s:
        c = s.get(Case, ids["case_id"])
        c.total_due = 5000.0                 # a correction to the calculation, below what was paid
        rec = ledger.reconcile(s, c)
        s.commit()
        assert rec["overpaid"] == 1500 and rec["fully_paid"] and c.status == "paid"
        insts = list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"], Payment.instalment_no != None)  # noqa: E711
                            .order_by(Payment.instalment_no)))
        assert [p.status for p in insts] == ["settled", "cancelled"]
        rems = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "reminder")))
        assert all(r.status == "cancelled" for r in rems)
        assert s.exec(select(LedgerPlan)).first().status == "done"
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["overpaid"] == 1500 and page["balance"] == 0
    assert [p["status"] for p in page["plan"]] == ["settled"]                # cancelled ones are not shown
    assert client.get(f"/api/hisaab/case/{ids['case_id']}").json()["overpaid"] == 1500


def test_total_up_during_plan_resplits_remaining(client):
    ids = make_case()
    client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 3})       # 4334 + 4333 + 4333
    claim_and_confirm(client, ids["token"], 4334)
    with db.session() as s:
        c = s.get(Case, ids["case_id"])
        c.total_due += 3000
        rec = ledger.reconcile(s, c)
        s.commit()
        assert rec["plan"]["resplit"] and c.status == "plan"
    plan = client.get(f"/api/e/{ids['token']}").json()["plan"]
    assert plan[0]["status"] == "settled" and [p["amount"] for p in plan[1:]] == [5833, 5833]
    assert sum(p["amount"] for p in plan[1:]) == 13000 + 3000 - 4334


def test_record_payment_caps_and_reports_excess(client):
    ids = make_case()
    with db.session() as s:
        c = s.get(Case, ids["case_id"])
        res = ledger.record_payment(s, c, 15000, "cash", None, "test")
        s.commit()
        assert res.recorded == 13000 and res.excess == 2000 and res.fully_paid
        assert ledger.overpaid(s, c) == 2000 and c.amount_paid == 13000
        with pytest.raises(ledger.LedgerError):
            ledger.record_payment(s, c, 100, "cash", None, "test")


# --------------------------------------------------------------------------- the employer page
def test_employer_page_never_plays_a_draft(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    m = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False}).json()
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["message"] is None and page["audio_url"] is None
    assert client.post(f"/api/e/{ids['token']}/played").json()["message_id"] is None
    client.post(f"/api/messages/{m['message_id']}/sent")
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["message"]["message_id"] == m["message_id"] and page["audio_url"] == m["audio_url"]


def test_stale_note_flagged_and_not_reused(client):
    ids = make_case()
    m = _sent_polite(client, ids)
    assert client.get(f"/api/e/{ids['token']}").json()["stale"] is False
    claim_and_confirm(client, ids["token"], 3000)
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["stale"] and page["message"]["stale"] and page["message"]["balance_at_make"] == 13000
    assert "₹13,000" in page["stale_note"] and "₹10,000" in page["stale_note"]
    listed = client.get(f"/api/cases/{ids['case_id']}/messages").json()["messages"]
    assert [x["stale"] for x in listed if x["message_id"] == m["message_id"]] == [True]
    # same balance figure inside other text no longer counts: a new note is made for ₹10,000
    again = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "audio": False}).json()
    assert again["reused"] is False and again["balance"] == 10000 and again["stale"] is False
    third = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "audio": False}).json()
    assert third["reused"] is True and third["message_id"] == again["message_id"]


def test_reply_accepts_typed_text(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/reply", data={"text": "Shanivaar ko 5000 de dunga", "use_llm": "false"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["source"] == "text" and b["transcript"].startswith("Shanivaar") and b["original_audio_url"] is None
    assert [a["value"] for a in b["amounts"]] == [5000]
    assert not any(q.url.path == "/stt/v3" for q in mock_gnani.requests)     # no STT for typed text
    assert client.post(f"/api/e/{ids['token']}/reply", data={}).status_code == 400


# --------------------------------------------------------------------------- replay
def test_story_shows_claim_then_confirmation(client):
    ids = make_case(diary_days=0)
    claim_and_confirm(client, ids["token"], 3000)
    r = client.post(f"/api/e/{ids['token']}/pay", json={"amount": 2000, "alert_audio": False}).json()
    client.post(f"/api/hisaab/{r['claim']['id']}/decide", json={"decision": "reject"})
    out = client.get(f"/api/story/{ids['case_id']}").json()
    kinds = [e["kind"] for e in out["events"]]
    assert kinds == ["spoke", "claim_made", "claim_confirmed", "paid", "paid_alert", "claim_made", "claim_disputed"]
    ev = {}
    for e in out["events"]:
        ev.setdefault(e["kind"], e)   # the first of each kind
    assert ev["claim_made"]["title"]["en"] == "Sharma ji said he paid"
    assert ev["claim_confirmed"]["title"]["en"] == "Lakshmi confirmed the money arrived"
    assert ev["claim_made"]["at_field"] == "hisaab_proposal.created_at"
    with db.session() as s:
        p = s.exec(select(HisaabProposal).order_by(HisaabProposal.id)).first()
        assert ev["claim_made"]["at"] == p.created_at and ev["claim_confirmed"]["at"] == p.decided_at
    assert out["balance"] == 10000 and out["payments_match_case"]


# --------------------------------------------------------------------------- public sandbox
def test_sandbox_mark_paid_is_claim_plus_labelled_demo_confirmation(client, mock_gnani):
    from app import sandbox_core

    sandbox_core.reset_limits()
    sid = client.post("/api/sandbox").json()["sandbox_id"]
    pb = client.post(f"/api/sandbox/{sid}/paid").json()
    assert pb["fully_paid"] and pb["balance"] == 0 and pb["status"] == "paid" and pb["badge"]
    assert pb["confirmation"]["label"] == "Demo: Lakshmi confirmed (synthetic)" and pb["confirmation"]["demo"]
    assert pb["alert"]["headline"] == "Paisa aa gaya!"
    w = client.get(f"/api/sandbox/{sid}/worker").json()
    assert w["paid"] and w["confirmation"]["synthetic"] and w["alert"]["text"]
    with db.session() as s:
        p = s.exec(select(HisaabProposal).where(HisaabProposal.kind == "said_paid")).one()
        assert p.status == "accepted"
        assert s.exec(select(HisaabClaim).where(HisaabClaim.proposal_id == p.id)).one().demo
        pay = s.get(Payment, p.payment_id)
        assert "Demo: Lakshmi confirmed" in pay.note
    assert mock_gnani.requests == []                                     # zero Gnani calls
    assert client.post(f"/api/sandbox/{sid}/paid").json()["already_paid"]
