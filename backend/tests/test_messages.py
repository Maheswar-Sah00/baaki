"""Ladder messages, voice notes and PDFs. Offline: Gnani and the LLM are mocked."""
from __future__ import annotations

import datetime as dt
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app import audio, config, db, letter, llm, messages, voice_note
from app.main import app
from app.messages import compose, load_ctx, split_sentences, verify_amounts

from .b_data import make_case, tts_ok

TODAY = dt.date(2026, 11, 9)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _ctx(case_id):
    with db.session() as s:
        return load_ctx(s, case_id)


# --------------------------------------------------------------------------- templates
@pytest.mark.parametrize("lang", ["hi-en", "te-IN", "en"])
@pytest.mark.parametrize("step", ["polite", "firm", "formal"])
async def test_templates_all_steps_all_languages(step, lang):
    ids = make_case()
    d = await compose(_ctx(ids["case_id"]), step, lang=lang, use_llm=False, today=TODAY)
    assert d.source == "template"
    assert d.checks["ok"], d.checks
    assert "₹13,000" in d.text
    assert 13000 in d.checks["speech"]["amounts_found"]       # spoken as words, re-parsed to 13000
    assert "₹" not in " ".join(d.speech)                        # amounts are spoken as words
    assert d.speech[0] == d.disclosure_speech                  # disclosure is spoken first
    assert not messages.forbidden_terms(d.text)
    assert d.reply_by == "2026-11-16"


async def test_disclosure_languages_and_devanagari_brand():
    ids = make_case()
    ctx = _ctx(ids["case_id"])
    hi = await compose(ctx, "polite", lang="hi-en", use_llm=False, today=TODAY)
    assert hi.text.startswith("यह एक AI वॉइस संदेश है")
    assert "Baaki ऐप" in hi.disclosure_speech and "लक्ष्मी" in hi.disclosure_speech
    assert "उनकी ओर से" in hi.disclosure_speech          # stock voice wording
    clone = await compose(ctx, "polite", lang="hi-en", use_llm=False, voice_mode="clone", today=TODAY)
    assert "उनकी आवाज़ में" in clone.disclosure_speech
    te = await compose(ctx, "polite", lang="te-IN", use_llm=False, today=TODAY)
    assert te.text.startswith("ఇది AI వాయిస్ సందేశం")
    en = await compose(ctx, "polite", lang="en", use_llm=False, today=TODAY)
    assert en.text.startswith("This is an AI voice message")


async def test_hinglish_speech_amounts_are_devanagari_words():
    ids = make_case()
    d = await compose(_ctx(ids["case_id"]), "polite", lang="hi-en", use_llm=False, today=TODAY)
    speech = " ".join(d.speech)
    assert "तेरह हज़ार रुपये" in speech and "चार हज़ार रुपये" in speech
    assert "₹" not in speech
    assert "शर्मा जी" in speech


async def test_firm_has_due_date_and_work_log():
    ids = make_case(diary_days=5)
    d = await compose(_ctx(ids["case_id"]), "firm", lang="hi-en", use_llm=False, today=TODAY)
    assert "7 सितंबर 2026" in d.text         # first unpaid wage (August) was due by 7 September
    assert "Kaam Diary" in d.text and "5 दिन" in d.text
    te = await compose(_ctx(ids["case_id"]), "firm", lang="te-IN", use_llm=False, today=TODAY)
    assert "5 రోజుల" in te.text


async def test_formal_cites_law_and_legal_aid_without_threats():
    ids = make_case()
    for lang in ("hi-en", "te-IN", "en"):
        d = await compose(_ctx(ids["case_id"]), "formal", lang=lang, use_llm=False, today=TODAY)
        assert "G.O.Ms.No.6" in d.text
        assert "17" in d.text
        assert "15100" in d.text and "1800 833 9020" in d.text and "DLSA" in d.text
        low = d.text.lower()
        for bad in ("penalt", "jail", "police", "10x", "ten times", "guarantee", "compensation"):
            assert bad not in low
        assert not messages.forbidden_terms(d.text)


async def test_male_worker_hinglish_formal_uses_masculine_verbs():
    ids = make_case(worker_name="Rafiq", worker_lang="hi-en", employer_name="Rao garu", employer_lang="te-IN")
    hi = await compose(_ctx(ids["case_id"]), "formal", lang="hi-en", use_llm=False, today=TODAY)
    assert "लूँगा" in hi.text and "लूँगी" not in hi.text
    te = await compose(_ctx(ids["case_id"]), "polite", use_llm=False, today=TODAY)   # employer language
    assert te.lang == "te-IN" and "రావు గారు" in te.text and "రఫీక్" in te.text


