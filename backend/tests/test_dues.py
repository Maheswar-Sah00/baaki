"""Baaki for every promise (/api/dues). Offline: Gnani STT/TTS mocked; no LLM is used anywhere in this feature."""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import dues_core
from app.dues_core import (PACK_MIN_BROKEN, bad_words, counter, log_hash, pack_eligible, parse_items, parse_promise,
                           promise_status, reminder, verify_log)
from app.main import app
from app.messages import amounts_in
from app.routes import dues as dues_route

from .conftest import multipart_fields

TODAY = dt.date(2026, 11, 9)   # a Monday


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(dues_route, "_today", lambda: TODAY)
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- totals from speech-like text
def test_total_from_telugu_text():
    r = parse_items("అక్టోబర్ పాలు 1,850 రూపాయలు, పేపర్ 320", "auto")
    assert r["lang"] == "te-IN"
    assert [i["amount"] for i in r["items"]] == [1850, 320]
    assert r["total"] == 2170 and r["total_display"] == "₹2,170"
    assert r["items"][0]["item_key"] == "milk" and r["items"][0]["month"] == 10
    assert r["items"][1]["item_key"] == "paper" and r["items"][1]["month"] == 10     # the month carries forward
    assert r["items"][0]["display"]["hi-en"] == "अक्टूबर का दूध"


def test_total_from_hinglish_words():
    r = parse_items("Reddy garu ka October ka doodh atharah sau pachaas rupaye aur paper teen sau bees", "auto",
                    party="Reddy garu")
    assert r["lang"] == "hi-en"
    assert [i["amount"] for i in r["items"]] == [1850, 320]
    assert r["total"] == 2170
    assert "Reddy" not in r["items"][0]["label"]


# --------------------------------------------------------------------------- promise dates (relative to the day said)
@pytest.mark.parametrize("words,lang,due,precision", [
    ("agle mahine pehle hafte mein de dunga", "hinglish", "2026-12-07", "week"),
    ("first week mein de dunga", "hinglish", "2026-12-07", "week"),         # said on the 9th: next month's first week
    ("ఈ వారం చివరికి ఇస్తాను", "te", "2026-11-15", "week"),
    ("ee vaaram chivariki istanu", "auto", "2026-11-15", "week"),
    ("by the end of this week", "en", "2026-11-15", "week"),
    ("1 tareekh ko pakka", "hinglish", "2026-12-01", "day"),
])
def test_parse_promise_dates(words, lang, due, precision):
    p = parse_promise(words, lang, TODAY)
    assert p and p["due_date"] == due and p["precision"] == precision and p["quote"] == words


def test_first_week_said_early_in_month_is_this_month():
    p = parse_promise("first week mein de dunga", "hinglish", dt.date(2026, 11, 3))
    assert p["due_date"] == "2026-11-07"


def test_promise_amount_from_parser():
    p = parse_promise("ఈ వారం చివరికి మొత్తం నలభై వేలు ఇస్తాను", "te", TODAY)
    assert p["amount"] == 40000


def test_no_date_no_promise():
    assert parse_promise("paise de dunga", "hinglish", TODAY) is None


# --------------------------------------------------------------------------- status and counting with as_of
def _p(said, due, status="pending", amount=None):
    return {"said_on": said, "due_date": due, "status": status, "amount": amount}


def test_status_broken_kept_pending():
    items = [{"kind": "due", "amount": 1850, "said_on": "2026-10-31"}]
    p = _p("2026-10-31", "2026-11-07")
    assert promise_status(p, dt.date(2026, 11, 7), items) == "pending"      # the due day itself is still fine
    assert promise_status(p, dt.date(2026, 11, 8), items) == "broken"
    paid = items + [{"kind": "paid", "amount": 1850, "said_on": "2026-11-05"}]
    assert promise_status(p, dt.date(2026, 11, 20), paid) == "kept"
    late = items + [{"kind": "paid", "amount": 1850, "said_on": "2026-11-12"}]
    assert promise_status(p, dt.date(2026, 11, 20), late) == "broken"      # paid, but after the promised date
    assert promise_status({**p, "status": "kept"}, dt.date(2026, 12, 1), items) == "kept"


