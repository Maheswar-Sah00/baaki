"""Haq Raise (/api/raise). Offline: Gnani TTS/STT mocked, LLM faked. Synthetic people only."""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, db, llm, raise_core
from app.main import app
from app.messages import amounts_in
from app.models import Case, Employer, Worker
from app.routes import raise_ as raise_route

from .b_data import tts_ok
from .conftest import multipart_fields

TODAY = dt.date(2026, 11, 9)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(raise_route, "_today", lambda: TODAY)
    with TestClient(app) as c:
        yield c


def _tts_log(ogg, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


def make_home(worker="Lakshmi", worker_lang="te-IN", employer="Mehta madam", employer_lang="hi-en", wage=2500,
              hours=2, days=6, work_type="housekeeping") -> dict:
    with db.session() as s:
        w = Worker(name=worker, language=worker_lang, upi_vpa="lakshmi.demo@upi")
        e = Employer(name=employer, language=employer_lang)
        s.add(w)
        s.add(e)
        s.commit()
        c = Case(worker_id=w.id, employer_id=e.id, monthly_wage=wage, hours_per_day=hours, days_per_week=days,
                 work_type=work_type, status="draft")
        s.add(c)
        s.commit()
        return {"worker_id": w.id, "employer_id": e.id, "case_id": c.id}


# --------------------------------------------------------------------------- the maths
def test_estimate_and_yearly_gain_mehta():
    e = raise_core.estimate("housekeeping", 2, 6, 2500, TODAY)
    assert e["legal_estimate"] == 4000 and e["target"] == 4000 and e["is_estimate"]
    assert e["gap_monthly"] == 1500 and e["gap_yearly"] == 18000
    assert e["per_day"] == 58                      # 1,500 / 26 working days, rounded up
    assert raise_core.yearly_gain(2500, 4000) == 18000


def test_estimate_cook_three_hours_and_fair_home():
    e = raise_core.estimate("cooking", 3, 6, 5000, TODAY)
    assert e["legal_estimate"] == 6937.5 and e["target"] == 6938 and e["gap_monthly"] == 1938
    fair = raise_core.estimate("housekeeping", 2, 6, 5000, TODAY)
    assert fair["gap_monthly"] == 0 and fair["gap_yearly"] == 0 and fair["per_day"] == 0


def test_step_split():
    assert raise_core.step_split(2500, 4000) == 3200
    assert raise_core.step_split(3000, 4000) == 3500
    assert raise_core.step_split(3900, 4000) is None          # too small to split
    n = raise_core.plan_numbers("step", 2500, 4000, TODAY)
    assert (n["step1"], n["ask"], n["months"]) == (3200, 4000, 6)
    assert n["start"] == "2026-12-01" and n["step_date"] == "2027-06-01"
    custom = raise_core.plan_numbers("step", 2500, 4000, TODAY, step1=3000, months=3)
    assert custom["step1"] == 3000 and custom["step_month"] == "2027-03"
    with pytest.raises(ValueError):
        raise_core.plan_numbers("step", 2500, 4000, TODAY, step1=4500)
    with pytest.raises(ValueError):
        raise_core.plan_numbers("full", 2500, 4000, TODAY, ask=2000)


# --------------------------------------------------------------------------- the message
@pytest.mark.parametrize("lang", ["hi-en", "te-IN", "en"])
def test_law_mention_off_by_default_and_amounts_verified(lang):
    import asyncio

    n = raise_core.plan_numbers("step", 2500, 4000, TODAY)
    m = asyncio.run(raise_core.compose(lang=lang, worker="Lakshmi", employer="Mehta madam", current=2500, legal=4000,
                                       nums=n, years=4, use_llm=False))
    assert m["mention_law"] is False and m["checks"]["ok"]
    assert raise_core.law_terms(m["text"]) == [] and raise_core.law_terms(" ".join(m["speech"])) == []
    assert sorted(set(amounts_in(m["text"], lang))) == [2500, 3200, 4000]
    assert m["speech"][0] == m["disclosure"] and "AI" in m["speech"][0]
    assert "₹" not in " ".join(m["speech"])            # amounts are spoken as words
    on = asyncio.run(raise_core.compose(lang=lang, worker="Lakshmi", employer="Mehta madam", current=2500, legal=4000,
                                        nums=n, mention_law=True, use_llm=False))
    assert on["checks"]["ok"] and raise_core.law_terms(on["text"])
    assert len([s for s in on["sentences"] if raise_core.law_terms(s)]) == 1     # exactly one gentle line


def test_llm_reword_with_wrong_amount_falls_back(monkeypatch):
    import asyncio

    monkeypatch.setattr(config, "groq_key", lambda: "gk")
    calls = []

    async def fake(system, user, schema, *, name="result", validate=None, **kw):
        calls.append(system)
        out = {"sentences": ["नमस्ते {employer}, मैं {worker}।", "मेरी salary {current} है।",
                             "{start} से {step1}, फिर {step_month} से {ask} कर दीजिए।", "धन्यवाद।"]}
        return validate(out) if validate else out

    monkeypatch.setattr(llm, "json_call", fake)
    n = raise_core.plan_numbers("step", 2500, 4000, TODAY)
    m = asyncio.run(raise_core.compose(lang="hi-en", worker="Lakshmi", employer="Mehta madam", current=2500,
                                       legal=4000, nums=n, use_llm=True))
    assert m["source"] == "llm" and "Never mention the law" in calls[0]
    # an LLM that writes the law or a digit is rejected by the validator
    v = raise_core.llm_validator({"employer", "ask", "start"}, {"employer", "ask", "start"}, mention_law=False)
    with pytest.raises(ValueError):
        v({"sentences": ["{employer}, न्यूनतम वेतन {ask} है।", "{start} से।"]})
    with pytest.raises(ValueError):
        v({"sentences": ["{employer}, 5000 दीजिए {ask}।", "{start} से।"]})


def test_personal_line_with_foreign_amount_is_dropped():
    import asyncio

    n = raise_core.plan_numbers("full", 2500, 4000, TODAY)
    m = asyncio.run(raise_core.compose(lang="en", worker="Lakshmi", employer="Mehta madam", current=2500, legal=4000,
                                       nums=n, use_llm=False,
                                       personal={"display": "Others get ₹9,000 for this.", "speech": None}))
    assert m["personal"]["included"] is False and "9,000" not in m["text"]
    ok = asyncio.run(raise_core.compose(lang="en", worker="Lakshmi", employer="Mehta madam", current=2500, legal=4000,
                                        nums=n, use_llm=False,
                                        personal={"display": "My son's school fees went up.", "speech": None}))
    assert ok["personal"]["included"] and "school fees" in ok["text"]


# --------------------------------------------------------------------------- API: worker side
def test_case_view_and_compose_default_step(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, seen)
    ids = make_home()
    v = client.get(f"/api/raise/case/{ids['case_id']}").json()
    assert v["numbers"]["gap_yearly"] == 18000 and v["numbers"]["legal_estimate"] == 4000
    assert v["plans"]["step"]["step1"] == 3200 and v["plans"]["full"]["ask"] == 4000 and v["raise"] is None
    r = client.post(f"/api/raise/case/{ids['case_id']}/compose", json={"years_worked": 4, "use_llm": False})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "draft" and b["mention_law"] is False and b["plan"] == "step"
    assert b["message"]["lang"] == "hi-en" and "मेहता मैडम" in b["message"]["text"]
    assert "₹3,200" in b["message"]["text"] and "₹4,000" in b["message"]["text"] and "4 साल" in b["message"]["text"]
    assert raise_core.law_terms(b["message"]["text"]) == []
    assert "మెహతా మేడమ్" in b["message"]["text_worker_lang"]      # her own copy, in Telugu
    assert b["audio_url"] and b["employer_path"].startswith("/raise/e/") and b["share_text"].endswith(b["employer_url"])
    assert len(seen) == 2 and seen[0]["text"].startswith("यह एक AI")   # disclosure first, then one body clip
    assert all(t["language"] == "hi-en" for t in seen)
    case_token = None
    with db.session() as s:
        case_token = s.get(Case, ids["case_id"]).employer_token
    assert case_token not in b["employer_path"]                         # a separate token
    assert client.post(f"/api/raise/case/{ids['case_id']}/sent").json()["status"] == "sent"


def test_compose_without_gnani_still_works(client):
    ids = make_home()
    b = client.post(f"/api/raise/case/{ids['case_id']}/compose", json={"plan": "full", "use_llm": False}).json()
    assert b["audio_url"] is None and b["audio_error"] and b["message"]["text"]


def test_compose_with_personal_line_same_language(client):
    ids = make_home(worker="Rafiq", worker_lang="hi-en", employer="Rao garu", employer_lang="hi-en",
                    wage=5000, hours=3, work_type="cooking")
    b = client.post(f"/api/raise/case/{ids['case_id']}/compose",
                    json={"plan": "full", "use_llm": False, "audio": False,
                          "personal_text": "Ghar ka kiraya badh gaya hai."}).json()
    assert "Ghar ka kiraya badh gaya hai." in b["message"]["text"] and b["message"]["personal"]["included"]
    assert b["ask_amount"] == 6938


def test_fair_home_cannot_compose(client):
    ids = make_home(wage=5000)
    r = client.post(f"/api/raise/case/{ids['case_id']}/compose", json={"use_llm": False, "audio": False})
    assert r.status_code == 409


# --------------------------------------------------------------------------- API: employer side + transitions
def _composed(client, plan="step", **kw):
    ids = make_home(**kw)
    b = client.post(f"/api/raise/case/{ids['case_id']}/compose", json={"plan": plan, "use_llm": False,
                                                                       "audio": False, "years_worked": 4}).json()
    return ids, b["employer_path"].rsplit("/", 1)[1]


def test_employer_view_why_without_law(client):
    ids, token = _composed(client)
    e = client.get(f"/api/raise/e/{token}").json()
    assert e["employer"]["language"] == "hi-en" and e["can_answer"]
    assert e["why"]["per_day"] == 58 and e["why"]["legal_estimate"] is None and e["why"]["fair_pay_link"] == "/check"
    assert e["why"]["per_day_step1"] == 27                  # 700 / 26 = 26.9, rounded up
    assert e["step_offer"] is None                          # she already asked for a step-up
    assert client.post(f"/api/raise/e/{token}/played").json()["status"] == "played"
    assert client.get("/api/raise/e/nope").status_code == 404


def test_employer_view_with_law_shows_estimate(client):
    ids = make_home()
    b = client.post(f"/api/raise/case/{ids['case_id']}/compose",
                    json={"plan": "full", "mention_law": True, "use_llm": False, "audio": False}).json()
    token = b["employer_path"].rsplit("/", 1)[1]
    e = client.get(f"/api/raise/e/{token}").json()
    assert e["why"]["legal_estimate"] == 4000 and "₹4,000" in e["why"]["legal_text"] and e["why"]["fair_pay_link"] is None
    assert e["step_offer"]["step1"] == 3200


def test_accept_celebrates_in_worker_language_with_pdf_and_ics(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, seen)
    ids, token = _composed(client, plan="full")
    r = client.post(f"/api/raise/e/{token}/accept", json={})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "accepted" and b["answer"]["new_wage"] == 4000 and b["answer"]["new_wage_from"] == "2026-12-01"
    assert b["answer"]["yearly_gain"] == 18000
    cel = b["celebration"]
    assert cel["title"] == "జీతం పెంచారు!" and cel["title_latin"] == "Jeetham penchaaru!"
    assert "₹4,000" in cel["text"] and cel["audio_url"]
    assert seen[-1]["language"] == "te-IN" and seen[-1]["text"].startswith("<excited>")
    assert "నాలుగు వేల" in seen[-1]["text"]
    pdf = client.get(b["agreement_url"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    ics = client.get(b["ics_url"])
    assert ics.status_code == 200 and "BEGIN:VCALENDAR" in ics.text and "Rs 4\\,000" in ics.text
    assert "DTSTART;VALUE=DATE:20270101" in ics.text
    # the worker's screen sees it
    v = client.get(f"/api/raise/case/{ids['case_id']}").json()["raise"]
    assert v["status"] == "accepted" and v["celebration"]["title"] == "జీతం పెంచారు!"
    assert client.post(f"/api/raise/e/{token}/accept", json={}).status_code == 409
    assert client.post(f"/api/raise/case/{ids['case_id']}/compose", json={"audio": False}).status_code == 409


def test_step_up_from_a_full_request(client):
    ids, token = _composed(client, plan="full", worker_lang="hi-en", worker="Rafiq", employer="Rao garu",
                           employer_lang="te-IN")
    b = client.post(f"/api/raise/e/{token}/step-up").json()
    assert b["status"] == "stepped" and b["answer"]["new_wage"] == 3200 and b["answer"]["step_up_to"] == 4000
    assert b["answer"]["step_up_from"] == "2027-06-01"
    assert b["celebration"]["title"] == "Salary बढ़ गई!" and b["celebration"]["title_latin"] == "Salary badh gayi!"
    assert b["celebration"]["audio_url"] is None and b["celebration"]["audio_error"]    # no Gnani: still celebrates
    ics = client.get(b["ics_url"]).text
    assert ics.count("BEGIN:VEVENT") == 2 and "UNTIL=20270630" in ics


def test_talk_text_and_voice(client, mock_gnani, short_ogg, short_wav):
    stt_seen = []

    def stt(request):
        stt_seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": "Theek hai, Sunday ko baat karte hain.",
                                         "detected_language_code": "hi-IN"})

    mock_gnani.push("/stt/v3", stt)
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids, token = _composed(client)
    r = client.post(f"/api/raise/e/{token}/talk", files={"audio": ("talk.wav", short_wav, "audio/wav")},
                    data={"use_llm": "false"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "talk" and b["transcript"].startswith("Theek hai")
    assert stt_seen[0]["language_code"] == "hi-IN,en-IN" and stt_seen[0]["format"] == "codemix"
    assert b["translation"]["language"] == "te-IN" and b["audio_url"] and b["original_audio_url"]
    t2 = client.post(f"/api/raise/e/{token}/talk", data={"text": "Kal baat karte hain", "use_llm": "false"}).json()
    assert t2["transcript"] == "Kal baat karte hain"
    page = client.get(f"/api/raise/e/{token}").json()
    assert len(page["replies"]) == 2 and page["can_answer"]
    # talking is not a no: she can still be accepted afterwards
    assert client.post(f"/api/raise/e/{token}/accept", json={"alert_audio": False}).json()["status"] == "accepted"


# --------------------------------------------------------------------------- agreement PDF scripts
@pytest.mark.parametrize("wl,el", [("te-IN", "hi-en"), ("hi-en", "te-IN"), ("en", "en")])
def test_agreement_pdf_renders_scripts(wl, el):
    from fpdf import FPDF  # noqa: F401  (fpdf2 present)

    n = raise_core.plan_numbers("step", 2500, 4000, TODAY)
    blocks = raise_core.agreement_blocks(worker="Lakshmi", employer="Mehta madam", worker_lang=wl, employer_lang=el,
                                         work_type="maid", hours=2, days=6, current=2500, nums=n, choice="step",
                                         today=TODAY)
    text = " ".join(b.text for b in blocks)
    assert "₹3,200" in text and "₹4,000" in text and "₹2,500" in text
    if "te-IN" in (wl, el):
        assert "జీతం ఒప్పందం" in text and "లక్ష్మి" in text
    if "hi-en" in (wl, el):
        assert "वेतन समझौता" in text and "मेहता मैडम" in text
    pdf = raise_core.agreement_pdf(worker="Lakshmi", employer="Mehta madam", worker_lang=wl, employer_lang=el,
                                   work_type="maid", hours=2, days=6, current=2500, nums=n, choice="step", today=TODAY)
    assert pdf[:4] == b"%PDF" and len(pdf) > 2000
    if wl == "te-IN":
        assert b"NotoSansTelugu" in pdf and b"NotoSansDevanagari" in pdf


# --------------------------------------------------------------------------- summary + demo
def test_summary_endpoint(client):
    with db.session() as s:
        w = Worker(name="Lakshmi", language="te-IN")
        s.add(w)
        s.commit()
        homes = []
        for name, wage in (("Sharma ji", 4000), ("Reddy garu", 5000), ("Mehta madam", 2500)):
            e = Employer(name=name, language="hi-en")
            s.add(e)
            s.commit()
            c = Case(worker_id=w.id, employer_id=e.id, monthly_wage=wage, hours_per_day=2, days_per_week=6,
                     work_type="housekeeping")
            s.add(c)
            s.commit()
            homes.append(c.id)
        wid = w.id
    r = client.get(f"/api/raise/summary?worker_id={wid}").json()
    assert [h["status"] for h in r["per_home"]] == ["fair", "fair", "none"]
    assert r["total_yearly_gain_possible"] == 18000 and r["total_yearly_gain_won"] == 0
    assert r["best_case_id"] == homes[2] and r["best_url"] == f"/raise/{homes[2]}"
    mehta = r["per_home"][2]
    assert (mehta["current"], mehta["legal_estimate"], mehta["gap_monthly"], mehta["gap_yearly"]) == (2500, 4000, 1500, 18000)
    b = client.post(f"/api/raise/case/{homes[2]}/compose", json={"plan": "full", "use_llm": False, "audio": False}).json()
    client.post(f"/api/raise/e/{b['employer_path'].rsplit('/', 1)[1]}/accept", json={"alert_audio": False})
    r2 = client.get(f"/api/raise/summary?worker_id={wid}").json()
    assert r2["total_yearly_gain_won"] == 18000 and r2["total_yearly_gain_possible"] == 0
    assert r2["per_home"][2]["status"] == "accepted" and r2["best_case_id"] is None
    assert client.get("/api/raise/summary?worker_id=999").status_code == 404


def test_demo_prepares_mehta_home(client):
    from app import seed

    seed.reset()
    r = client.post("/api/raise/demo", json={"audio": False})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["worker_path"] == f"/raise/{b['case_id']}" and b["employer_path"] == f"/raise/e/{b['token']}"
    v = b["raise"]
    assert (v["current"], v["ask_amount"], v["step1_amount"]) == (2500, 4000, 3200)
    assert v["years_worked"] == 4 and v["mention_law"] is False and v["demo"]
    # running it again replaces the old request (fresh token), and a reset invalidates old links
    b2 = client.post("/api/raise/demo", json={"audio": False}).json()
    assert b2["token"] != b["token"] and client.get(f"/api/raise/e/{b['token']}").status_code == 404
    seed.reset()
    assert client.get(f"/api/raise/e/{b2['token']}").status_code == 404
