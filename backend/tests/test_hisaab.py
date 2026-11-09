"""V09 Hisaab Milao: employer proposes a correction, the worker accepts or rejects. Offline, mocked Gnani."""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import db
from app.hisaab_core import detect_kind, parse_correction, parse_typed_amount, readback, resolve_month
from app.hisaab_models import HisaabProposal
from app.main import app
from app.models import Case, DiaryEntry, Payment
from app.routes.cases import entry_hash

from .b_data import make_case, tts_ok
from .conftest import multipart_fields

TODAY = dt.date(2026, 11, 10)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _stt(transcript, seen):
    def handler(request):
        seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": transcript, "detected_language_code": "hi-IN"})
    return handler


def _tts_log(ogg, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


# --------------------------------------------------------------------------- parsing (app.lang only)
@pytest.mark.parametrize("text,amount,month,kind", [
    ("Maine October mein do hazaar cash diye the", 2000, "2026-10", "cash"),
    ("मैंने अक्टूबर में दो हज़ार कैश दिए थे", 2000, "2026-10", "cash"),
    ("maine 2000 upi kiye the september me", 2000, "2026-09", "upi"),      # bare 2000 is not a year here
    ("Diwali pe 1500 advance diya tha", 1500, None, "advance"),
    ("pichle mahine do hazaar diye", 2000, "2026-10", "other"),
    ("October 2026 me 2000 diye", 2000, "2026-10", "other"),              # 2026 is the year, 2000 the money
    ("I paid Rs 2,500 by GPay in August", 2500, "2026-08", "upi"),
])
def test_parse_correction(text, amount, month, kind):
    p = parse_correction(text, "hi-en", TODAY)
    assert p["amount"] == amount and p["month"] == month and p["kind"] == kind


def test_parse_no_amount_and_month_rollback():
    assert parse_correction("kuch yaad nahi, maine diya tha", "hi-en", TODAY)["amount"] is None
    # app.lang.dates resolves "December" forward (deadline style); a past payment means December 2025
    assert resolve_month("December mein diye", "hinglish", TODAY)[0] == "2025-12"
    assert detect_kind("haath mein diye") == "cash"
    assert parse_typed_amount("₹2,000") == 2000 and parse_typed_amount("do hazaar") == 2000
    assert parse_typed_amount("abc") is None and parse_typed_amount("") is None


def test_readback_telugu_slow_on_amount_words():
    r = readback("Sharma ji", 2000, "cash", "2026-10", "te-IN")
    assert r["text"] == "శర్మ గారు అంటున్నారు: అక్టోబర్ లో ₹2,000 క్యాష్ ఇచ్చారు. నిజమేనా?"
    assert "<slow> రెండు వేల రూపాయలు" in r["speech"] and "₹" not in r["speech"] and r["speech"].endswith("నిజమేనా?")
    hi = readback("Mehta madam", 1500, "upi", None, "hi-en")
    assert "कह रही हैं" in hi["text"] and "₹1,500 यूपीआई से" in hi["text"] and "<slow>" in hi["speech"]


# --------------------------------------------------------------------------- text proposal -> accept
def test_text_proposal_then_accept_updates_both_sides(client, mock_gnani, short_ogg):
    tts_seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, tts_seen)
    ids = make_case()
    r = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "Maine October mein do hazaar cash diye the"})
    assert r.status_code == 200, r.text
    b = r.json()
    p = b["proposal"]
    assert b["state"] == "proposed" and p["status"] == "proposed" and p["said_by"] == "employer"
    assert p["amount"] == 2000 and p["kind"] == "cash" and p["month"] == "2026-10"
    assert p["chip"]["text"] == "−₹2,000 · cash · October (said by Sharma ji)"
    assert "said by the employer" in p["said_by_label"]
    assert p["readback"]["text"].startswith("శర్మ గారు అంటున్నారు")
    assert len(tts_seen) == 1 and tts_seen[0]["language"] == "te-IN" and "<slow>" in tts_seen[0]["text"]
    # never auto-accepted: no money moved
    assert b["balance"] == 13000
    with db.session() as s:
        assert not list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))

    # read-back audio is served from the TTS cache (no second Timbre call)
    a = client.get(p["readback"]["audio_url"])
    assert a.status_code == 200 and a.headers["content-type"] == "audio/ogg" and len(tts_seen) == 1

    # both sides list it
    mine = client.get(f"/api/hisaab/e/{ids['token']}").json()
    hers = client.get(f"/api/hisaab/case/{ids['case_id']}").json()
    assert mine["proposals"][0]["id"] == p["id"] and hers["pending"] == 1

    d = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "accept"})
    assert d.status_code == 200, d.text
    db_ = d.json()
    assert db_["proposal"]["status"] == "accepted" and db_["balance"] == 11000 and db_["changed"]
    assert db_["proposal"]["balance_before"] == 13000 and db_["proposal"]["balance_after"] == 11000

    # a normal Payment row, labelled "said by the employer, accepted by her"
    with db.session() as s:
        pays = list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))
        assert len(pays) == 1 and pays[0].amount == 2000 and pays[0].method == "cash" and pays[0].status == "paid"
        assert "said by the employer" in pays[0].note and "accepted by her" in pays[0].note
        diary = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == ids["worker_id"]).order_by(DiaryEntry.id)))
        # b_data's synthetic check-ins use their own toy hash, so check our two entries link and hash correctly
        for prev, cur in zip(diary[-3:], diary[-2:]):
            assert cur.prev_hash == prev.hash and entry_hash(cur.prev_hash, cur) == cur.hash
        assert [d.kind for d in diary[-2:]] == ["note", "payment"] and "Hisaab Milao" in diary[-1].text

    # every existing total agrees with zero changes to core maths
    assert client.get(f"/api/e/{ids['token']}").json()["balance"] == 11000
    case = client.get(f"/api/cases/{ids['case_id']}").json()
    assert case["balance"] == 11000 and case["amount_paid"] == 2000
    assert client.get(f"/api/hisaab/e/{ids['token']}").json()["proposals"][0]["status_text_employer"].startswith("लक्ष्मी")

    again = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "reject"})
    assert again.status_code == 409 and again.json()["detail"]["error"] == "already_decided"


