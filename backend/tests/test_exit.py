"""Exit Kit (W03 lite): due date, part-month, earlier dues, never-claim rules, checklist audio. Offline."""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import exit_kit as ek
from app import tts_cache, wages
from app.main import app
from app.routes import exit as exit_route

from .b_data import tts_ok

TODAY = dt.date(2026, 11, 9)  # a Monday (the demo's "today")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setattr(exit_route, "today_ist", lambda: TODAY)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo(client):
    r = client.post("/api/demo/reset")
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- due date
def test_due_date_skips_sunday_across_weekend():
    assert dt.date(2026, 11, 13).weekday() == 4  # Friday
    assert ek.due_by(dt.date(2026, 11, 13)) == dt.date(2026, 11, 16)  # Sat, (Sun skipped), Mon
    assert ek.due_by(dt.date(2026, 11, 14)) == dt.date(2026, 11, 17)  # Sat -> Mon, Tue
    assert ek.due_by(dt.date(2026, 11, 9)) == dt.date(2026, 11, 11)   # Mon -> Wed
    assert ek.due_by(dt.date(2026, 11, 15)) == dt.date(2026, 11, 17)  # last day a Sunday -> Mon, Tue


def test_due_is_a_date_not_a_countdown(client, demo):
    r = client.post("/api/exit", json={"worker_id": demo["workers"]["lakshmi"], "employer_id": demo["employers"]["sharma"],
                                       "last_day": "2026-11-13", "days_worked_this_month": 10}).json()
    assert r["due_by"] == "2026-11-16" and r["due_weekday"] == "Monday"
    assert "holidays are not skipped" in r["basis"]["due_note"]
    blob = json.dumps(r).lower()
    assert "hours_left" not in blob and "countdown" not in blob and "48 hours" not in blob


# --------------------------------------------------------------------------- part-month
def test_part_month_pro_rata_26_days_rounded_down():
    amt, div, basis = ek.part_month_pay(4000, 10)
    assert (amt, div) == (1538.0, 26.0)  # 4000 / 26 x 10 = 1538.46 -> 1538 (never overstated)
    assert "/ 26 x 10 days" in basis
    assert ek.part_month_pay(9000, 12)[0] == 4153.0
    assert ek.part_month_pay(4000, 26)[0] == 4000.0
    assert ek.part_month_pay(4000, 30)[0] == 4000.0      # capped at one month's wage
    assert ek.part_month_pay(5000, 0)[0] == 0.0


def test_part_month_fewer_days_a_week_uses_wages_divisor():
    amt, div, _ = ek.part_month_pay(3000, 10, days_per_week=3)
    assert div == wages.days_per_month(3) == 13.0
    assert amt == 2307.0  # 3000 / 13 x 10 = 2307.69


def test_days_worked_sources():
    last = dt.date(2026, 11, 13)
    assert ek.days_worked_this_month(last, given=7) == (7.0, "you said", False)
    diary = ["2026-11-02T04:30:00Z", "2026-11-03T04:30:00Z", "2026-11-03T09:00:00Z", "2026-10-31T04:30:00Z",
             "2026-11-20T04:30:00Z"]
    assert ek.days_worked_this_month(last, checkin_dates=diary) == (2.0, "diary check-ins", False)
    # 1-13 Nov 2026: Sundays on the 1st and 8th -> 11 working days, labelled an estimate
    assert ek.days_worked_this_month(last) == (11.0, "calendar count", True)
    assert ek.days_worked_this_month(last, start_date="2026-11-10") == (4.0, "calendar count", True)


# --------------------------------------------------------------------------- combined with the case
def test_exit_combines_part_month_with_unpaid_months(client, demo):
    w, sharma = demo["workers"]["lakshmi"], demo["employers"]["sharma"]
    r = client.post("/api/exit", json={"worker_id": w, "employer_id": sharma, "last_day": "2026-11-13",
                                       "days_worked_this_month": 10})
    assert r.status_code == 200, r.text
    r = r.json()
    part = [i for i in r["items"] if i["kind"] == "final_settlement"]
    assert len(part) == 1 and part[0]["amount"] == 1538 and part[0]["month"] == "2026-11"
    unpaid = sorted(i["month"] for i in r["items"] if i["kind"] == "unpaid_wage")
    assert unpaid == ["2026-08", "2026-09", "2026-10"]
    assert r["total"] == 12692 + 1538 == sum(i["amount"] for i in r["items"] if i["included_in_total"])
    assert r["case_id"] == demo["cases"]["sharma"] and r["polite"]["mode"] == "update_case"
    # earlier months are now due by the settlement date too (s.17(2) only ever makes a date earlier)
    assert all(i["due_date"] <= "2026-11-16" for i in r["items"] if i["kind"] == "unpaid_wage")
    # GET returns the same thing
    again = client.get(f"/api/exit/{r['id']}").json()
    assert again["total"] == r["total"] and again["due_by"] == r["due_by"]