async def test_shortfall_not_included_is_not_claimed():
    ids = make_case(shortfall_info=2500.0)
    d = await compose(_ctx(ids["case_id"]), "polite", lang="en", use_llm=False, today=TODAY)
    assert "2,500" not in d.text and d.checks["ok"]


def test_verify_amounts_catches_a_wrong_number():
    ok, info = verify_amounts(["कुल ₹13,000 बाकी हैं।"], "hi-en", [13000, 4000], 13000)
    assert ok
    ok, info = verify_amounts(["कुल ₹14,000 बाकी हैं।"], "hi-en", [13000, 4000], 13000)
    assert not ok and info["unexpected"] == [14000]
    ok, info = verify_amounts(["మొత్తం పద్నాలుగు వేల రూపాయలు బాకీ."], "te-IN", [13000], 13000)
    assert not ok
    # helplines and the G.O. number are not money
    ok, _ = verify_amounts(["NALSA 15100, India Labourline 1800 833 9020, G.O.Ms.No.6, total ₹13,000"], "en",
                           [13000], 13000)
    assert ok


def test_split_sentences_keeps_citations():
    s = split_sentences("Under G.O.Ms.No.6 and s.17, pay by the 7th. Rs. 4,000 a month! ठीक है। Thanks.")
    assert s == ["Under G.O.Ms.No.6 and s.17, pay by the 7th.", "Rs. 4,000 a month!", "ठीक है।", "Thanks."]


def test_upi_link_format():
    assert messages.upi_link("lakshmi.demo@upi", "Lakshmi", 13000) == \
        "upi://pay?pa=lakshmi.demo@upi&pn=Lakshmi&am=13000&cu=INR&tn=Baaki"
    assert "am=615.50" in messages.upi_link("a@b", "A B", 615.5)
    assert messages.upi_link(None, "x", 1) is None


# --------------------------------------------------------------------------- LLM path
def _llm_returns(monkeypatch, sentences):
    monkeypatch.setattr(config, "groq_key", lambda: "gk")
    calls = []

    async def fake_json_call(system, user, schema, *, name="result", validate=None, **kw):
        calls.append(json.loads(user))
        out = {"sentences": sentences}
        try:
            return validate(out) if validate else out
        except Exception:
            return None

    monkeypatch.setattr(llm, "json_call", fake_json_call)
    return calls


async def test_llm_wording_used_when_slots_and_amounts_check(monkeypatch):
    calls = _llm_returns(monkeypatch, [
        "नमस्ते {employer}, उम्मीद है आप ठीक हैं।",
        "मेरी {months_list} की salary अभी बाकी है।",
        "कुल {total} बाकी हैं, कृपया {reply_by} तक दे दीजिए। धन्यवाद।",
    ])
    ids = make_case()
    d = await compose(_ctx(ids["case_id"]), "polite", lang="hi-en", use_llm=True, today=TODAY)
    assert calls and "draft_sentences" in calls[0]
    assert d.source == "llm"
    assert "उम्मीद है आप ठीक हैं" in d.text and "₹13,000" in d.text
    assert d.text.startswith("यह एक AI वॉइस संदेश है")     # disclosure added by code, not the LLM


async def test_llm_polite_cannot_use_law_or_legal_aid_slots(monkeypatch):
    _llm_returns(monkeypatch, ["నమస్కారం {employer}, మొత్తం {total} బాకీ ఉంది.",
                               "{reply_by} లోపు ఇవ్వండి, లేకపోతే {legal_aid} సహాయం తీసుకోవచ్చు."])
    ids = make_case(worker_name="Rafiq", worker_lang="hi-en", employer_name="Rao garu", employer_lang="te-IN")
    d = await compose(_ctx(ids["case_id"]), "polite", use_llm=True, today=TODAY)
    assert d.source == "template" and "NALSA" not in d.text and "15100" not in d.text


