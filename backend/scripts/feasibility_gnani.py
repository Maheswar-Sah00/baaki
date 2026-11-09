"""Real-key feasibility test of three Gnani features for Baaki (voice clone, audio tags, numbers).

Every audio file lands in backend/data/feasibility/ with a descriptive name, and every result in
backend/data/feasibility/results.json. A step whose output already exists is skipped, so a re-run
spends no credits for finished steps. Calls are strictly sequential (1 active request per account).
Synthetic data only: the "worker" reference voice is itself a Timbre voice. The key is never printed.

  backend/.venv/Scripts/python.exe backend/scripts/feasibility_gnani.py t3a   # STT settings on smoke audio
  backend/.venv/Scripts/python.exe backend/scripts/feasibility_gnani.py t1    # cross-lingual voice clone
  backend/.venv/Scripts/python.exe backend/scripts/feasibility_gnani.py t2    # audio tags
  backend/.venv/Scripts/python.exe backend/scripts/feasibility_gnani.py t3b   # TTS amount formats
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import audio, config, gnani  # noqa: E402

OUT = BACKEND / "data" / "feasibility"
RESULTS = OUT / "results.json"
SMOKE_HINGLISH = BACKEND / "data" / "smoke" / "hinglish_tts.ogg"

# Synthetic reference script for the "worker" (fictional; ~17 s of natural Telugu).
TE_REFERENCE = (
    "నమస్తే, నా పేరు లక్ష్మి. నేను హైదరాబాద్‌లో మూడు ఇళ్లలో వంట పని, ఇంటి పని చేస్తాను. "
    "ప్రతి రోజు ఉదయం ఆరు గంటలకే బయలుదేరుతాను. పిల్లల్ని బడికి పంపించి, మళ్ళీ సాయంత్రం దాకా పని చేస్తాను. "
    "నా పని నాకు ఇష్టమే, కానీ జీతం సమయానికి రావాలి కదా. అందుకే ఈ యాప్ వాడుతున్నాను."
)
VC_TEXTS = {
    "hinglish_roman": "Yeh sandesh Lakshmi ki anumati se, unki awaaz mein, Baaki app ne banaya hai. Madam, namaste. "
                      "Meri teen mahine ki salary, total baarah hazaar rupaye, abhi tak baaki hai. "
                      "Kya aap is hafte de sakti hain? Dhanyavaad.",
    "hinglish_devanagari": "यह संदेश लक्ष्मी की अनुमति से, उनकी आवाज़ में, Baaki app ने बनाया है। मैडम, नमस्ते। "
                           "मेरी तीन महीने की salary, total बारह हज़ार रुपये, अभी तक बाकी है। "
                           "क्या आप इस हफ्ते दे सकती हैं? धन्यवाद।",
    "telugu": "అమ్మగారు, నా మూడు నెలల జీతం, మొత్తం పన్నెండు వేల రూపాయలు, ఇంకా బాకీ ఉంది.",
    "english": "Madam, my salary for three months, twelve thousand rupees in total, is still pending.",
}
TAG_TEXTS = {
    "hinglish_slow_readback": ("hi-en", "Shivani",
                               "<slow> Teen mahine <pauses> chaar hazaar har mahina <pauses> kul baarah hazaar rupaye. <pauses> Sahi hai?"),
    "hinglish_excited": ("hi-en", "Shivani", "<excited> Paisa aa gaya! Sharma ji ne baarah hazaar rupaye bhej diye."),
    "telugu_slow_readback": ("te-IN", "Kalpana",
                             "<slow> మూడు నెలలు, <pauses> నెలకు నాలుగు వేలు, <pauses> మొత్తం పన్నెండు వేలు. <pauses> సరేనా?"),
    "telugu_excited": ("te-IN", "Kalpana", "<excited> డబ్బులు వచ్చేశాయి!"),
}
# Test 3b: same smoke sentence, three amount spellings, two TTS set-ups.
SMOKE_TEXT = "Madam, मेरी तीन महीने की salary अभी तक नहीं मिली. Total बारह हज़ार रुपये बाकी हैं."
T3B = {
    "poorvi_v25_words_devanagari": ("timbre-v2.5", "Poorvi", SMOKE_TEXT),
    "shivani_v3_digits": ("timbre-v3.0", "Shivani", SMOKE_TEXT.replace("बारह हज़ार रुपये", "₹12,000")),
}


def load() -> dict:
    return json.loads(RESULTS.read_text("utf-8")) if RESULTS.exists() else {}


def save(res: dict) -> None:
    RESULTS.write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")


def silences(data: bytes, ext: str, min_s: float = 0.25) -> list[list[float]]:
    """[start, duration] of silences >= min_s (ffmpeg silencedetect, -35 dB)."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory(dir=str(config.TMP_DIR)) as d:
        p = Path(d) / f"a.{ext}"
        p.write_bytes(data)
        r = subprocess.run([audio.ffmpeg_exe(), "-nostdin", "-hide_banner", "-i", str(p), "-af",
                            f"silencedetect=noise=-35dB:d={min_s}", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", r.stderr)]
    return [[round(s, 2), round(d, 2)] for s, d in zip(starts, durs)]


def credit_headers(c: gnani.GnaniClient) -> dict:
    return {k: v for k, v in c.last_response_headers.items()
            if any(w in k.lower() for w in ("credit", "balance", "quota", "remaining", "usage", "cost"))}


async def stt(c, data: bytes, fname: str, lang: str, fmt: str, **kw) -> dict:
    t0 = time.perf_counter()
    try:
        body = await c.stt(data, fname, language_code=lang, fmt=fmt, **kw)
        return {"ok": True, "language_code": lang, "format": fmt, **({"keyterms": kw["keyterms"]} if "keyterms" in kw else {}),
                "latency_s": round(time.perf_counter() - t0, 2), "transcript": body.get("transcript"),
                "detected": body.get("detected_language_code"), "credit_headers": credit_headers(c)}
    except gnani.GnaniError as e:
        return {"ok": False, "language_code": lang, "format": fmt, "error": e.as_dict()}


async def tts_step(c, res: dict, key: str, path: Path, coro_fn, meta: dict) -> bytes | None:
    if path.exists():
        print(f"[{key}] cached {path.name}")
        return path.read_bytes()
    t0 = time.perf_counter()
    try:
        data = await coro_fn()
    except gnani.GnaniError as e:
        res[key] = {**meta, "ok": False, "error": e.as_dict(), "latency_s": round(time.perf_counter() - t0, 2)}
        print(f"[{key}] FAILED {e.as_dict()}")
        save(res)
        return None
    lat = round(time.perf_counter() - t0, 2)
    path.write_bytes(data)
    ext = path.suffix[1:]
    res[key] = {**meta, "ok": True, "latency_s": lat, "file": str(path), "bytes": len(data),
                "duration_s": audio.duration_s(data, ext), "silences": silences(data, ext),
                "credit_headers": credit_headers(c)}
    print(f"[{key}] ok {lat}s, {res[key]['duration_s']}s audio")
    save(res)
    return data


async def t3a(c, res):
    data = SMOKE_HINGLISH.read_bytes()
    out = res.setdefault("t3a", {})
    for name, lang, fmt, kw in [
        ("verbatim_hi_en", "hi-IN,en-IN", "verbatim", {}),
        ("codemix_hi_en", "hi-IN,en-IN", "codemix", {}),
        ("transcribe_hi_only", "hi-IN", "transcribe", {}),
    ]:
        if name in out and out[name].get("ok"):
            continue
        out[name] = await stt(c, data, "hinglish_tts.ogg", lang, fmt, **kw)
        print(name, json.dumps(out[name], ensure_ascii=False))
        save(res)


async def t1(c, res):
    out = res.setdefault("t1", {})
    ref_path = OUT / "t1_reference_lakshmi_telugu_kalpana_v3.wav"
    ref = await tts_step(c, out, "reference", ref_path,
                         lambda: c.tts(TE_REFERENCE, "te-IN", "Kalpana", container="wav", sample_rate=24000),
                         {"text": TE_REFERENCE, "voice": "Kalpana", "model": "timbre-v3.0", "language": "te-IN",
                          "audio_config": c.audio_config("wav", 24000)})
    if ref is None:
        return
    emb_path = OUT / "t1_speaker_embedding.json"
    if emb_path.exists():
        emb = json.loads(emb_path.read_text("utf-8"))
    else:
        t0 = time.perf_counter()
        try:
            emb = await c.vc_embedding(ref, ref_path.name)
        except gnani.GnaniError as e:
            out["embedding"] = {"ok": False, "error": e.as_dict()}
            save(res)
            print("embedding FAILED", e.as_dict())
            return
        emb_path.write_text(json.dumps(emb), "utf-8")
        out["embedding"] = {"ok": True, "latency_s": round(time.perf_counter() - t0, 2), "shape": emb["shape"],
                            "dtype": emb["dtype"], "embedding_chars": len(emb["embedding"]),
                            "reference_duration_s": out["reference"]["duration_s"], "credit_headers": credit_headers(c)}
        save(res)
        print("embedding", out["embedding"])
    for name, text in VC_TEXTS.items():
        p = OUT / f"t1_vc_{name}.wav"
        await tts_step(c, out, f"vc_{name}", p, lambda t=text: c.vc_tts(t, emb, container="wav", sample_rate=24000),
                       {"text": text, "model": "vachana-vc-v1", "audio_config": c.audio_config("wav", 24000)})
    # Transcribe the two Hinglish outputs (the demo's key line).
    for name in ("hinglish_roman", "hinglish_devanagari"):
        k = f"vc_{name}"
        p = OUT / f"t1_vc_{name}.wav"
        if p.exists() and "stt" not in out.get(k, {}):
            out[k]["stt"] = await stt(c, p.read_bytes(), p.name, "hi-IN,en-IN", "codemix")
            print(k, "heard:", out[k]["stt"].get("transcript"))
            save(res)


async def t2(c, res):
    out = res.setdefault("t2", {})
    for name, (lang, voice, text) in TAG_TEXTS.items():
        p = OUT / f"t2_tags_{name}_{voice.lower()}_v3.ogg"
        await tts_step(c, out, name, p, lambda t=text, l=lang, v=voice: c.tts(t, l, v, container="ogg"),
                       {"text": text, "voice": voice, "model": "timbre-v3.0", "language": lang})
    for name, lang, fmt in (("hinglish_slow_readback", "hi-IN,en-IN", "codemix"), ("telugu_slow_readback", "te-IN,en-IN", "verbatim")):
        r = out.get(name, {})
        if r.get("ok") and "stt" not in r:
            p = Path(r["file"])
            r["stt"] = await stt(c, p.read_bytes(), p.name, lang, fmt)
            print(name, "heard:", r["stt"].get("transcript"))
            save(res)


async def t3b(c, res, stt_fmt: str = "codemix"):
    out = res.setdefault("t3b", {})
    for name, (model, voice, text) in T3B.items():
        p = OUT / f"t3b_{name}.ogg"
        await tts_step(c, out, name, p, lambda t=text, m=model, v=voice: c.tts(t, "hi-en", v, container="ogg", model=m),
                       {"text": text, "voice": voice, "model": model, "language": "hi-en"})
        r = out.get(name, {})
        if r.get("ok") and "stt" not in r:
            r["stt"] = await stt(c, p.read_bytes(), p.name, "hi-IN,en-IN", stt_fmt)
            print(name, "heard:", r["stt"].get("transcript"))
            save(res)


async def main(steps: list[str]) -> int:
    if not config.gnani_key():
        print("GNANI_API_KEY is not set")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    c = gnani.GnaniClient(timeout_s=120.0, max_attempts=4)
    res = load()
    for s in steps:
        await {"t3a": t3a, "t1": t1, "t2": t2, "t3b": t3b}[s](c, res)
    st = gnani.STATS
    calls = res.setdefault("calls", {"stt": 0, "tts": 0, "vc_embed": 0, "vc_tts": 0})
    for k in calls:
        calls[k] += getattr(st, k)
    save(res)
    print("calls this run:", st)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:] or ["t3a", "t1", "t2", "t3b"])))
