"""G13 spoken consent = voice sample. Offline: mocked Gnani (STT, embeddings, TTS). Synthetic people only."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import config, consent_flow, consent_text as ct, db
from app.main import app
from app.models import DiaryEntry, VoiceProfile, Worker

from .conftest import make_wav, multipart_fields

TE_GOOD = ("నా పేరు లక్ష్మి. నా గొంతుతో నా యజమానికి సందేశాలు పంపడానికి బాకీ కి అనుమతి ఇస్తున్నాను. "
           "ప్రతి సందేశం ముందు ఇది ఏఐ సందేశం అని చెబుతుంది. నేను ఎప్పుడైనా దీన్ని తొలగించొచ్చు.")
TE_UNRELATED = "ఈరోజు వాతావరణం చాలా బాగుంది, నేను మార్కెట్‌కి వెళ్ళాను. లక్ష్మి."
HI_GOOD = ("मेरा नाम लक्ष्मी है। मैं बाकी को अपनी आवाज में मेरे एम्प्लॉयर को मैसेज भेजने की अनुमति देती हूं। "
           "हर message पहले बताएगा कि यह एआई message है। मैं इसे कभी भी डिलीट कर सकती हूं।")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_attempts():
    consent_flow._ATTEMPTS.clear()
    yield
    consent_flow._ATTEMPTS.clear()


def _worker(name="Lakshmi", lang="te-IN") -> int:
    with db.session() as s:
        w = Worker(name=name, language=lang)
        s.add(w)
        s.commit()
        return w.id


def _embed_ok(seen):
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {"voice_clone_embedding": {
            "embedding": "QUJD" * 1024, "shape": [1, 768], "dtype": "torch.bfloat16"}}})
    return handler


def _stt(text, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": text, "detected_language_code": "te-IN"})
    return handler


CLIP = make_wav([("tone", 12.0)])


def _attempt(client, wid, method="spoken", lang=None, clip=CLIP):
    data = {"worker_id": str(wid), "method": method}
    if lang:
        data["lang"] = lang
    return client.post("/api/consent/attempt", data=data, files={"audio": ("consent.wav", clip, "audio/wav")})


def _consents(wid):
    with db.session() as s:
        return list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == wid, DiaryEntry.kind == "consent")
                           .order_by(DiaryEntry.id)))


# --------------------------------------------------------------------------- matcher (pure)
def test_skeleton_is_script_independent():
    assert ct.skeleton("Lakshmi") == ct.skeleton("లక్ష్మి") == ct.skeleton("लक्ष्मी") == ct.skeleton("laxmi")
    assert ct.skeleton("Rafiq") == ct.skeleton("रफ़ीक़") == ct.skeleton("రఫీక్")
    assert ct.skeleton("delete") == ct.skeleton("डिलीट")
    assert ct.skeleton("अनुमति") == ct.skeleton("అనుమతి")


@pytest.mark.parametrize("lang", ["te-IN", "hi-en", "en"])
def test_reading_the_exact_sentence_passes(lang):
    m = ct.match(ct.consent_sentence("Lakshmi", lang), "Lakshmi", lang)
    assert m["passed"] and m["name_matched"] and m["content_matched"] == m["content_total"] and m["missed"] == []


def test_telugu_variants_and_split_words_pass():
    m = ct.match(TE_GOOD, "Lakshmi", "te-IN")
    assert m["passed"], m["missed"]
    assert m["ratio"] >= 0.9


def test_hinglish_in_devanagari_passes():
    m = ct.match(HI_GOOD, "Lakshmi", "hinglish")
    assert m["lang"] == "hi-en" and m["passed"], m["missed"]


def test_latin_transliteration_of_name_is_accepted():
    m = ct.match(ct.consent_sentence("Lakshmi", "en").replace("Lakshmi", "Laxmi"), "Lakshmi", "en")
    assert m["passed"] and m["name_matched"]


def test_unrelated_speech_fails_and_lists_missed_words():
    m = ct.match(TE_UNRELATED, "Lakshmi", "te-IN")
    assert not m["passed"] and m["reason"] == "too_few_words" and m["name_matched"]
    assert "అనుమతి" in m["missed"] and len(m["missed"]) >= 10
    assert all(w["matched"] is None for w in m["words"] if w["kind"] == "filler")


def test_wrong_name_fails_even_with_every_other_word():
    m = ct.match(ct.consent_sentence("Lakshmi", "te-IN").replace("లక్ష్మి", "సునీత"), "Lakshmi", "te-IN")
    assert not m["passed"] and m["reason"] == "name_not_heard"


def test_partial_reading_below_threshold_fails():
    first_half = " ".join(ct.consent_sentence("Lakshmi", "te-IN").split()[:9])
    m = ct.match(first_half, "Lakshmi", "te-IN")
    assert not m["passed"] and m["ratio"] < ct.PASS_RATIO
    assert ct.match("", "Lakshmi", "te-IN")["passed"] is False


def test_prompt_speech_is_slow_and_paused():
    sp = ct.speech_text("Lakshmi", "te-IN")
    assert sp.startswith("<slow> ") and sp.count("<pauses>") == 3 and "లక్ష్మి" in sp


# --------------------------------------------------------------------------- API
def test_get_consent_text_and_words(client):
    wid = _worker()
    b = client.get(f"/api/consent?worker_id={wid}").json()
    assert b["lang"] == "te-IN" and "లక్ష్మి" in b["text"] and b["prompt"] is None
    kinds = {w["kind"] for w in b["words"]}
    assert kinds == {"name", "content", "filler"}
    assert b["profile"]["exists"] is False and b["log"] == [] and b["consent_active"] is False
    hi = client.get(f"/api/consent?worker_id={wid}&lang=hinglish").json()
    assert hi["lang"] == "hi-en" and "लक्ष्मी" in hi["text"]
    assert client.get("/api/consent?worker_id=999").status_code == 404


def test_match_endpoint_needs_no_gnani(client):
    wid = _worker()
    r = client.post("/api/consent/match", json={"worker_id": wid, "transcript": TE_GOOD}).json()
    assert r["passed"] is True


def test_spoken_consent_makes_profile_and_logs_diary(client, mock_gnani):
    wid = _worker()
    emb, stt = [], []
    mock_gnani.default["/stt/v3"] = _stt(TE_GOOD, stt)
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb)
    media_before = set(config.media_dir().rglob("*")) if config.media_dir().exists() else set()
    r = _attempt(client, wid)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "ready" and b["consent_method"] == "spoken" and b["audio_stored"] is False
    assert b["match"]["passed"] and b["profile"]["exists"] and b["profile"]["audio_stored"] is False
    assert len(stt) == 1 and stt[0]["language_code"] == "te-IN,en-IN" and stt[0]["format"] == "codemix"
    assert len(emb) == 1
    rows = _consents(wid)
    assert len(rows) == 1 and rows[0].audio_sha256 == db.sha256_hex(CLIP) == b["audio_sha256"]
    assert "method: spoken" in rows[0].text and "లక్ష్మి" in rows[0].text
    assert b["consent"]["hash"] == rows[0].hash and b["consent"]["consent_method"] == "spoken"
    media_after = set(config.media_dir().rglob("*")) if config.media_dir().exists() else set()
    assert media_after == media_before                       # the recording is never stored
    chain = client.get(f"/api/diary?worker_id={wid}").json()["chain"]
    assert chain["valid"] and chain["count"] == 1
    st = client.get(f"/api/consent?worker_id={wid}").json()
    assert st["consent_active"] and st["profile"]["exists"] and st["log"][0]["event"] == "given"


def test_failed_match_never_embeds_then_tap_confirms_without_second_stt(client, mock_gnani):
    wid = _worker()
    emb, stt = [], []
    mock_gnani.default["/stt/v3"] = _stt(TE_UNRELATED, stt)
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb)
    b = _attempt(client, wid).json()
    assert b["status"] == "not_matched" and b["can_retry"] and b["can_confirm_by_tap"]
    assert b["missed"] and any(w["matched"] is False for w in b["words"])
    assert emb == [] and _consents(wid) == []                # nothing made, nothing logged
    with db.session() as s:
        assert s.exec(select(VoiceProfile).where(VoiceProfile.worker_id == wid)).first() is None
    t = _attempt(client, wid, method="tap").json()
    assert t["status"] == "ready" and t["consent_method"] == "tap" and t["transcript"] == TE_UNRELATED
    assert len(stt) == 1 and len(emb) == 1                    # the tap reused the first transcript
    rows = _consents(wid)
    assert len(rows) == 1 and "method: tap" in rows[0].text and rows[0].text.startswith("Voice consent given by tap")


def test_stt_down_still_offers_tap(client, mock_gnani):
    wid = _worker()
    emb = []
    mock_gnani.default["/stt/v3"] = httpx.Response(500, json={"detail": {"error_code": "BOOM", "message": "down"}})
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb)
    b = _attempt(client, wid).json()
    assert b["status"] == "not_matched" and b["stt_error"]["status"] == 500 and b["can_confirm_by_tap"]
    assert b["match"] is None and len(b["words"]) > 10 and emb == []
    t = _attempt(client, wid, method="tap").json()
    assert t["status"] == "ready" and "spoken check skipped" in t["consent"]["text"]


def test_tap_without_prior_spoken_attempt_is_refused(client, mock_gnani):
    """GAP_AUDIT #13 (intended change): a tap alone (a client flag) never makes a clone."""
    wid = _worker()
    emb = []
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb)
    t = _attempt(client, wid, method="tap").json()
    assert t["status"] == "spoken_first" and t["can_confirm_by_tap"] is False
    assert emb == [] and _consents(wid) == []
    assert not [r for r in mock_gnani.requests if r.url.path == "/stt/v3"]
    with db.session() as s:
        assert s.exec(select(VoiceProfile).where(VoiceProfile.worker_id == wid)).first() is None


