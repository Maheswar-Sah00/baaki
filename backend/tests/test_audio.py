import pytest

from app import audio


def test_probe_wav(short_wav):
    p = audio.probe(short_wav, "wav")
    assert p.codec == "pcm_s16le"
    assert p.sample_rate == 16000
    assert abs(p.duration_s - 3.3) < 0.05
    assert abs(audio.duration_s(short_wav, "wav") - 3.3) < 0.05


def test_to_ogg_opus_is_whatsapp_shaped(short_wav):
    ogg = audio.to_ogg_opus(short_wav, "wav")
    assert ogg[:4] == b"OggS"
    p = audio.probe(ogg, "ogg")
    assert p.codec == "opus" and p.channels == "mono" and "ogg" in p.container
    assert abs(p.duration_s - 3.3) < 0.1


def test_whatsappify_compresses(short_wav):
    wa = audio.whatsappify(short_wav, "wav")
    hi = audio.to_ogg_opus(short_wav, "wav", bitrate="64k")
    assert wa[:4] == b"OggS"
    assert audio.probe(wa, "ogg").codec == "opus"
    assert len(wa) < len(hi)


def test_to_wav16k_and_mp3(short_ogg):
    wav = audio.to_wav16k(short_ogg, "ogg")
    p = audio.probe(wav, "wav")
    assert (p.codec, p.sample_rate) == ("pcm_s16le", 16000)
    mp3 = audio.to_mp3(short_ogg, "ogg")
    assert audio.probe(mp3, "mp3").codec == "mp3"


def test_remux_opus_extension(short_ogg):
    # WhatsApp shares voice notes as .opus: same Ogg bytes, different extension
    out = audio.remux_to_ogg(short_ogg, "opus")
    assert out[:4] == b"OggS"
    assert audio.probe(out, "ogg").codec == "opus"


def test_garbage_raises():
    with pytest.raises(audio.AudioError):
        audio.probe(b"not audio at all" * 10, "ogg")
    with pytest.raises(audio.AudioError):
        audio.to_wav16k(b"", "wav")


def test_plan_cuts_short_is_single():
    assert audio.plan_cuts(12.0, []) == [(0.0, 12.0)]


def test_plan_cuts_prefers_silence():
    cuts = audio.plan_cuts(60.0, [(19.0, 20.0), (40.0, 41.0)])
    assert cuts == [(0.0, 19.5), (19.5, 40.5), (40.5, 60.0)]


def test_plan_cuts_hard_fallback():
    cuts = audio.plan_cuts(70.0, [])
    assert cuts == [(0.0, 28.0), (28.0, 56.0), (56.0, 70.0)]
    assert all(e - s <= 28.0 for s, e in cuts)


def test_plan_cuts_ignores_silence_too_early():
    # a pause at 1 s would make a tiny first chunk; min_len_s=3 skips it
    cuts = audio.plan_cuts(40.0, [(0.8, 1.2), (25.0, 26.0)])
    assert cuts[0] == (0.0, 25.5)


def test_split_on_silence_real_audio(long_wav):
    chunks = audio.split_on_silence(long_wav, "wav")
    assert len(chunks) == 3
    assert all(c["end_s"] - c["start_s"] <= 28.0 for c in chunks)
    assert abs(chunks[0]["end_s"] - 20.5) < 0.3     # cut inside the first long pause
    assert abs(chunks[1]["end_s"] - 45.2) < 0.4     # and inside the second
    total = sum(audio.duration_s(c["audio"], "wav") for c in chunks)
    assert abs(total - audio.duration_s(long_wav, "wav")) < 0.05


def test_prepare_for_stt_passthrough_short_ogg(short_ogg):
    chunks, total = audio.prepare_for_stt(short_ogg, "note.ogg")
    assert len(chunks) == 1 and chunks[0]["audio"] == short_ogg and chunks[0]["filename"].endswith(".ogg")
    assert abs(total - 3.3) < 0.1


def test_prepare_for_stt_converts_webm(short_wav):
    webm = audio._convert(short_wav, "wav", "webm", ["-c:a", "libopus", "-b:a", "24k", "-f", "webm"])
    chunks, total = audio.prepare_for_stt(webm, "rec.webm")
    assert len(chunks) == 1 and chunks[0]["filename"].endswith(".wav")
    assert audio.probe(chunks[0]["audio"], "wav").sample_rate == 16000
    assert abs(total - 3.3) < 0.15


def test_prepare_for_stt_long_is_split(long_wav):
    chunks, total = audio.prepare_for_stt(long_wav, "long.wav")
    assert len(chunks) == 3 and abs(total - 65.35) < 0.1


def test_concat_with_gaps(short_wav, short_ogg):
    out = audio.concat_with_gaps([(short_wav, "wav"), (short_ogg, "ogg")], gap_s=1.0)
    assert abs(audio.duration_s(out, "wav") - (3.3 + 1.0 + 3.3)) < 0.15
