"""Share to Baaki + Promise Keeper (W04+G16+W05). Offline: Gnani STT/TTS and the LLM are mocked."""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import config, db, llm
from app.inbox_logic import detect_lang, extract_promises, reminder
from app.inbox_models import InboxCard
from app.main import app
from app.models import DiaryEntry
from app.routes import inbox as inbox_route
from app.routes.cases import add_diary_entry

from .b_data import make_case, tts_ok
from .conftest import multipart_fields

SAID = dt.date(2026, 11, 9)   # a Monday


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(inbox_route, "_today", lambda: SAID)
    with TestClient(app) as c:
        yield c


def _stt(transcript, seen, detected="hi-IN"):
    def handler(request):
        seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": transcript, "detected_language_code": detected})
    return handler


def _tts_log(ogg, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


def _fake_llm(monkeypatch, translation):
    monkeypatch.setattr(config, "groq_key", lambda: "gk")

    async def fake_json_call(system, user, schema, *, name="result", validate=None, **kw):
        out = {"translation": translation}
        return validate(out) if validate else out

    monkeypatch.setattr(llm, "json_call", fake_json_call)


# --------------------------------------------------------------------------- 1. Hinglish voice note, relative date
def test_hinglish_voice_note_promise_next_week(client, mock_gnani, short_ogg, short_wav, monkeypatch):
    stt_seen, tts_seen = [], []
    mock_gnani.push("/stt/v3", _stt("Lakshmi, agle hafte 12,692 de dungi, abhi thoda tight hai", stt_seen))
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, tts_seen)
    _fake_llm(monkeypatch, "లక్ష్మి, వచ్చే వారం ₹12,692 ఇస్తాను, ఇప్పుడు కొంచెం కష్టంగా ఉంది.")
    ids = make_case(diary_days=0)
    r = client.post(f"/api/inbox/{ids['case_id']}", files={"audio": ("PTT-20261109-WA0007.opus", short_ogg, "audio/ogg")})
    assert r.status_code == 200, r.text
    b = r.json()
    # Prisma: the employer's language (Hinglish) with codemix; the .opus share was renamed to .ogg
    assert stt_seen[0]["language_code"] == "hi-IN,en-IN" and stt_seen[0]["format"] == "codemix"
    assert b["language_code"] == "hi-en" and b["transcript"].startswith("Lakshmi, agle hafte")
    assert b["translation"].startswith("లక్ష్మి") and b["translation_source"] == "llm" and b["translation_lang"] == "te-IN"
    p = b["promise"]
    assert p["amount"] == 12692 and p["due_date"] == "2026-11-22" and p["range_start"] == "2026-11-16"
    assert p["phrase"] == "agle hafte" and p["precision"] == "week" and p["status"] == "pending"
    assert p["confidence"] >= 0.8
    assert b["summary"]["text_en"] == "Sharma ji said on 9 November: will pay ₹12,692 by 22 November."
    # One Timbre call in Telugu: translation + the read-back of the promise, amounts as words
    assert len(tts_seen) == 1 and tts_seen[0]["language"] == "te-IN"
    spoken = tts_seen[0]["text"]
    assert "పన్నెండు వేల ఆరు వందల తొంభై రెండు రూపాయలు" in spoken and "22 నవంబర్" in spoken and "₹" not in spoken
    assert b["audio_url"] and b["original_audio_url"] and b["audio_error"] is None
    # The card is a diary-chain entry
    with db.session() as s:
        e = s.get(DiaryEntry, b["card"]["diary_entry_id"])
        assert e.kind == "evidence" and e.hash == b["card"]["hash"] and e.case_id == ids["case_id"]
        assert e.text.startswith("Employer reply (WhatsApp voice note), Sharma ji") and "₹12,692 by 22 November 2026" in e.text
        assert e.audio_sha256
    g = client.get(f"/api/inbox/{ids['case_id']}").json()
    assert len(g["cards"]) == 1 and g["counts"]["pending"] == 1 and g["passed"] == []
    assert g["chain"]["valid"] and g["chain"]["cards_linked"]


def test_sample_reply_two_promises(client, mock_gnani, short_ogg, short_wav):
    """Agent B's synthetic clip: "Saturday ₹12,000, the rest next month" -> two promises, Saturday first."""
    mock_gnani.push("/stt/v3", _stt("लक्ष्मी को बोलो, मैं शनिवार को बारह हज़ार रुपये दे दूँगा, बाकी अगले महीने।", []))
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"use_llm": "false"},
                    files={"audio": ("reply.wav", short_wav, "audio/wav")}).json()
    assert [(p["amount"], p["due_date"], p["is_rest"]) for p in b["promises"]] == \
        [(12000, "2026-11-14", False), (None, "2026-12-31", True)]
    assert b["translation_source"] == "template" and "₹12,000" in b["translation"]


