"""Employer page, pay, plan, reply, and the opt-in voice profile. Offline, mocked Gnani/LLM."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import audio, config, db, llm, translate, voice_note
from app.main import app
from app.models import Employer, Message, Payment, VoiceProfile

from .b_data import make_case, tts_ok
from .conftest import make_wav, multipart_fields


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _tts_log(ogg, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


# --------------------------------------------------------------------------- employer page
def test_employer_page_shows_items_audio_and_upi(client, mock_gnani, short_ogg):
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    ids = make_case(shortfall_info=2500)
    sent = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False}).json()
    # F2 (GAP #10): a draft never plays on his page; she shares it first
    assert client.get(f"/api/e/{ids['token']}").json()["audio_url"] is None
    client.post(f"/api/messages/{sent['message_id']}/sent")
    r = client.get(f"/api/e/{ids['token']}")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["balance"] == 13000 and b["balance_display"] == "₹13,000"
    assert b["audio_url"] == sent["audio_url"] and b["pdf_url"] == sent["pdf_url"]
    assert b["upi"]["link"] == "upi://pay?pa=lakshmi.demo@upi&pn=Lakshmi&am=13000&cu=INR&tn=Baaki"
    labels = [i["label"] for i in b["items"]]
    assert "अगस्त 2026 की salary" in labels
    est = [i for i in b["items"] if i["kind"] == "min_wage_shortfall"][0]
    assert est["is_estimate"] and not est["included_in_total"]
    assert b["badge"] is None
    assert client.post(f"/api/e/{ids['token']}/played").json()["status"] == "played"
    assert client.get("/api/e/nope").status_code == 404


# --------------------------------------------------------------------------- pay
# F2 (GAP #5): "I've paid" is a claim; the alert and badge come only after she confirms (decide accept).
def _confirm(client, claim_id):
    r = client.post(f"/api/hisaab/{claim_id}/decide", json={"decision": "accept"})
    assert r.status_code == 200, r.text
    return r.json()


def test_pay_in_full_triggers_excited_alert_and_badge(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, seen)
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/pay", json={})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["pending_confirmation"] and not c["fully_paid"] and c["badge"] is None and not seen
    b = _confirm(client, c["claim"]["id"])
    assert b["fully_paid"] and b["balance"] == 0 and b["case_status"] == "paid"
    assert b["badge"]["title"] == "Fair Employer" and "13,000" not in b["badge"]["text"]
    # Lakshmi hears it in Telugu, with the <excited> tag, on Timbre v3.0
    assert len(seen) == 1
    assert seen[0]["text"].startswith("<excited> డబ్బులు వచ్చేశాయి!") and "పదమూడు వేల రూపాయలు" in seen[0]["text"]
    assert seen[0]["language"] == "te-IN" and seen[0]["model"] == "timbre-v3.0"
    assert b["alert"]["text"].startswith("డబ్బులు వచ్చేశాయి!") and "₹13,000" in b["alert"]["text"]
    assert b["alert"]["audio"]["url"]
    with db.session() as s:
        assert s.get(Employer, ids["employer_id"]).fair_employer is True
    assert client.get(f"/api/e/{ids['token']}").json()["badge"]["reason"] == "paid_in_full"
    assert client.post(f"/api/e/{ids['token']}/pay", json={}).status_code == 409


def test_partial_pay_hinglish_worker(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, seen)
    ids = make_case(worker_name="Rafiq", worker_lang="hi-en", employer_name="Rao garu", employer_lang="te-IN")
    c = client.post(f"/api/e/{ids['token']}/pay", json={"amount": 5000}).json()
    b = _confirm(client, c["claim"]["id"])
    assert b["balance"] == 8000 and not b["fully_paid"] and b["badge"] is None
    assert seen[0]["text"].startswith("<excited> पैसा आ गया!") and "राव गारु" in seen[0]["text"]
    assert "आठ हज़ार रुपये बाकी" in seen[0]["text"] and seen[0]["language"] == "hi-en"
    assert client.post(f"/api/e/{ids['token']}/pay", json={"amount": 9000}).status_code == 400


def test_pay_without_gnani_still_records(client):
    ids = make_case()
    c = client.post(f"/api/e/{ids['token']}/pay", json={"method": "cash"}).json()
    b = _confirm(client, c["claim"]["id"])
    assert b["fully_paid"] and b["alert"]["audio"] is None and b["alert"]["audio_error"]["code"] == "NOT_CONFIGURED"


# --------------------------------------------------------------------------- plan
@pytest.mark.parametrize("n", [2, 3])
def test_plan_creates_instalments_and_reminders(client, n):
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/plan", json={"instalments": n})
    assert r.status_code == 200, r.text
    b = r.json()
    assert len(b["instalments"]) == n and b["total_check"]
    assert sum(i["amount"] for i in b["instalments"]) == 13000
    dues = [i["due_date"] for i in b["instalments"]]
    assert dues == sorted(dues) and len(set(dues)) == n
    assert all(i["reminder"]["status"] == "scheduled" for i in b["instalments"])
    assert b["instalments"][0]["reminder"]["text"].startswith("याद दिलाना")
    assert "am=" in b["instalments"][0]["upi_link"]
    assert b["worker_note"]["text"].startswith("శర్మ గారు")
    # replacing the plan does not duplicate
    client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 2})
    with db.session() as s:
        from sqlmodel import select
        planned = list(s.exec(select(Payment).where(Payment.case_id == ids["case_id"], Payment.status == "planned")))
        reminders = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "reminder")))
    assert len(planned) == 2 and len(reminders) == 2
    assert client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 4}).status_code == 422


def test_paying_first_instalment_settles_it(client):
    ids = make_case()
    plan = client.post(f"/api/e/{ids['token']}/plan", json={"instalments": 2}).json()
    first = plan["instalments"][0]["amount"]
    c = client.post(f"/api/e/{ids['token']}/pay", json={"amount": first, "alert_audio": False}).json()
    _confirm(client, c["claim"]["id"])
    page = client.get(f"/api/e/{ids['token']}").json()
    assert [p["status"] for p in page["plan"]] == ["settled", "planned"]
    assert page["balance"] == 13000 - first


def test_split_amount():
    from app.routes.employer import split_amount

    assert split_amount(13000, 3) == [4334, 4333, 4333]
    assert split_amount(1000.5, 2) == [500.5, 500]
    assert sum(split_amount(44000, 3)) == 44000


# --------------------------------------------------------------------------- reply
def _stt_reply(transcript, seen):
    def handler(request):
        seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": transcript, "detected_language_code": "hi-IN"})
    return handler


def test_reply_hinglish_to_telugu_with_llm(client, mock_gnani, short_ogg, short_wav, monkeypatch):
    stt_seen, tts_seen = [], []
    mock_gnani.push("/stt/v3", _stt_reply("Lakshmi ko bolo, main शनिवार को बारह हज़ार रुपये दूँगा, baaki agle mahine।", stt_seen))
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, tts_seen)
    monkeypatch.setattr(config, "groq_key", lambda: "gk")

    async def fake_json_call(system, user, schema, *, name="result", validate=None, **kw):
        assert "Telugu" in system
        out = {"translation": "లక్ష్మికి చెప్పండి, శనివారం ₹12,000 ఇస్తాను, మిగతాది వచ్చే నెల."}
        return validate(out) if validate else out

    monkeypatch.setattr(llm, "json_call", fake_json_call)
    ids = make_case()
    r = client.post(f"/api/e/{ids['token']}/reply", files={"audio": ("reply.wav", short_wav, "audio/wav")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert stt_seen[0]["language_code"] == "hi-IN,en-IN" and stt_seen[0]["format"] == "codemix"
    assert [a["value"] for a in b["amounts"]] == [12000]
    assert b["translation"]["source"] == "llm" and b["translation"]["language"] == "te-IN"
    assert "₹12,000" in b["translation"]["text"]
    spoken = " ".join(t["text"] for t in tts_seen)
    assert len(tts_seen) == 1 and all(t["language"] == "te-IN" for t in tts_seen)
    assert "పన్నెండు వేల రూపాయలు" in spoken and "₹" not in spoken and "శర్మ గారు" in spoken
    assert b["audio"]["url"] and b["original_audio_url"]
    with db.session() as s:
        from sqlmodel import select
        msgs = list(s.exec(select(Message).where(Message.case_id == ids["case_id"], Message.step == "reply")))
    assert {m.direction for m in msgs} == {"from_employer", "to_worker"}
    page = client.get(f"/api/e/{ids['token']}").json()
    assert page["replies"][0]["text"].startswith("Lakshmi ko bolo")


def test_reply_translation_amount_mismatch_falls_back(client, mock_gnani, short_ogg, short_wav, monkeypatch):
    mock_gnani.push("/stt/v3", _stt_reply("मैं बारह हज़ार रुपये दूँगा", []))
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    monkeypatch.setattr(config, "groq_key", lambda: "gk")

    async def fake_json_call(system, user, schema, *, name="result", validate=None, **kw):
        try:
            return validate({"translation": "నేను ₹2,000 ఇస్తాను"})     # wrong amount
        except ValueError:
            return None

    monkeypatch.setattr(llm, "json_call", fake_json_call)
    ids = make_case()
    b = client.post(f"/api/e/{ids['token']}/reply", files={"audio": ("r.wav", short_wav, "audio/wav")}).json()
    assert b["translation"]["source"] == "template"
    assert "₹12,000" in b["translation"]["text"] and "2,000" not in b["translation"]["text"].replace("12,000", "")
    assert any("పన్నెండు వేల రూపాయలు" in s for s in b["translation"]["speech"])


def test_reply_telugu_employer_to_hinglish_worker_no_llm(client, mock_gnani, short_ogg, short_wav):
    stt_seen, tts_seen = [], []
    mock_gnani.push("/stt/v3", _stt_reply("రఫీక్ కి చెప్పండి, ఐదు వేల రూపాయలు రేపు ఇస్తాను.", stt_seen))
    mock_gnani.default["/api/v1/tts/inference"] = _tts_log(short_ogg, tts_seen)
    ids = make_case(worker_name="Rafiq", worker_lang="hi-en", employer_name="Rao garu", employer_lang="te-IN")
    b = client.post(f"/api/e/{ids['token']}/reply", files={"audio": ("r.wav", short_wav, "audio/wav")}).json()
    assert stt_seen[0]["language_code"] == "te-IN,en-IN" and stt_seen[0]["format"] == "codemix"
    assert b["translation"]["source"] == "template" and b["translation"]["amounts"] == [5000]
    assert all(t["language"] == "hi-en" for t in tts_seen)
    assert "पाँच हज़ार रुपये" in " ".join(t["text"] for t in tts_seen) or "पांच हज़ार रुपये" in " ".join(t["text"] for t in tts_seen)


def test_reply_rejects_bad_audio(client):
    ids = make_case()
    assert client.post(f"/api/e/{ids['token']}/reply", files={"audio": ("r.txt", b"hi", "text/plain")}).status_code == 415


async def test_translate_same_language_passthrough():
    t = await translate.translate("मैं ₹12,000 दूँगा", "hi-en", "hi-en", use_llm=False)
    assert t.source == "same_language" and t.amounts == [12000]


# --------------------------------------------------------------------------- voice profile
def _embed_ok(seen):
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {"voice_clone_embedding": {
            "embedding": "QUJD" * 1024, "shape": [1, 768], "dtype": "torch.bfloat16"}}})
    return handler


def test_voice_profile_needs_consent(client, mock_gnani):
    seen = []
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(seen)
    ids = make_case()
    wav = make_wav([("tone", 12.0)])
    for consent in (None, "false", "yes-ish"):
        data = {"worker_id": str(ids["worker_id"])}
        if consent is not None:
            data["consent"] = consent
        r = client.post("/api/voice-profile", data=data, files={"audio": ("v.wav", wav, "audio/wav")})
        assert r.status_code == 400 and r.json()["detail"]["error"] == "consent_required"
        assert "రికార్డింగ్ దాచము" in r.json()["detail"]["consent_text"]
    assert seen == []                                   # nothing reached Gnani without consent


def test_voice_profile_create_use_and_delete(client, mock_gnani, short_ogg):
    emb_seen, tts_seen = [], []
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb_seen)

    def tts(request):
        body = json.loads(request.content)
        tts_seen.append(body)
        if body["model"] == "vachana-vc-v1":
            return httpx.Response(200, content=make_wav([("tone", 0.8)]), headers={"content-type": "audio/wav"})
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = tts
    # GAP_AUDIT #13 (intended change): the recording must carry the spoken consent sentence
    from app import consent_text as ct
    said = ct.consent_sentence("Lakshmi", ct.lang_for_worker("te-IN", None))
    mock_gnani.default["/stt/v3"] = httpx.Response(200, json={"success": True, "transcript": said,
                                                              "detected_language_code": "te-IN"})
    ids = make_case()
    media_before = set((config.media_dir()).rglob("*")) if config.media_dir().exists() else set()
    r = client.post("/api/voice-profile", data={"worker_id": str(ids["worker_id"]), "consent": "true"},
                    files={"audio": ("v.wav", make_wav([("tone", 24.0)]), "audio/wav")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["exists"] and b["audio_stored"] is False and b["stored"] == "embedding only" and b["trimmed_to_20s"]
    assert b["duration_s"] == 20.0 and "embedding" not in json.dumps(b).replace("embedding only", "").replace("embedding_shape", "")
    f = multipart_fields(emb_seen[0])
    assert f["audio_file.filename"].endswith(".wav")
    media_after = set((config.media_dir()).rglob("*")) if config.media_dir().exists() else set()
    assert media_after == media_before                  # the recording was never stored
    # the voice note now uses her clone, and says so
    m = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False}).json()
    assert m["voice_mode"] == "clone" and m["audio"]["voice"] == "worker-clone"
    assert "उनकी आवाज़ में" in m["text"]
    assert all(t["model"] == "vachana-vc-v1" for t in tts_seen)
    with db.session() as s:
        prof = s.get(VoiceProfile, b["profile_id"])
        emb = voice_note.load_embedding(prof)
    assert voice_note.vc_cache_dir(emb).exists()
    # stock is still available on request
    st = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "voice": "stock"}).json()
    assert st["voice_mode"] == "stock" and "उनकी ओर से" in st["text"]
    # delete removes the profile and the cloned clips
    d = client.delete(f"/api/voice-profile?worker_id={ids['worker_id']}").json()
    assert d["deleted"] == 1 and d["exists"] is False
    assert not voice_note.vc_cache_dir(emb).exists()
    assert client.get(f"/api/voice-profile?worker_id={ids['worker_id']}").json()["exists"] is False
    after = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False}).json()
    assert after["voice_mode"] == "stock"


def test_voice_profile_rejects_short_recording(client, mock_gnani):
    seen = []
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(seen)
    ids = make_case()
    r = client.post("/api/voice-profile", data={"worker_id": str(ids["worker_id"]), "consent": "true"},
                    files={"audio": ("v.wav", make_wav([("tone", 4.0)]), "audio/wav")})
    assert r.status_code == 400 and r.json()["detail"]["error"] == "bad_recording" and seen == []
    assert client.post("/api/voice-profile", data={"worker_id": "999", "consent": "true"},
                       files={"audio": ("v.wav", b"x", "audio/wav")}).status_code == 404


def test_speakable_turns_digit_amounts_into_words():
    assert translate.speakable("నేను శనివారం 12,000 రూపాయలు ఇస్తాను.", "te-IN") == "నేను శనివారం పన్నెండు వేల రూపాయలు ఇస్తాను."
    assert "पाँच हज़ार रुपये" in translate.speakable("₹5,000 कल दूँगा", "hi-en")