@pytest.mark.parametrize("bad", [
    ["नमस्ते {employer}, कुल ₹14,000 बाकी हैं, {reply_by} तक दीजिए।", "{total}"],    # invents digits
    ["नमस्ते {employer}, कुल चौदह हज़ार रुपये हैं।", "{total} {reply_by} तक दीजिए।"],  # invents a number in words
    ["नमस्ते {employer}, {total} नहीं दिए तो पुलिस आएगी, {reply_by} तक।", "धन्यवाद।"],  # threat
    ["नमस्ते {employer}, {bonus} भी दीजिए।", "{total} {reply_by}"],                   # unknown slot
    ["नमस्ते {employer}।", "धन्यवाद।"],                                                 # drops the total
])
async def test_llm_bad_output_falls_back_to_template(monkeypatch, bad):
    _llm_returns(monkeypatch, bad)
    ids = make_case()
    d = await compose(_ctx(ids["case_id"]), "polite", lang="hi-en", use_llm=True, today=TODAY)
    assert d.source == "template"
    assert d.checks["ok"]
    assert "14,000" not in d.text and "पुलिस" not in d.text and "चौदह" not in d.text


# --------------------------------------------------------------------------- voice note
def _tts_handler(ogg, seen):
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


async def test_voice_note_one_call_per_sentence_tagged_and_cached(mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_handler(short_ogg, seen)
    note = await voice_note.make_voice_note(["पहला वाक्य।", "दूसरा वाक्य।", "तीसरा।"], "hi-en", worker_name="Lakshmi")
    assert len(seen) == 3 and note.gnani_calls == 3
    assert all(b["model"] == "timbre-v3.0" and b["voice"] == "Shivani" and b["language"] == "hi-en" for b in seen)
    tags = audio.read_tags(note.data, "ogg")
    assert tags["comment"].startswith("AI-generated voice") and f"ID={note.id}" in tags["comment"]
    assert tags["id"] == note.id
    p = audio.probe(note.data, "ogg")
    assert p.codec == "opus" and p.channels == "mono" and p.sample_rate == 48000
    one = audio.probe(short_ogg, "ogg").duration_s
    assert note.duration_s >= 3 * one + 2 * 0.3 - 0.15          # three clips plus two 300 ms gaps
    again = await voice_note.make_voice_note(["पहला वाक्य।", "दूसरा वाक्य।", "तीसरा।"], "hi-en")
    assert again.gnani_calls == 0 and again.cache_hits == 3 and len(seen) == 3


async def test_voice_note_loudness_is_normalised(mock_gnani):
    from .conftest import make_wav

    quiet_wav = make_wav([("tone", 2.0)])
    import struct
    pcm = audio.pcm16k(quiet_wav, "wav")
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    soft = struct.pack(f"<{len(samples)}h", *[int(x * 0.05) for x in samples])  # about -26 dB
    soft_ogg = audio.to_ogg_opus(audio.wav_from_pcm(soft), "wav")
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(soft_ogg)
    note = await voice_note.make_voice_note(["एक।"], "hi-en")

    def peak(data):
        raw = audio._convert(data, "ogg", "raw", ["-ac", "1", "-ar", "16000", "-f", "s16le", "-c:a", "pcm_s16le"])
        return max(abs(v) for v in struct.unpack(f"<{len(raw) // 2}h", raw))

    assert peak(note.data) > 3 * peak(soft_ogg)


async def test_voice_note_uses_clone_only_with_embedding(mock_gnani):
    from .conftest import make_wav

    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, content=make_wav([("tone", 1.0)]), headers={"content-type": "audio/wav"})

    mock_gnani.default["/api/v1/tts/inference"] = handler
    emb = {"embedding": "abc" * 100, "shape": [1, 768], "dtype": "torch.bfloat16"}
    note = await voice_note.make_voice_note(["<excited> एक।", "दो।"], "hi-en", embedding=emb, worker_name="Lakshmi")
    assert note.voice_mode == "clone" and len(seen) == 2
    assert all(b["model"] == "vachana-vc-v1" and "voice" not in b and "language" not in b for b in seen)
    assert seen[0]["text"] == "एक।"                   # audio tags never reach VC
    assert "cloned voice" in audio.read_tags(note.data)["comment"]
    assert voice_note.vc_cache_dir(emb).exists()
    assert voice_note.purge_vc_cache(emb) and not voice_note.vc_cache_dir(emb).exists()