def test_auto_language_detects_telugu(client, mock_gnani, short_wav):
    seen = []
    mock_gnani.push("/stt/v3", _stt("లక్ష్మి, ఒకటో తారీఖు కి ఐదు వేలు పంపిస్తాను", seen, detected="te-IN"))
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"lang": "auto", "use_llm": "false", "speak": "false"},
                    files={"audio": ("r.wav", short_wav, "audio/wav")}).json()
    assert seen[0]["language_code"] == "te-IN,hi-IN,en-IN" and seen[0]["format"] == "codemix"
    assert b["language_code"] == "te-IN" and b["translation_source"] == "same_language"
    assert b["promise"]["amount"] == 5000 and b["promise"]["due_date"] == "2026-12-01"


# --------------------------------------------------------------------------- 2. Telugu text (pasted)
def test_telugu_text_to_hinglish_worker(client, mock_gnani):
    ids = make_case(worker_name="Rafiq", worker_lang="hi-en", employer_name="Rao garu", employer_lang="te-IN",
                    diary_days=0)
    r = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "రఫీక్, వచ్చే వారం ఐదు వేల రూపాయలు ఇస్తాను.",
                                                         "use_llm": "false", "speak": "false"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["source"] == "text" and b["language_code"] == "te-IN" and b["original_audio_url"] is None
    assert b["translation_lang"] == "hi-en" and b["translation_source"] == "template" and "₹5,000" in b["translation"]
    assert b["promise"]["amount"] == 5000 and b["promise"]["due_date"] == "2026-11-22"
    assert b["summary"]["text"] == "राव गारु ने 9 नवंबर को कहा: 22 नवंबर तक ₹5,000 देंगे।"
    assert mock_gnani.requests == []          # text in, no speech asked: zero Gnani calls


# --------------------------------------------------------------------------- 3. no promise
def test_no_promise_still_saved_as_evidence(client):
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "Lakshmi, is mahine thoda mushkil hai, baad mein baat karte hain",
                                                         "use_llm": "false", "speak": "false"}).json()
    assert b["promise"] is None and b["promises"] == []
    assert b["summary"]["text_en"] == "Sharma ji replied on 9 November."
    assert b["card"]["hash"] and b["language_code"] == "hi-en"
    g = client.get(f"/api/inbox/{ids['case_id']}").json()
    assert g["promises"] == [] and len(g["cards"]) == 1


def test_bad_inputs(client):
    ids = make_case(diary_days=0)
    assert client.post(f"/api/inbox/{ids['case_id']}", data={"text": "  "}).status_code == 400
    assert client.post("/api/inbox/999", data={"text": "agle hafte"}).status_code == 404
    assert client.post(f"/api/inbox/{ids['case_id']}", files={"audio": ("x.txt", b"hi", "text/plain")}).status_code == 415
    assert client.post(f"/api/inbox/{ids['case_id']}", data={"text": "kal dungi", "said_on": "2027-01-01"}).status_code == 400
    assert client.get(f"/api/inbox/{ids['case_id']}?as_of=nope").status_code == 400


# --------------------------------------------------------------------------- 4. passed promise -> reminder
def test_passed_promise_generates_polite_reminder(client):
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "Lakshmi, agle hafte 12,692 de dungi, abhi thoda tight hai",
                                                         "use_llm": "false", "speak": "false"}).json()
    pid = b["promise"]["id"]
    # the due day itself is not "passed"; the day after is
    on_due = client.get(f"/api/inbox/{ids['case_id']}?as_of=2026-11-22").json()
    assert on_due["promises"][0]["status"] == "pending"
    assert client.post(f"/api/inbox/promises/{pid}/remind", json={"as_of": "2026-11-22"}).status_code == 409
    after = client.get(f"/api/inbox/{ids['case_id']}?as_of=2026-11-23").json()
    assert after["promises"][0]["status"] == "passed" and after["promises"][0]["can_remind"]
    assert [p["id"] for p in after["passed"]] == [pid] and after["counts"]["passed"] == 1

    r = client.post(f"/api/inbox/promises/{pid}/remind", json={"as_of": "2026-11-23"})
    assert r.status_code == 200, r.text
    rm = r.json()
    assert rm["language"] == "hi-en" and rm["source"] == "template"
    assert "“agle hafte 12,692 de dungi”" in rm["text"]          # their own words, quoted
    assert "₹12,692" in rm["text"] and "22 नवंबर" in rm["text"] and "शर्मा जी" in rm["text"]
    assert rm["checks"]["amounts_ok"] and rm["checks"]["no_accusation"]
    assert rm["text_worker_lang"].startswith("నమస్కారం శర్మ గారు")
    assert rm["share_text"].endswith(f"/e/{ids['token']}") and rm["whatsapp_url"].startswith("https://wa.me/?text=")
    assert rm["promise"]["reminded_at"]

    # she marks it kept -> no more reminders
    k = client.post(f"/api/inbox/promises/{pid}/status", json={"status": "kept", "as_of": "2026-11-23"}).json()
    assert k["status"] == "kept"
    assert client.post(f"/api/inbox/promises/{pid}/remind", json={"as_of": "2026-11-23"}).status_code == 409
    br = client.post(f"/api/inbox/promises/{pid}/status", json={"status": "broken"}).json()
    assert br["status"] == "broken"