def test_reject_is_disputed_and_changes_nothing(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    p = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "do hazaar diye the", "kind": "cash"}).json()["proposal"]
    d = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "reject"}).json()
    assert d["proposal"]["status"] == "rejected" and d["proposal"]["display_state"] == "disputed"
    assert d["balance"] == 13000 and not d["changed"]
    hers = client.get(f"/api/hisaab/case/{ids['case_id']}").json()
    assert hers["disputed_total"] == 2000 and hers["proposals"][0]["display_state"] == "disputed"
    with db.session() as s:
        assert not list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"])))
    assert client.get(f"/api/cases/{ids['case_id']}").json()["balance"] == 13000


# --------------------------------------------------------------------------- guards
def test_accept_cannot_exceed_balance(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    p = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "maine pandrah hazaar diye the"}).json()["proposal"]
    assert p["amount"] == 15000 and p["exceeds_balance"]
    r = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "accept"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "too_much"
    assert client.get(f"/api/cases/{ids['case_id']}").json()["balance"] == 13000


def test_no_amount_asks_to_type_then_typed_amount_works(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    r = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "maine pichle mahine kuch paise diye the"})
    assert r.status_code == 422
    det = r.json()["detail"]
    assert det["error"] == "no_amount" and det["transcript"].startswith("maine") and det["message_en"]
    ok = client.post(f"/api/hisaab/e/{ids['token']}",
                     data={"text": det["transcript"], "amount": "1500", "kind": "upi"}).json()["proposal"]
    assert ok["amount"] == 1500 and ok["amount_source"] == "typed" and ok["month"] and ok["kind"] == "upi"


def test_bad_inputs(client):
    ids = make_case()
    t = ids["token"]
    assert client.post(f"/api/hisaab/e/{t}", data={}).status_code == 400
    assert client.post(f"/api/hisaab/e/{t}", data={"text": "x", "kind": "gold"}).status_code == 400
    assert client.post(f"/api/hisaab/e/{t}", data={"text": "x", "month": "Oct"}).status_code == 400
    assert client.post(f"/api/hisaab/e/{t}", data={"amount": "lots"}).status_code == 400
    assert client.post("/api/hisaab/e/nope", data={"text": "do hazaar"}).status_code == 404
    assert client.get("/api/hisaab/case/999").status_code == 404
    assert client.post("/api/hisaab/999/decide", json={"decision": "accept"}).status_code == 404
    assert client.post("/api/hisaab/1/decide", json={"decision": "maybe"}).status_code == 422


def test_readback_audio_failure_keeps_proposal(client):
    """No Gnani key (offline): the proposal is still created, with the text read-back and an audio error."""
    ids = make_case()
    r = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "do hazaar cash diye"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["proposal"]["status"] == "proposed" and b["readback_audio_error"]
    a = client.get(b["proposal"]["readback"]["audio_url"])
    assert a.status_code == 503 and a.json()["detail"]["text"].startswith("శర్మ గారు")


def test_stale_after_token_change(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    p = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "do hazaar diye"}).json()["proposal"]
    with db.session() as s:   # a demo reset re-creates the case with a new token (and maybe the same id)
        c = s.get(Case, ids["case_id"])
        c.employer_token = "fresh-token"
        s.add(c)
        s.commit()
    assert client.get(f"/api/hisaab/case/{ids['case_id']}").json()["proposals"] == []
    assert client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "accept"}).status_code == 404


def test_accept_settling_full_balance_marks_paid(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case()
    p = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "x", "amount": "13000"}).json()["proposal"]
    d = client.post(f"/api/hisaab/{p['id']}/decide", json={"decision": "accept"}).json()
    assert d["balance"] == 0 and d["case_status"] == "paid"
    r = client.post(f"/api/hisaab/e/{ids['token']}", data={"text": "do hazaar"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "nothing_due"


# --------------------------------------------------------------------------- voice
def test_voice_proposal_uses_codemix_hinglish(client, mock_gnani, short_ogg, short_wav):
    stt_seen, tts_seen = [], []
    mock_gnani.push("/stt/v3", _stt("मैंने October में दो हज़ार cash दिए थे", stt_seen))
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, tts_seen)
    ids = make_case()
    r = client.post(f"/api/hisaab/e/{ids['token']}", files={"audio": ("h.wav", short_wav, "audio/wav")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert stt_seen[0]["language_code"] == "hi-IN,en-IN" and stt_seen[0]["format"] == "codemix"
    p = b["proposal"]
    assert p["source"] == "voice" and p["amount"] == 2000 and p["month"] == "2026-10" and p["kind"] == "cash"
    assert p["employer_audio_url"] and p["transcript"].startswith("मैंने")
    with db.session() as s:
        row = s.get(HisaabProposal, p["id"])
        assert row.amount_source == "spoken"


def test_voice_with_no_amount_returns_transcript(client, mock_gnani, short_wav):
    mock_gnani.push("/stt/v3", _stt("maine pehle hi de diya tha", []))
    ids = make_case()
    r = client.post(f"/api/hisaab/e/{ids['token']}", files={"audio": ("h.wav", short_wav, "audio/wav")})
    assert r.status_code == 422 and r.json()["detail"]["transcript"] == "maine pehle hi de diya tha"