def test_short_recording_spends_nothing(client, mock_gnani):
    wid = _worker()
    b = _attempt(client, wid, clip=make_wav([("tone", 4.0)])).json()
    assert b["status"] == "too_short" and b["can_retry"] and b["duration_s"] < 5
    assert mock_gnani.requests == []
    assert client.post("/api/consent/attempt", data={"worker_id": str(wid)},
                       files={"audio": ("x.txt", b"hello", "text/plain")}).status_code == 415
    assert _attempt(client, wid, method="nod").status_code == 400
    assert _attempt(client, 999).status_code == 404


def test_hinglish_worker_uses_codemix_hinglish(client, mock_gnani):
    wid = _worker("Rafiq", "hi-en")
    stt = []
    text = ct.consent_sentence("Rafiq", "hi-en")
    mock_gnani.default["/stt/v3"] = _stt(text, stt)
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok([])
    b = _attempt(client, wid).json()
    assert b["status"] == "ready" and b["lang"] == "hi-en"
    assert stt[0]["language_code"] == "hi-IN,en-IN" and stt[0]["format"] == "codemix"


def test_withdraw_deletes_profile_and_logs(client, mock_gnani):
    wid = _worker()
    mock_gnani.default["/stt/v3"] = _stt(TE_GOOD)
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok([])
    assert _attempt(client, wid).json()["status"] == "ready"
    w = client.post("/api/consent/withdraw", json={"worker_id": wid}).json()
    assert w["deleted"] == 1 and w["logged"] and w["consent"]["event"] == "withdrawn"
    assert "method: spoken" in w["consent"]["text"]
    st = client.get(f"/api/consent?worker_id={wid}").json()
    assert st["profile"]["exists"] is False and st["consent_active"] is False
    assert [x["event"] for x in st["log"]] == ["given", "withdrawn"]
    assert client.get(f"/api/diary?worker_id={wid}").json()["chain"]["valid"]
    again = client.post("/api/consent/withdraw", json={"worker_id": wid}).json()
    assert again["deleted"] == 0 and again["logged"] is False