def test_confirm_and_correct_date(client):
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "1 tareekh ko de dungi", "use_llm": "false",
                                                         "speak": "false"}).json()
    pid = b["promise"]["id"]
    assert b["promise"]["due_date"] == "2026-12-01" and b["promise"]["amount"] is None
    v = client.post(f"/api/inbox/promises/{pid}/status", json={"confirmed": True, "due_date": "2026-12-02",
                                                              "amount": 6000}).json()
    assert v["confirmed"] and v["edited"] and v["due_date"] == "2026-12-02" and v["amount"] == 6000
    # the evidence (hash) never changes when she corrects the promise
    g = client.get(f"/api/inbox/{ids['case_id']}").json()
    assert g["cards"][0]["card"]["hash"] == b["card"]["hash"] and g["chain"]["cards_linked"]
    assert client.post("/api/inbox/promises/999/status", json={"status": "kept"}).status_code == 404


def test_payment_marks_promise_kept(client):
    ids = make_case(diary_days=0)
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "agle hafte 5,000 de dungi", "use_llm": "false",
                                                         "speak": "false"}).json()
    client.post(f"/api/e/{ids['token']}/pay", json={"amount": 5000, "alert_audio": False})
    g = client.get(f"/api/inbox/{ids['case_id']}?as_of=2026-11-30").json()
    assert g["promises"][0]["status"] == "kept" and b["promise"]["status"] == "pending"


# --------------------------------------------------------------------------- 5. hash chain
def test_hash_chain_links_into_diary_and_detects_tampering(client):
    ids = make_case(diary_days=0)
    a = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "agle hafte de dungi", "speak": "false",
                                                         "use_llm": "false"}).json()
    with db.session() as s:   # an ordinary check-in in between
        add_diary_entry(s, ids["worker_id"], "Sharma ji ke ghar, do ghante", employer_id=ids["employer_id"],
                        case_id=ids["case_id"])
        s.commit()
    b = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "1 tareekh ko pakka", "speak": "false",
                                                         "use_llm": "false"}).json()
    assert a["card"]["prev_hash"] == ""
    with db.session() as s:
        chain = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == ids["worker_id"]).order_by(DiaryEntry.id)))
    assert [e.kind for e in chain] == ["evidence", "checkin", "evidence"]
    assert b["card"]["prev_hash"] == chain[1].hash and chain[0].hash == a["card"]["hash"]
    g = client.get(f"/api/inbox/{ids['case_id']}").json()
    assert g["chain"]["valid"] and g["chain"]["count"] == 3 and g["chain"]["cards_linked"]
    # the diary route sees the same valid chain
    d = client.get(f"/api/diary?worker_id={ids['worker_id']}").json()
    assert d["chain"]["valid"] and d["chain"]["head"] == b["card"]["hash"]

    # the same note shared twice -> the same card, no second entry
    again = client.post(f"/api/inbox/{ids['case_id']}", data={"text": "1 tareekh ko pakka", "speak": "false"}).json()
    assert again["duplicate"] and again["id"] == b["id"]
    with db.session() as s:
        assert len(list(s.exec(select(InboxCard)))) == 2
        e = s.get(DiaryEntry, a["card"]["diary_entry_id"])
        e.text = e.text.replace("Words", "Wordz")   # tamper with the stored evidence
        s.add(e)
        s.commit()
    g = client.get(f"/api/inbox/{ids['case_id']}").json()
    assert not g["chain"]["valid"] and g["chain"]["broken_at"] == a["card"]["diary_entry_id"]
    assert not g["chain"]["cards_linked"]


# --------------------------------------------------------------------------- pure logic
def test_logic_units():
    assert detect_lang("లక్ష్మి వచ్చే వారం") == "te-IN"
    assert detect_lang("Lakshmi vacche vaaram istanu") == "te-IN"
    assert detect_lang("agle hafte de dungi") == "hi-en"
    assert detect_lang("will pay next week", None, "en") == "en"
    # ₹5,000 is "now", the rest is the promise
    ps = extract_promises("abhi 5,000 bhej raha hoon, baaki 1 tareekh ko", "hi-en", SAID)
    assert [(p["amount"], p["is_rest"], p["due_date"]) for p in ps] == [(None, True, "2026-12-01")]
    # Telugu "next week"
    ps = extract_promises("వచ్చే వారం పన్నెండు వేలు ఇస్తాను", "te-IN", SAID)
    assert ps[0]["amount"] == 12000 and ps[0]["due_date"] == "2026-11-22"
    # a past date ("baat hui thi") is not a promise
    assert extract_promises("teen tareekh ko baat hui thi", "hi-en", SAID) == []
    r = reminder(employer="Rao garu", worker="Rafiq", employer_lang="te-IN", worker_lang="hi-en", said_on="2026-11-09",
                 quote="వచ్చే వారం ఐదు వేల రూపాయలు ఇస్తాను", quote_lang="te-IN", amount=5000, is_rest=False,
                 due_date="2026-11-22")
    assert r["text"].startswith("నమస్కారం రావు గారు") and "₹5,000" in r["text"] and r["checks"]["amounts_ok"]