# --------------------------------------------------------------------------- PDFs
@pytest.mark.parametrize("worker_lang,employer_lang", [("te-IN", "hi-en"), ("hi-en", "te-IN"), ("te-IN", "en")])
async def test_formal_letter_pdf_renders_all_scripts(worker_lang, employer_lang):
    ids = make_case(worker_lang=worker_lang, employer_lang=employer_lang,
                    transcript="మూడు నెలల జీతం ఇవ్వలేదు" if worker_lang == "te-IN" else "तीन महीने की salary नहीं मिली")
    ctx = _ctx(ids["case_id"])
    d = await compose(ctx, "formal", use_llm=False, today=TODAY)
    en = await compose(ctx, "formal", lang="en", use_llm=False, today=TODAY)
    data = letter.render(letter.LetterInput(ctx=ctx, step="formal", draft=d, draft_en=en, today=TODAY,
                                            upi_link=messages.upi_link("lakshmi.demo@upi", "Lakshmi", 13000)))
    assert data[:5] == b"%PDF-" and data.rstrip().endswith(b"%%EOF")
    assert int(re.search(rb"/Count (\d+)", data).group(1)) >= 2      # letter + diary annex
    assert b"NotoSans" in data
    if "te-IN" in (worker_lang, employer_lang):
        assert b"NotoSansTelugu" in data
    if "hi-en" in (worker_lang, employer_lang):
        assert b"NotoSansDevanagari" in data


async def test_card_pdf_polite_and_legal_pack():
    ids = make_case()
    ctx = _ctx(ids["case_id"])
    d = await compose(ctx, "polite", use_llm=False, today=TODAY)
    card = letter.render(letter.LetterInput(ctx=ctx, step="polite", draft=d, today=TODAY))
    assert card[:5] == b"%PDF-"
    pack = letter.render_legal_pack(letter.LetterInput(ctx=ctx, step="legal_pack", today=TODAY,
                                                       statement_translation="Three months' salary not paid."))
    assert pack[:5] == b"%PDF-" and b"NotoSansTelugu" in pack


# --------------------------------------------------------------------------- routes
def test_message_route_polite_without_gnani_still_returns_text_and_pdf(client):
    ids = make_case()
    r = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["source"] == "template" and b["language"] == "hi-en"
    assert "₹13,000" in b["text"] and b["audio"] is None
    assert b["audio_error"]["code"] == "NOT_CONFIGURED"
    assert b["upi_link"].startswith("upi://pay?pa=lakshmi.demo@upi&pn=Lakshmi&am=13000&cu=INR&tn=Baaki")
    assert b["text_worker_lang"].startswith("ఇది AI వాయిస్ సందేశం")     # what Lakshmi sees, in Telugu
    pdf = client.get(b["pdf_url"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert b["employer_url"].endswith("/e/" + ids["token"])


def test_message_route_with_mocked_tts_and_reuse(client, mock_gnani, short_ogg):
    seen = []
    mock_gnani.default["/api/v1/tts/inference"] = _tts_handler(short_ogg, seen)
    ids = make_case()
    r = client.post(f"/api/cases/{ids['case_id']}/messages/firm", json={"use_llm": False})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["audio"]["voice_mode"] == "stock" and b["audio"]["voice"] == "Shivani"
    assert b["audio"]["gnani_calls"] == len(b["speech"]) == len(seen)
    a = client.get(b["audio_url"])
    assert a.status_code == 200 and a.headers["content-type"] == "audio/ogg"
    assert audio.read_tags(a.content)["id"] == b["voice_note_id"]
    r2 = client.post(f"/api/cases/{ids['case_id']}/messages/firm", json={"use_llm": False})
    assert r2.json()["reused"] is True and r2.json()["message_id"] == b["message_id"] and len(seen) == len(b["speech"])
    r3 = client.post(f"/api/cases/{ids['case_id']}/messages/firm", json={"use_llm": False, "regenerate": True})
    assert r3.json()["reused"] is False and len(seen) == len(b["speech"])     # TTS cache: no new calls
    sent = client.post(f"/api/messages/{b['message_id']}/sent").json()
    assert sent["status"] == "sent" and sent["sent_at"]
    listing = client.get(f"/api/cases/{ids['case_id']}/messages").json()["messages"]
    assert [m["step"] for m in listing] == ["firm", "firm"]


def test_message_route_errors(client):
    ids = make_case()
    assert client.post(f"/api/cases/{ids['case_id']}/messages/angry").status_code == 404
    assert client.post("/api/cases/999/messages/polite").status_code == 404
    r = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"voice": "clone", "use_llm": False})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "no_voice_profile"
    assert client.get("/api/media/../../etc/passwd").status_code == 404


def test_legal_pack_route(client):
    ids = make_case()
    client.post(f"/api/cases/{ids['case_id']}/messages/formal", json={"use_llm": False, "audio": False})
    r = client.get(f"/api/cases/{ids['case_id']}/legal-pack")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert r.headers["content-type"] == "application/pdf"