def test_counter_text_and_as_of():
    ps = [{**_p("2026-07-10", "2026-07-12"), "status": "broken"}, {**_p("2026-08-01", "2026-08-02"), "status": "broken"},
          {**_p("2026-11-01", "2026-11-14"), "status": "pending"}, {**_p("2026-12-01", "2026-12-07"), "status": "pending"}]
    c = counter(ps, TODAY)
    assert (c["made"], c["broken"], c["pending"]) == (3, 2, 1)      # the December entry is after as_of
    assert c["first_promised"] == "2026-07-10" and c["months_ago"] == 3
    assert c["text_en"] == "Promise made 3 times, broken 2 times, first promised 10 July 2026 (3 months ago)"


def test_demo_counts_with_time_travel(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    chit = client.get(f"/api/dues/{ids['chit']}").json()
    assert chit["counter"]["made"] == 6 and chit["counter"]["broken"] == 6
    assert chit["counter"]["months_ago"] == 4
    assert chit["balance"] == 40000 and chit["pack"]["eligible"] is True
    assert all(p["status"] == "broken" for p in chit["promises"])
    # every chit promise was resolved from the day it was said: due within the same week
    for p in chit["promises"]:
        gap = (dt.date.fromisoformat(p["due_date"]) - dt.date.fromisoformat(p["said_on"])).days
        assert 0 <= gap <= 6 and p["precision"] == "week"
    # back in time: 70 days ago only 3 promises had been made
    early = client.get(f"/api/dues/{ids['chit']}", params={"as_of": (TODAY - dt.timedelta(days=70)).isoformat()}).json()
    assert early["counter"]["made"] == 3 and early["counter"]["broken"] == 3

    milk = client.get(f"/api/dues/{ids['milk']}").json()
    assert milk["balance"] == 1850 and milk["items"][0]["display"]["en"] == "October milk"
    assert milk["counter"]["made"] == 2 and milk["counter"]["broken"] == 1 and milk["counter"]["pending"] == 1
    assert [p["due_date"] for p in milk["promises"]] == ["2026-11-07", "2026-12-07"]
    assert milk["pack"]["applies"] is False and milk["pack"]["eligible"] is False
    assert milk["upi_url"] == "upi://pay?pa=demo.ramu@baaki&pn=Ramu&am=1850&cu=INR&tn=Baaki"
    # a month later the second "first week" has passed too
    later = client.get(f"/api/dues/{ids['milk']}", params={"as_of": "2026-12-08"}).json()
    assert later["counter"]["broken"] == 2

    lst = client.get("/api/dues").json()
    assert lst["total"] == 41850 and lst["promises_broken"] == 7
    assert lst["by_kind"]["chit"]["broken"] == 6 and lst["by_kind"]["vendor"]["balance"] == 1850
    # demo is idempotent
    client.post("/api/dues/demo")
    assert len(client.get("/api/dues").json()["accounts"]) == 2


# --------------------------------------------------------------------------- reminders: amounts re-verified, polite
def test_vendor_reminder_amounts_and_upi(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    r = client.post(f"/api/dues/{ids['milk']}/remind", json={}).json()
    assert r["language"] == "hi-en"
    assert r["text"].startswith("नमस्ते रेड्डी गारु, रामू की तरफ़ से")
    assert "अक्टूबर के दूध का bill ₹1,850 बाकी है" in r["text"]
    assert r["checks"]["amounts_ok"] and r["checks"]["amounts_expected"] == [1850]
    assert r["checks"]["no_accusation"]
    assert r["upi_url"].startswith("upi://pay?pa=demo.ramu@baaki") and r["upi_url"] in r["share_text"]
    assert r["whatsapp_url"].startswith("https://wa.me/?text=")
    te = client.post(f"/api/dues/{ids['milk']}/remind", json={"lang": "te"}).json()
    assert "అక్టోబర్ పాలు బిల్లు ₹1,850" in te["text"] and te["checks"]["amounts_ok"]


def test_chit_reminder_quotes_their_last_promise(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    r = client.post(f"/api/dues/{ids['chit']}/remind", json={}).json()
    assert r["language"] == "te-IN"
    assert "“ఈ వారం చివరికి ఇచ్చేస్తాను”" in r["text"]
    assert "₹40,000" in r["text"] and r["checks"]["amounts_ok"]
    assert r["upi_url"] is None and r["quoted_promise"]
    assert not bad_words(r["text"]) and not bad_words(r["text_owner_lang"])


@pytest.mark.parametrize("lang", ["hi-en", "te-IN", "en"])
@pytest.mark.parametrize("kind", ["vendor", "chit", "other"])
def test_reminder_every_amount_verified_no_accusation(kind, lang):
    items = [{"kind": "due", "label": "October doodh", "item_key": "milk", "month": 10, "amount": 1850.0},
             {"kind": "due", "label": "paper", "item_key": "paper", "month": 10, "amount": 320.0}]
    lp = {"said_on": "2026-10-24", "quote": "ఈ వారం చివరికి మొత్తం నలభై వేలు ఇస్తాను", "lang": "te-IN"}
    r = reminder(kind=kind, party="Reddy garu", owner="Ramu", lang=lang, balance=2170, items=items, last_promise=lp)
    assert r["checks"]["amounts_ok"], r
    found = sorted(int(a) for a in amounts_in(r["text"], lang))
    assert 2170 in found
    for word in ("fraud", "police", "court", "interest", "penalt", "धोखा", "మోసం", "legal"):
        assert word not in r["text"].lower()
    assert r["checks"]["no_accusation"]


def test_reminder_falls_back_when_label_reads_as_a_number():
    # "do" (two) in a free-text label would add a stray figure: the item list is dropped, the total stays
    items = [{"kind": "due", "label": "do hazaar wala", "item_key": None, "month": None, "amount": 900.0},
             {"kind": "due", "label": "teen packet", "item_key": None, "month": None, "amount": 300.0}]
    r = reminder(kind="vendor", party="Reddy garu", owner="Ramu", lang="hi-en", balance=1200, items=items,
                 last_promise=None)
    assert r["checks"]["amounts_ok"] and r["checks"]["amounts_found"] == [1200]


def test_bad_words_catches_accusations():
    assert bad_words("you are a fraud") == ["fraud"]
    assert "మోసం" in bad_words("ఇది మోసం")
    assert bad_words("नमस्ते, एक छोटी सी याद।") == []


def test_reminder_voice_note_starts_with_disclosure(client, mock_gnani, short_ogg):
    seen = []

    def tts(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = tts
    ids = client.post("/api/dues/demo").json()["accounts"]
    r = client.post(f"/api/dues/{ids['chit']}/remind", json={"voice": True}).json()
    assert r["audio_error"] is None, r["audio_error"]
    assert r["audio"]["gnani_calls"] == 2        # disclosure + the whole reminder as one sentence
    assert r["audio_url"].startswith("/api/media/")
    assert r["audio"]["disclosure"].startswith("ఇది AI వాయిస్ సందేశం")
    texts = [json.dumps(x, ensure_ascii=False) for x in seen]
    assert "AI" in texts[0]          # first synthesised sentence is the disclosure


# --------------------------------------------------------------------------- record pack threshold
def test_pack_threshold_rule():
    assert PACK_MIN_BROKEN == 3
    assert not pack_eligible("chit", 2) and pack_eligible("chit", 3) and pack_eligible("other", 5)
    assert not pack_eligible("vendor", 9)


def test_pack_endpoint(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    pdf = client.get(f"/api/dues/{ids['chit']}/pack.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
    assert client.get(f"/api/dues/{ids['milk']}/pack.pdf").status_code == 409       # vendor kind: no pack
    early = client.get(f"/api/dues/{ids['chit']}/pack.pdf",
                       params={"as_of": (TODAY - dt.timedelta(days=95)).isoformat()})
    assert early.status_code == 409 and early.json()["detail"]["error"] == "too_early"   # only 2 promises by then


def test_pack_text_has_legal_aid_and_no_accusation(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    with dues_route.db.session() as s:
        v = dues_route.account_view(s, s.get(dues_route.DuesAccount, ids["chit"]), TODAY)
    text = " ".join(b.text for b in dues_core.pack_blocks(v))
    assert "15100" in text and "not legal advice" in text.lower()
    for word in ("fraud", "cheat", "scam", "police", "मोसम", "మోసం"):
        assert word not in text.lower()
    assert all(p["hash"][:16] in text for p in v["promises"])


# --------------------------------------------------------------------------- hash chain
def test_hash_chain_valid_and_detects_edits(client):
    ids = client.post("/api/dues/demo").json()["accounts"]
    v = client.get(f"/api/dues/{ids['chit']}").json()
    assert v["chain"]["valid"] and v["chain"]["count"] == 1 + 1 + 6
    with dues_route.db.session() as s:
        logs = [e.model_dump() for e in s.exec(dues_route.select(dues_route.DuesLog)
                                               .where(dues_route.DuesLog.account_id == ids["chit"])
                                               .order_by(dues_route.DuesLog.id)).all()]
    assert verify_log(logs)["valid"]
    tampered = [dict(e) for e in logs]
    tampered[3]["text"] = tampered[3]["text"].replace("ఈ వారం", "వచ్చే నెల")
    out = verify_log(tampered)
    assert out["valid"] is False and out["broken_at"] == logs[3]["id"]
    assert log_hash(logs[0]["prev_hash"], logs[0]) == logs[0]["hash"]


# --------------------------------------------------------------------------- API flows
def test_parse_create_promise_paid_flow(client):
    r = client.post("/api/dues/parse", data={"text": "October doodh 1850, paper 320", "kind": "vendor"}).json()
    assert r["total"] == 2170 and len(r["items"]) == 2 and r["promise"] is None
    body = {"kind": "vendor", "party_name": "Mehta madam", "party_lang": "en", "owner_name": "Ramu",
            "owner_vpa": "demo.ramu@baaki", "party_phone": "98480 00000",
            "items": [{k: i[k] for k in ("label", "amount", "item_key", "month", "source_text")} for i in r["items"]]}
    a = client.post("/api/dues", json=body).json()
    aid = a["account"]["id"]
    assert a["balance"] == 2170 and a["chain"]["valid"] and a["chain"]["count"] == 3
    p = client.post(f"/api/dues/{aid}/promises", data={"text": "next month first week, pakka",
                                                       "said_on": "2026-11-02"}).json()
    assert p["promises"][0]["due_date"] == "2026-12-07"   # said on the 2nd with "next month"
    assert client.post(f"/api/dues/{aid}/promises", data={"text": "haan haan de dunga"}).status_code == 422
    fixed = client.post(f"/api/dues/{aid}/promises", data={"text": "haan haan de dunga", "due_date": "2026-11-20"}).json()
    assert fixed["promises"][-1]["due_date"] == "2026-11-20"
    rem = client.post(f"/api/dues/{aid}/remind", json={}).json()
    assert rem["whatsapp_url"].startswith("https://wa.me/919848000000?text=")
    assert rem["checks"]["amounts_ok"] and rem["checks"]["amounts_expected"] == [320, 1850, 2170]
    paid = client.post(f"/api/dues/{aid}/paid", json={"amount": 2170}).json()
    assert paid["balance"] == 0 and paid["chain"]["valid"]
    assert client.post(f"/api/dues/{aid}/remind", json={}).status_code == 409
    st = client.post(f"/api/dues/promises/{fixed['promises'][-1]['id']}/status", json={"status": "kept"}).json()
    assert st["promises"][-1]["status"] == "kept" and st["chain"]["valid"]
    assert client.delete(f"/api/dues/{aid}").json() == {"deleted": aid}
    assert client.get(f"/api/dues/{aid}").status_code == 404


def test_parse_audio_uses_codemix_stt(client, mock_gnani, short_wav):
    seen = []

    def stt(request):
        seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": "అక్టోబర్ పాలు 1,850, పేపర్ 320",
                                         "detected_language_code": "te-IN"})

    mock_gnani.push("/stt/v3", stt)
    r = client.post("/api/dues/parse", data={"lang": "te", "kind": "vendor"},
                    files={"audio": ("clip.wav", short_wav, "audio/wav")})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["total"] == 2170 and out["transcript"].startswith("అక్టోబర్")
    assert seen and seen[0].get("language_code") == "te-IN,en-IN"
