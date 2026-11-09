"""Noise proof bench (G04+V14): scoring, degradations and the /api/proof route. Offline, no Gnani."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import audio, config, proof_bench as pb
from app.main import app

from .conftest import make_wav


# --------------------------------------------------------------------------- corpus + scoring
def test_corpus_shape_and_parser_reads_every_source_text():
    assert len(pb.CORPUS) == 12
    assert sum(u["lang"] == "te" for u in pb.CORPUS) == 6
    assert sum(u["lang"] == "hinglish" for u in pb.CORPUS) == 6
    assert len({u["voice"] for u in pb.CORPUS}) >= 8
    for u in pb.CORPUS:
        assert 1 <= len(u["expected"]) <= 2
        s = pb.score(u["expected"], u["text"], u["lang"], said=u["text"])
        assert s["match"], (u["id"], s["heard"])
        assert s["word_slips"] == []


def test_score_exact_miss_and_extra():
    ok = pb.score([12000, 2000], "मैडम बारह हज़ार बाकी है, दो हज़ार ही दिए", "hinglish")
    assert ok["hits"] == 2 and ok["total"] == 2 and ok["match"] and ok["extras"] == []
    assert [s["match"] for s in ok["spans"]] == [True, True]

    miss = pb.score([12000, 2000], "मैडम हज़ार बाकी है, दो हज़ार ही दिए", "hinglish")  # dropped "बारह"
    assert miss["hits"] == 1 and not miss["match"]
    assert [a["heard"] for a in miss["amounts"]] == [False, True]
    assert miss["extras"] == [1000]
    assert [s["match"] for s in miss["spans"]] == [False, True]

    nothing = pb.score([4000], "", "te")
    assert nothing["hits"] == 0 and nothing["heard"] == [] and not nothing["match"]


def test_score_is_a_multiset_match():
    s = pb.score([1000, 1000], "ek hazaar advance diya, ek hazaar kaat liya", "hinglish")
    assert s["hits"] == 2 and s["match"]
    s = pb.score([1000, 1000], "ek hazaar", "hinglish")
    assert s["hits"] == 1 and not s["match"]


def test_score_telugu_words():
    s = pb.score([3500], "పండగ అడ్వాన్స్ మూడు వేల ఐదు వందలు తీసుకున్నాను", "te")
    assert s["match"]


def test_word_slips_ignore_punctuation_but_list_changes():
    assert pb.word_slips("मैडम, सात हज़ार।", "मैडम सात हज़ार") == []
    slips = pb.word_slips("పండగ అడ్వాన్స్ మూడు వేల", "అండగా అడ్వాన్స్ మూడు వేల")
    assert slips == [{"said": "పండగ", "heard": "అండగా"}]


def _row(utt, cond, expected, transcript, lang="hinglish"):
    r = {"clip_id": pb.clip_id(utt, cond), "utt_id": utt, "condition": cond, "lang": lang, "latency_s": 0.8,
         "expected": expected, "transcript": transcript, "error": None, "text": transcript}
    r.update(pb.score(expected, transcript, lang))
    return r


def test_summarize_rates_misses_and_headline():
    rows = [
        _row("hi01", "clean", [7000], "हर महीने सात हज़ार"),
        _row("hi01", "combined", [7000], "हर महीने सात हज़ार"),
        _row("hi02", "combined", [1000, 9000], "एक हज़ार काट लिया, नौ बाकी"),  # 9000 missed
        _row("hi02", "kitchen_0db", [1000], "एक हज़ार"),
        {"clip_id": "hi03-phone", "utt_id": "hi03", "condition": "phone", "lang": "hinglish",
         "transcript": None, "error": "500 X", "expected": [1], "hits": 0, "total": 1, "amounts": []},
    ]
    s = pb.summarize(rows)
    per = {p["condition"]: p for p in s["per_condition"]}
    assert set(per) == {"clean", "kitchen_0db", "combined"}  # errored row is not counted
    assert per["combined"]["exact"] == 2 and per["combined"]["amounts"] == 3 and per["combined"]["rate"] == 66.7
    assert per["combined"]["clips_exact"] == 1
    assert s["noisy"] == {"clips": 3, "amounts": 4, "exact": 3, "rate": 75.0}
    assert s["overall"]["amounts"] == 5 and s["overall"]["exact"] == 4
    assert s["headline"]["exact"] == 3 and s["headline"]["amounts"] == 4
    assert "3 of 4" in s["headline"]["text"]
    assert s["headline"]["hardest"]["exact"] == 2
    assert [m["clip_id"] for m in s["misses"]] == ["hi02-combined"]
    assert s["misses"][0]["missed"] == [9000]


def test_clip_ids_round_trip():
    for u in pb.CORPUS:
        for c in pb.CONDITIONS:
            assert pb.parse_clip_id(pb.clip_id(u["id"], c)) == (u["id"], c)
    assert pb.parse_clip_id("zz99-clean") is None
    assert pb.parse_clip_id("te01-nope") is None


# --------------------------------------------------------------------------- degradations
@pytest.fixture(scope="module")
def speechy_wav() -> bytes:
    return make_wav([("sil", 0.3), ("tone", 0.8), ("sil", 0.2), ("tone", 1.0), ("sil", 0.3)])


def test_kitchen_hits_the_target_snr(speechy_wav):
    for target in (5.0, 0.0):
        wav, measured = pb.kitchen(speechy_wav, "wav", target)
        info = pb.wav_info(wav)
        assert info["sample_rate"] == 16000 and info["channels"] == 1 and info["sample_width"] == 2
        assert abs(measured - target) < 0.6
        # 0.4 s of kitchen before and after the voice
        assert info["frames"] == pytest.approx(16000 * (2.6 + 0.8), abs=40)


def test_kitchen_noise_is_deterministic_and_not_silent():
    a = pb.kitchen_noise(1.5, seed=3)
    b = pb.kitchen_noise(1.5, seed=3)
    assert len(a) == pytest.approx(1.5 * 16000, abs=20)
    assert pb.rms(a) > 300
    assert a[:4000] == b[:4000]


def test_phone_line_is_8k_band_limited_wav(speechy_wav):
    out = pb.phone_line(speechy_wav, "wav")
    info = pb.wav_info(out)
    assert info["sample_rate"] == 8000 and info["channels"] == 1 and info["sample_width"] == 2
    assert audio.probe(out, "wav").duration_s == pytest.approx(2.6, abs=0.05)


def test_whatsapp_and_combined_are_low_bitrate_opus(speechy_wav):
    wa = pb.whatsapp(speechy_wav, "wav")
    p = audio.probe(wa, "ogg")
    assert p.codec == "opus" and p.channels == "mono"
    assert len(wa) < len(speechy_wav) / 10
    combined, ext, snr = pb.degrade(speechy_wav, "wav", "combined")
    assert ext == "ogg" and audio.probe(combined, "ogg").codec == "opus"
    assert snr == pytest.approx(5.0, abs=0.6)


def test_degrade_every_condition(speechy_wav):
    for c in pb.CONDITION_ORDER:
        b, ext, _ = pb.degrade(speechy_wav, "wav", c)
        assert ext == ("wav" if c == "clean" else pb.CONDITIONS[c]["ext"])
        assert audio.probe(b, ext).duration_s > 2.0
    with pytest.raises(ValueError):
        pb.degrade(speechy_wav, "wav", "underwater")


# --------------------------------------------------------------------------- route
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bench_fixture(speechy_wav):
    d = config.DATA_DIR / "bench"
    (d / "audio").mkdir(parents=True)
    rows = []
    for utt, cond, transcript in [("te01", "clean", "నెలకు నాలుగు వేలు జీతం"),
                                  ("te01", "combined", "నెలకు నాలుగు వేలు జీతం"),
                                  ("hi02", "combined", "दो दिन बीमार थी तो काट लिया")]:
        u = pb.CORPUS_BY_ID[utt]
        r = {"clip_id": pb.clip_id(utt, cond), "utt_id": utt, "lang": u["lang"], "voice": u["voice"],
             "condition": cond, "snr_db": 5.0 if cond == "combined" else None, "text": u["text"],
             "gloss": u["gloss"], "expected": u["expected"], "transcript": transcript, "latency_s": 0.8,
             "error": None}
        r.update(pb.score(u["expected"], transcript, u["lang"], said=u["text"]))
        rows.append(r)
    (d / "results.json").write_text(json.dumps({"version": 1, "updated_at": "2026-11-09T14:34:00+00:00",
                                                "settings": {"model": "prisma-v3.0"},
                                                "calls": {"tts": 2, "stt": 3, "runs": [{"at": "x"}]},
                                                "clips": rows}, ensure_ascii=False), encoding="utf-8")
    (d / "audio" / "te01-clean.ogg").write_bytes(audio.to_ogg_opus(speechy_wav, "wav"))
    (d / "audio" / "te01-combined.ogg").write_bytes(pb.whatsapp(speechy_wav, "wav"))
    (d / "audio" / "hi02-kitchen0db.wav").write_bytes(speechy_wav)
    return d


def test_proof_without_results(client):
    b = client.get("/api/proof").json()
    assert b["available"] is False and b["clips"] == [] and len(b["method"]) == 3


def test_proof_summary_and_rows(client, bench_fixture):
    r = client.get("/api/proof")
    assert r.status_code == 200
    b = r.json()
    assert b["available"] is True and b["calls"] == {"tts": 2, "stt": 3}
    assert [c["clip_id"] for c in b["clips"]] == ["hi02-combined", "te01-clean", "te01-combined"]
    s = b["summary"]
    assert s["noisy"] == {"clips": 2, "amounts": 2, "exact": 1, "rate": 50.0}
    assert s["misses"][0]["clip_id"] == "hi02-combined" and s["misses"][0]["missed"] == [1000]
    row = b["clips"][2]
    assert row["audio_url"] == "/api/proof/audio/te01-combined"
    assert row["clean_url"] == "/api/proof/audio/te01-clean"
    assert row["condition_label"] == pb.CONDITIONS["combined"]["label"]
    assert row["spans"][0]["amount"] == 4000 and row["spans"][0]["match"] is True
    assert row["word_slips"]  # the transcript is shorter than the script
    assert {c["id"] for c in b["conditions"]} == set(pb.CONDITIONS)


def test_proof_audio_serves_files(client, bench_fixture):
    r = client.get("/api/proof/audio/te01-combined")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/ogg"
    assert audio.probe(r.content, "ogg").codec == "opus"
    r = client.get("/api/proof/audio/hi02-kitchen0db")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert pb.wav_info(r.content)["sample_rate"] == 16000


def test_proof_audio_is_path_safe(client, bench_fixture):
    (config.DATA_DIR / "secret.ogg").write_bytes(b"x")
    for bad in ["..%2Fsecret", "te01-..", "te01-clean.ogg", "TE01-clean", "te01-nope", "zz99-clean",
                "results", "te01-clean%00"]:
        assert client.get(f"/api/proof/audio/{bad}").status_code == 404, bad
    assert client.get("/api/proof/audio/te06-phone").status_code == 404  # valid id, no file