def test_polite_plan_goes_through_existing_endpoints_and_is_idempotent(client, demo):
    w, sharma, cid = demo["workers"]["lakshmi"], demo["employers"]["sharma"], demo["cases"]["sharma"]
    body = {"worker_id": w, "case_id": cid, "last_day": "2026-11-13", "days_worked_this_month": 10}
    r = client.post("/api/exit", json=body).json()
    c = client.post(f"/api/cases/{cid}/confirm", json=r["polite"]["confirm"])
    assert c.status_code == 200, c.text
    case = c.json()
    assert case["total_due"] == 14230 and case["dismissed"] is True and case["end_date"] == "2026-11-13"
    # run the kit again (she corrects the days): the old exit amount is replaced, never added twice
    r2 = client.post("/api/exit", json={**body, "days_worked_this_month": 12}).json()
    assert r2["total"] == 12692 + 1846  # 4000 / 26 x 12 = 1846.15
    case2 = client.post(f"/api/cases/{cid}/confirm", json=r2["polite"]["confirm"]).json()
    assert case2["total_due"] == r2["total"]
    assert case2["facts"]["unpaid_months"] == ["2026-08", "2026-09", "2026-10"]
    # the normal Polite step (existing endpoint, no new ladder step) asks for the new balance
    m = client.post(f"/api/cases/{cid}/messages/polite", json={"use_llm": False, "audio": False, "pdf": False})
    assert m.status_code == 200, m.text
    assert m.json()["step"] == "polite" and m.json()["balance"] == r2["total"]


def test_months_unpaid_without_list_does_not_slide_onto_exit_month(client, demo):
    w = demo["workers"]["lakshmi"]
    created = client.post("/api/cases", json={"worker_id": w, "employer": {"name": "Gupta ji"}, "use_llm": False,
                                              "facts": {"monthly_wage": 6000, "hours_per_day": 3, "months_unpaid": 2,
                                                        "last_unpaid_month": "2026-10"}}).json()
    r = client.post("/api/exit", json={"worker_id": w, "case_id": created["id"], "last_day": "2026-11-06",
                                       "days_worked_this_month": 5}).json()
    assert sorted(i["month"] for i in r["items"] if i["kind"] == "unpaid_wage") == ["2026-09", "2026-10"]
    assert r["total"] == 12000 + 1153  # 6000 / 26 x 5 = 1153.8
    case = client.post(f"/api/cases/{created['id']}/confirm", json=r["polite"]["confirm"]).json()
    assert case["total_due"] == r["total"]


def test_month_already_counted_in_full_is_not_added_again(client, demo):
    w, rao_case = demo["workers"]["rafiq"], demo["cases"]["rao"]
    r = client.post("/api/exit", json={"worker_id": w, "case_id": rao_case, "last_day": "2026-10-31"}).json()
    assert not [i for i in r["items"] if i["kind"] == "final_settlement"]
    assert r["total"] == 14000 and r["notes"]
    assert r["due_by"] == "2026-11-03"  # Sat 31 Oct -> Mon 2, Tue 3 Nov


def test_shortfall_estimate_is_labelled_and_not_in_total(client, demo):
    w, mehta = demo["workers"]["lakshmi"], demo["employers"]["mehta"]
    r = client.post("/api/exit", json={"worker_id": w, "employer_id": mehta, "last_day": "2026-11-13",
                                       "days_worked_this_month": 10}).json()
    sf = [i for i in r["items"] if i["kind"] == "min_wage_shortfall" and i["month"] == "2026-11"]
    assert len(sf) == 1 and sf[0]["is_estimate"] and not sf[0]["included_in_total"]
    assert sf[0]["amount"] == 1538 - 961  # minimum 4000/26x10 vs agreed 2500/26x10
    assert r["total"] == 961 and r["is_estimate_flags"]["min_wage_shortfall"] is True
    assert r["shortfall_estimate_not_in_total"] >= sf[0]["amount"]


def test_no_case_creates_one_through_existing_post_cases(client, demo):
    w = demo["workers"]["lakshmi"]
    emp = client.post("/api/cases", json={"worker_id": w, "employer": {"name": "Temp"}, "use_llm": False,
                                          "facts": {"monthly_wage": 1}}).json()["employer"]["id"]
    # Rafiq has no case with this employer: the plan is a new case through the existing POST /api/cases
    r = client.post("/api/exit", json={"worker_id": demo["workers"]["rafiq"], "employer_id": emp,
                                       "last_day": "2026-11-13", "days_worked_this_month": 10, "monthly_wage": 5200})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["case_id"] is None and r["total"] == 2000 and r["polite"]["mode"] == "new_case"
    made = client.post("/api/cases", json=r["polite"]["create"])
    assert made.status_code == 200, made.text
    assert made.json()["total_due"] == 2000 and made.json()["end_date"] == "2026-11-13"