def test_prompt_is_cached_and_slow(client, mock_gnani, short_ogg):
    wid = _worker()
    seen = []

    def tts(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = tts
    a = client.post("/api/consent/prompt", json={"worker_id": wid}).json()
    assert a["audio_url"].startswith("/api/consent/audio/") and a["cached"] is False and a["tts_error"] is None
    got = client.get(a["audio_url"])
    assert got.status_code == 200 and got.content == short_ogg and got.headers["content-type"] == "audio/ogg"
    assert client.get("/api/consent/audio/" + "0" * 64 + ".ogg").status_code == 404
    assert client.get("/api/consent/audio/..%2F..%2Fapp.db").status_code == 404
    b = client.post("/api/consent/prompt", json={"worker_id": wid}).json()
    assert b["cached"] is True and b["audio_url"] == a["audio_url"] and len(seen) == 1
    assert seen[0]["text"].startswith("<slow> ") and seen[0]["language"] == "te-IN" and seen[0]["voice"] == "Kalpana"
    assert client.get(f"/api/consent?worker_id={wid}").json()["prompt"]["audio_url"] == a["audio_url"]


def test_prompt_tts_error_does_not_block(client, mock_gnani):
    wid = _worker()
    mock_gnani.default["/api/v1/tts/inference"] = httpx.Response(400, json={"detail": {"error_code": "BAD", "message": "x"}})
    r = client.post("/api/consent/prompt", json={"worker_id": wid})
    assert r.status_code == 200 and r.json()["audio_url"] is None and r.json()["tts_error"]


def test_voice_profile_post_goes_through_the_spoken_check(client, mock_gnani):
    """GAP_AUDIT #13 (intended change): POST /api/voice-profile is no longer a bare consent=true flag."""
    wid = _worker()
    emb = []
    mock_gnani.default["/api/v1/tts/voice-clone/embeddings"] = _embed_ok(emb)
    mock_gnani.default["/stt/v3"] = _stt(TE_UNRELATED)
    r = client.post("/api/voice-profile", data={"worker_id": str(wid), "consent": "true"},
                    files={"audio": ("v.wav", CLIP, "audio/wav")})
    assert r.status_code == 400 and r.json()["detail"]["error"] == "consent_not_heard" and emb == []
    mock_gnani.default["/stt/v3"] = _stt(TE_GOOD)
    r = client.post("/api/voice-profile", data={"worker_id": str(wid), "consent": "true"},
                    files={"audio": ("v.wav", CLIP, "audio/wav")})
    assert r.status_code == 200 and r.json()["exists"] and len(emb) == 1
    assert len(_consents(wid)) == 1 and "method: spoken" in _consents(wid)[0].text