def test_needs_wage_and_employer(client, demo):
    w = demo["workers"]["lakshmi"]
    assert client.post("/api/exit", json={"worker_id": w}).status_code == 422
    assert client.post("/api/exit", json={"worker_id": 999, "employer_id": 1}).status_code == 404


# --------------------------------------------------------------------------- never-claim rules
def test_never_claims_notice_pay_gratuity_bonus(client, demo):
    w, sharma = demo["workers"]["lakshmi"], demo["employers"]["sharma"]
    r = client.post("/api/exit", json={"worker_id": w, "employer_id": sharma, "last_day": "2026-11-13",
                                       "days_worked_this_month": 10, "notice_pay": 4000, "gratuity": 9000,
                                       "bonus": 1000}).json()
    assert r["total"] == 12692 + 1538  # extra fields are ignored
    assert ek.find_never_claims(r) == []
    assert {i["kind"] for i in r["items"]} <= ek.ALLOWED_KINDS
    for i in r["items"]:
        assert not any(word in i["label"].lower() for word in ("notice", "gratuity", "bonus", "compensation"))
    assert "does not add notice pay, gratuity" in r["basis"]["not_claimed"]
    assert r["disclaimer"] == wages.DISCLAIMER


def test_find_never_claims_catches_a_bad_item():
    assert ek.find_never_claims({"items": [{"kind": "notice_pay", "label": "Notice pay"}]})
    assert ek.find_never_claims({"items": [{"kind": "unpaid_wage", "label": "Gratuity"}]})


def test_checklist_is_calm():
    for lang, texts in ek.CHECKLIST.items():
        assert len(texts) == 4
    for t in ek.CHECKLIST["en-IN"]:
        low = t.lower()
        assert not any(w in low for w in ("demand", "police", "threat", "must", "fight", "refuse"))


# --------------------------------------------------------------------------- last day from her words
def test_last_day_from_speech():
    assert exit_route.last_day_from("repu nunchi raavaddu annaru", "te-IN", TODAY) == (TODAY, "from_tomorrow")
    assert exit_route.last_day_from("Madam ne bola kal se mat aana", "hi-en", TODAY) == (TODAY, "from_tomorrow")
    assert exit_route.last_day_from("", "te-IN", TODAY) == (TODAY, "today")


def test_transcript_sets_last_day_and_runs_safety(client, demo):
    r = client.post("/api/exit", json={"worker_id": demo["workers"]["lakshmi"], "employer_id": demo["employers"]["sharma"],
                                       "transcript": "Madam ne bola kal se mat aana", "days_worked_this_month": 6}).json()
    assert r["last_day"] == TODAY.isoformat() and r["last_day_how"] == "from_tomorrow"
    assert r["due_by"] == "2026-11-11" and r["safety"] is not None


# --------------------------------------------------------------------------- checklist audio
def test_checklist_without_cache_is_text_only_and_spends_nothing(client, demo):
    before = tts_cache.SYNTH_CALLS["count"]
    r = client.post("/api/exit", json={"worker_id": demo["workers"]["lakshmi"], "employer_id": demo["employers"]["sharma"],
                                       "last_day": "2026-11-13", "days_worked_this_month": 10}).json()
    assert [c["id"] for c in r["checklist"]] == list(ek.CHECKLIST_IDS)
    assert all(c["audio_url"] is None and c["text"] for c in r["checklist"])
    assert r["checklist_audio"] == "text_only" and r["checklist"][0]["lang"] == "te-IN"
    assert tts_cache.SYNTH_CALLS["count"] == before


def test_checklist_audio_falls_back_to_text_when_tts_fails(client, mock_gnani):
    mock_gnani.default["/api/v1/tts/inference"] = httpx.Response(500, json={"detail": "boom"})
    r = client.post("/api/exit/checklist", json={"lang": "te"})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["fallback"] == "text" and r["tts_calls"] == 0
    assert all(c["audio_url"] is None and c["tts_error"] and c["text"] for c in r["checklist"])


def test_checklist_audio_cached_once(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    r = client.post("/api/exit/checklist", json={"lang": "te-IN"}).json()
    assert r["tts_calls"] == 4 and r["fallback"] is None
    url = r["checklist"][0]["audio_url"]
    assert url.startswith("/api/exit/audio/") and client.get(url).status_code == 200
    again = client.post("/api/exit/checklist", json={"lang": "te-IN"}).json()
    assert again["tts_calls"] == 0  # every clip from the cache
    cached = client.get("/api/exit/checklist?lang=te-IN").json()
    assert all(c["audio_url"] for c in cached["checklist"])
    sent = [json.loads(req.content) for req in mock_gnani.requests]
    assert len(sent) == 4 and all(s["text"].startswith("<slow>") and s["language"] == "te-IN" for s in sent)
    assert "యూపీఐ" in sent[3]["text"]  # spelt out for Telugu speech
    assert client.get("/api/exit/audio/" + "0" * 64 + ".ogg").status_code == 404
