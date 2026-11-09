"""Noise proof bench (G04+V14): the corpus, the audio degradations, the scoring and the summary.

Everything here is offline. The live run (Timbre for the clean clips, Prisma for the transcripts) is
done by backend/scripts/bench_noisy.py, which writes backend/data/bench/results.json; the route
app/routes/proof.py serves it.

Degradations use ffmpeg only (imageio-ffmpeg). No third-party noise recordings, so no licence question:
  kitchen_5db / kitchen_0db  synthetic kitchen: running tap (filtered pink + brown noise, wobbling),
                             a pressure-cooker whistle (a warbling ~2.9 kHz tone plus steam hiss)
                             and steel-vessel clatter bursts, mixed at 5 dB or 0 dB SNR
  phone                      8 kHz phone line: 300-3400 Hz band-pass, slight hard clipping, G.711 mu-law
  whatsapp                   WhatsApp-style voice note: Opus 12 kbps, mono, 16 kHz, VoIP mode
  combined                   kitchen 5 dB, then the phone line, then Opus 12 kbps
SNR = active-speech RMS (20 ms frames within 35 dB of the loudest frame) over the RMS of the noise bed.
"""
from __future__ import annotations

import difflib
import io
import math
import random
import re
import unicodedata
import wave
from array import array
from collections import Counter
from pathlib import Path
from typing import Any

from . import audio
from .lang.amounts import extract_amounts

SR = 16000  # working rate for mixing (Prisma resamples to 16 kHz anyway)

# --------------------------------------------------------------------------- corpus (synthetic)
# Fictional workers, fictional amounts. Amounts are written as words (as people say them); the
# expected values were checked against app.lang.amounts on the source text itself (see tests).
CORPUS: list[dict[str, Any]] = [
    {"id": "te01", "lang": "te", "tts_lang": "te-IN", "voice": "Kalpana",
     "text": "అమ్మగారు, మూడు నెలలుగా నెలకు నాలుగు వేలు జీతం ఇవ్వలేదు.",
     "gloss": "Madam, for three months you have not paid my salary of four thousand a month.",
     "expected": [4000]},
    {"id": "te02", "lang": "te", "tts_lang": "te-IN", "voice": "Lakshmi",
     "text": "మేడం, నాకు పన్నెండు వేల రూపాయలు బాకీ ఉంది, రెండు వేలు మాత్రమే ఇచ్చారు.",
     "gloss": "Madam, I am owed twelve thousand rupees; you only gave two thousand.",
     "expected": [12000, 2000]},
    {"id": "te03", "lang": "te", "tts_lang": "te-IN", "voice": "Vasudha",
     "text": "ఈ నెల జీతం ఆరు వేలు, కానీ ఐదు వందలు కట్ చేశారు.",
     "gloss": "This month's salary is six thousand, but they cut five hundred.",
     "expected": [6000, 500]},
    {"id": "te04", "lang": "te", "tts_lang": "te-IN", "voice": "Chetana",
     "text": "రెండు రోజులు జ్వరం వచ్చిందని వెయ్యి రూపాయలు కోత పెట్టారు.",
     "gloss": "Because I had fever for two days, they cut a thousand rupees.",
     "expected": [1000]},
    {"id": "te05", "lang": "te", "tts_lang": "te-IN", "voice": "Devansh",
     "text": "పండగ అడ్వాన్స్ మూడు వేల ఐదు వందలు తీసుకున్నాను, మిగతా జీతం ఇవ్వాలి.",
     "gloss": "I took a festival advance of three thousand five hundred; the rest of the salary is due.",
     "expected": [3500]},
    {"id": "te06", "lang": "te", "tts_lang": "te-IN", "voice": "Prakash",
     "text": "అయ్యగారు ఎనిమిది వేలు ఇస్తానన్నారు, ఇప్పటికి నాలుగు వేల ఐదు వందలు వచ్చింది.",
     "gloss": "Sir promised eight thousand; so far four thousand five hundred has come.",
     "expected": [8000, 4500]},
    {"id": "hi01", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Shivani",
     "text": "मैडम, तीन महीने की salary बाकी है, हर महीने सात हज़ार।",
     "gloss": "Madam, three months of salary are pending, seven thousand each month.",
     "expected": [7000]},
    {"id": "hi02", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Riyaa",
     "text": "दो दिन बीमार थी तो एक हज़ार काट लिया।",
     "gloss": "I was sick for two days, so they cut one thousand.",
     "expected": [1000]},
    {"id": "hi03", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Tarika",
     "text": "Sir ने ढाई हज़ार advance दिया था, बाकी नौ हज़ार अभी तक नहीं मिला।",
     "gloss": "Sir gave an advance of two and a half thousand; the remaining nine thousand has not come.",
     "expected": [2500, 9000]},
    {"id": "hi04", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Kalpana",
     "text": "मेरी पगार पाँच हज़ार है, पर इस बार सिर्फ़ साढ़े तीन हज़ार दिए।",
     "gloss": "My pay is five thousand, but this time they gave only three and a half thousand.",
     "expected": [5000, 3500]},
    {"id": "hi05", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Shubham",
     "text": "Diwali का bonus पंद्रह सौ रुपये बोला था, वो भी नहीं दिया।",
     "gloss": "They promised a Diwali bonus of fifteen hundred rupees; that wasn't paid either.",
     "expected": [1500]},
    {"id": "hi06", "lang": "hinglish", "tts_lang": "hi-en", "voice": "Yashraj",
     "text": "कुल ग्यारह हज़ार रुपये बाकी हैं, अगले हफ़्ते तक दे दो।",
     "gloss": "Eleven thousand rupees in total are owed; please pay by next week.",
     "expected": [11000]},
]
CORPUS_BY_ID = {u["id"]: u for u in CORPUS}

CONDITIONS: dict[str, dict[str, Any]] = {
    "clean": {"label": "Quiet room", "short": "Clean", "snr_db": None, "ext": "ogg",
              "desc": "The stock-voice clip as made, no added noise."},
    "kitchen_5db": {"label": "Kitchen, 5 dB", "short": "Kitchen 5 dB", "snr_db": 5.0, "ext": "wav",
                    "desc": "Running tap, pressure-cooker whistle and clattering steel at 5 dB SNR."},
    "kitchen_0db": {"label": "Loud kitchen, 0 dB", "short": "Kitchen 0 dB", "snr_db": 0.0, "ext": "wav",
                    "desc": "The same kitchen, as loud as the voice (0 dB SNR)."},
    "phone": {"label": "Phone line", "short": "Phone line", "snr_db": None, "ext": "wav",
              "desc": "8 kHz call audio: 300-3400 Hz band, slight clipping, mu-law."},
    "whatsapp": {"label": "WhatsApp voice note", "short": "WhatsApp", "snr_db": None, "ext": "ogg",
                 "desc": "Opus at 12 kbps, mono: a heavily compressed voice note."},
    "combined": {"label": "Kitchen + phone + WhatsApp", "short": "All at once", "snr_db": 5.0, "ext": "ogg",
                 "desc": "Kitchen at 5 dB, then the phone line, then 12 kbps Opus."},
}
HARDEST = "combined"
PHRASE = {"kitchen_5db": "a kitchen at 5 dB", "kitchen_0db": "a kitchen as loud as the voice",
          "phone": "a phone line", "whatsapp": "WhatsApp compression",
          "combined": "kitchen + phone line + WhatsApp at once"}


def _join(xs: list[str]) -> str:
    return "; ".join(xs)
CONDITION_ORDER = ["clean", "kitchen_5db", "kitchen_0db", "phone", "whatsapp", "combined"]
LANG_LABEL = {"te": "Telugu", "hinglish": "Hinglish"}


def clip_id(utt_id: str, condition: str) -> str:
    return f"{utt_id}-{condition.replace('_', '')}"


def parse_clip_id(cid: str) -> tuple[str, str] | None:
    utt, _, cond = cid.partition("-")
    for c in CONDITIONS:
        if c.replace("_", "") == cond and utt in CORPUS_BY_ID:
            return utt, c
    return None


# --------------------------------------------------------------------------- PCM helpers (stdlib only)
def decode_pcm(data: bytes, ext: str, sr: int = SR) -> array:
    """Decode any audio to mono s16 samples at ``sr``."""
    raw = audio._convert(data, ext, "raw", ["-ac", "1", "-ar", str(sr), "-f", "s16le", "-c:a", "pcm_s16le"])
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    return a


def wav_bytes(samples: array, sr: int = SR) -> bytes:
    return audio.wav_from_pcm(samples.tobytes(), sr)


def wav_info(data: bytes) -> dict[str, int]:
    with wave.open(io.BytesIO(data), "rb") as w:
        return {"sample_rate": w.getframerate(), "channels": w.getnchannels(), "sample_width": w.getsampwidth(),
                "frames": w.getnframes()}


def rms(samples) -> float:
    if not len(samples):
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def active_rms(samples: array, sr: int = SR, frame_ms: int = 20, floor_db: float = 35.0) -> float:
    """RMS over speech-active frames: frames within ``floor_db`` of the loudest frame."""
    n = max(1, sr * frame_ms // 1000)
    frames = [rms(samples[i:i + n]) for i in range(0, len(samples) - n + 1, n)]
    if not frames:
        return rms(samples)
    top = max(frames)
    if top <= 0:
        return 0.0
    gate = top * 10 ** (-floor_db / 20)
    act = [f for f in frames if f >= gate]
    return math.sqrt(sum(f * f for f in act) / len(act))


def snr_db(speech: array, noise: array, sr: int = SR) -> float:
    return 20 * math.log10(active_rms(speech, sr) / max(rms(noise), 1e-9))


# --------------------------------------------------------------------------- kitchen noise (ffmpeg lavfi)
def kitchen_noise(duration_s: float, seed: int = 7, sr: int = SR) -> array:
    """A synthetic kitchen bed: tap water + one pressure-cooker whistle + 3-4 clatter bursts."""
    rnd = random.Random(seed)
    d = max(1.0, float(duration_s))
    # whistle: starts in the first half so it lands on the words, lasts ~1.6-2.4 s
    w0 = round(rnd.uniform(0.15, 0.45) * d, 3)
    w1 = round(min(d - 0.1, w0 + rnd.uniform(1.6, 2.4)), 3)
    f0 = rnd.choice([2750, 2850, 2950])
    env = f"between(t,{w0},{w1})*min(1,(t-{w0})*5)*min(1,({w1}-t)*3)"
    whistle = (f"aevalsrc='{env}*(0.55*sin(2*PI*{f0}*t+3*sin(2*PI*6.5*t))"
               f"+0.18*sin(4*PI*{f0}*t+6*sin(2*PI*6.5*t))+0.35*(random(0)-0.5))'"
               f":s={sr}:d={d}")
    hits = sorted(round(rnd.uniform(0.05, 0.95) * d, 3) for _ in range(rnd.choice([3, 4])))
    clang = "+".join(
        f"gte(t,{h})*exp(-(t-{h})*{rnd.choice([22, 28, 35])})"
        f"*(0.6*sin(2*PI*{rnd.choice([1180, 1370, 1520])}*t)+0.45*sin(2*PI*{rnd.choice([2230, 2470])}*t)"
        f"+0.3*sin(2*PI*{rnd.choice([3710, 4120])}*t)+0.5*(random(1)-0.5))" for h in hits)
    clatter = f"aevalsrc='{clang}':s={sr}:d={d}"
    water = (f"anoisesrc=color=pink:amplitude=0.6:seed={seed}:r={sr}:d={d},"
             f"highpass=f=350,lowpass=f=6500,tremolo=f={rnd.choice([3.1, 4.3, 5.2])}:d=0.35")
    rumble = f"anoisesrc=color=brown:amplitude=0.5:seed={seed + 1}:r={sr}:d={d},lowpass=f=260"
    graph = (f"{water}[a];{rumble}[b];{whistle}[c];{clatter}[e];"
             f"[a][b][c][e]amix=inputs=4:weights=1 0.6 0.9 0.7:normalize=0:duration=longest,"
             f"aformat=sample_fmts=s16:channel_layouts=mono[out]")
    with audio._tmpdir() as tmp:
        dst = Path(tmp) / "noise.raw"
        p = audio._run(["-y", "-filter_complex", graph, "-map", "[out]", "-ar", str(sr), "-f", "s16le",
                        "-c:a", "pcm_s16le", str(dst)])
        if p.returncode != 0 or not dst.exists():
            tail = p.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
            raise audio.AudioError("ffmpeg noise failed: " + " | ".join(tail))
        a = array("h")
        raw = dst.read_bytes()
        a.frombytes(raw[: len(raw) // 2 * 2])
    return a


def mix_at_snr(speech: array, noise: array, target_db: float, sr: int = SR, lead_s: float = 0.4) -> tuple[array, float]:
    """Pad the speech with ``lead_s`` of noise either side and mix at ``target_db`` SNR.
    The whole mix is scaled down if it would clip, which keeps the SNR. Returns (mix, measured SNR)."""
    lead = int(lead_s * sr)
    n = len(speech) + 2 * lead
    if len(noise) < n:
        reps = n // max(1, len(noise)) + 1
        noise = array("h", noise * reps)
    noise = noise[:n]
    s_level = active_rms(speech, sr)
    n_level = max(rms(noise), 1e-9)
    gain = s_level / (n_level * 10 ** (target_db / 20))
    padded = [0] * lead + list(speech) + [0] * lead
    mix = [p + gain * x for p, x in zip(padded, noise)]
    peak = max(1.0, max(abs(v) for v in mix))
    scale = min(1.0, 32000.0 / peak)
    out = array("h", (int(round(v * scale)) for v in mix))
    scaled_noise = array("h", (int(round(gain * scale * x)) for x in noise))
    measured = 20 * math.log10(active_rms(speech, sr) * scale / max(rms(scaled_noise), 1e-9))
    return out, round(measured, 2)


def kitchen(data: bytes, ext: str, target_db: float, seed: int = 7) -> tuple[bytes, float]:
    """Clean clip -> 16 kHz WAV with kitchen noise at ``target_db`` SNR. Returns (wav, measured SNR)."""
    speech = decode_pcm(data, ext, SR)
    noise = kitchen_noise(len(speech) / SR + 0.8, seed=seed)
    mix, measured = mix_at_snr(speech, noise, target_db)
    return wav_bytes(mix, SR), measured


def phone_line(data: bytes, ext: str) -> bytes:
    """8 kHz narrowband call: band-pass 300-3400 Hz, about 2 dB of hard clipping, G.711 mu-law.
    Returns a 16-bit PCM WAV at 8 kHz (decoded from the mu-law, as a call recording would be)."""
    pcm = decode_pcm(data, ext, SR)
    peak = max(1, max((abs(s) for s in pcm), default=1))
    # push the peaks ~25% past full scale, then hard-clip at 0.95: only the loudest syllables clip
    gain = 1.25 * 32767 / peak
    af = (f"aformat=sample_fmts=flt,highpass=f=300,highpass=f=300,lowpass=f=3400,lowpass=f=3400,"
          f"volume={gain:.4f},asoftclip=type=hard:threshold=0.95")
    mulaw = audio._convert(wav_bytes(pcm, SR), "wav", "wav",
                           ["-af", af, "-ac", "1", "-ar", "8000", "-c:a", "pcm_mulaw", "-f", "wav"])
    return audio._convert(mulaw, "wav", "wav", ["-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", "-f", "wav"])


def whatsapp(data: bytes, ext: str, bitrate: str = "12k") -> bytes:
    """WhatsApp-style voice note: Ogg Opus, mono, 16 kHz, VoIP mode, ``bitrate`` (12-16 kbps)."""
    return audio.to_ogg_opus(data, ext, bitrate=bitrate, sample_rate=16000)


def degrade(clean: bytes, clean_ext: str, condition: str, seed: int = 7) -> tuple[bytes, str, float | None]:
    """Make one condition from the clean clip. Returns (bytes, ext, measured SNR or None)."""
    if condition == "clean":
        return clean, clean_ext, None
    if condition in ("kitchen_5db", "kitchen_0db"):
        wav, snr = kitchen(clean, clean_ext, CONDITIONS[condition]["snr_db"], seed=seed)
        return wav, "wav", snr
    if condition == "phone":
        return phone_line(clean, clean_ext), "wav", None
    if condition == "whatsapp":
        return whatsapp(clean, clean_ext), "ogg", None
    if condition == "combined":
        wav, snr = kitchen(clean, clean_ext, CONDITIONS["combined"]["snr_db"], seed=seed)
        return whatsapp(phone_line(wav, "wav"), "wav"), "ogg", snr
    raise ValueError(f"unknown condition {condition!r}")


# --------------------------------------------------------------------------- scoring
def score(expected: list[int], transcript: str, lang: str, said: str | None = None) -> dict[str, Any]:
    """Exact match per expected amount (multiset), using the app's own parser on the transcript."""
    found = extract_amounts(transcript or "", lang)
    left = Counter(int(a["amount_inr"]) for a in found)
    hits = []
    for e in expected:
        ok = left[e] > 0
        if ok:
            left[e] -= 1
        hits.append({"amount": int(e), "heard": ok})
    extras = list(left.elements())
    want = Counter(int(e) for e in expected)
    spans = []
    for a in found:
        v = int(a["amount_inr"])
        ok = want[v] > 0
        if ok:
            want[v] -= 1
        spans.append({"start": a["start"], "end": a["end"], "amount": v, "text": a["source_text"], "match": ok})
    n_hit = sum(h["heard"] for h in hits)
    return {"heard": [int(a["amount_inr"]) for a in found], "amounts": hits, "hits": n_hit, "total": len(expected),
            "extras": extras, "spans": spans, "match": n_hit == len(expected) and not extras,
            "word_slips": word_slips(said, transcript) if said is not None else []}


_PUNCT = re.compile(r"[\s,.;:!?।॥\"'()\-]+")


def _words(text: str) -> list[str]:
    return [w for w in _PUNCT.split(unicodedata.normalize("NFC", text or "").lower()) if w]


def word_slips(said: str, heard: str) -> list[dict[str, str]]:
    """Words where the transcript differs from the script (spelling or script changes count too)."""
    a, b = _words(said), _words(heard)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            out.append({"said": " ".join(a[i1:i2]), "heard": " ".join(b[j1:j2])})
    return out


def _pct(a: int, b: int) -> float | None:
    return round(100.0 * a / b, 1) if b else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Exact-amount rate per condition and overall, plus every miss."""
    done = [r for r in rows if r.get("transcript") is not None and not r.get("error")]
    per: list[dict[str, Any]] = []
    for c in CONDITION_ORDER:
        rs = [r for r in done if r["condition"] == c]
        if not rs:
            continue
        hits = sum(r["hits"] for r in rs)
        total = sum(r["total"] for r in rs)
        lat = [r["latency_s"] for r in rs if r.get("latency_s") is not None]
        per.append({"condition": c, "label": CONDITIONS[c]["label"], "short": CONDITIONS[c]["short"],
                    "desc": CONDITIONS[c]["desc"], "snr_db": CONDITIONS[c]["snr_db"],
                    "clips": len(rs), "clips_exact": sum(1 for r in rs if r["match"]),
                    "amounts": total, "exact": hits, "rate": _pct(hits, total),
                    "extras": sum(len(r.get("extras") or []) for r in rs),
                    "by_lang": {lg: {"exact": sum(r["hits"] for r in rs if r["lang"] == lg),
                                     "amounts": sum(r["total"] for r in rs if r["lang"] == lg)}
                                for lg in ("te", "hinglish") if any(r["lang"] == lg for r in rs)},
                    "median_latency_s": round(sorted(lat)[len(lat) // 2], 2) if lat else None})
    noisy = [r for r in done if r["condition"] != "clean"]
    misses = []
    for r in done:
        missed = [a["amount"] for a in r["amounts"] if not a["heard"]]
        if missed or r.get("extras"):
            misses.append({"clip_id": r["clip_id"], "utt_id": r["utt_id"], "condition": r["condition"],
                           "lang": r["lang"], "missed": missed, "extras": r.get("extras") or [],
                           "transcript": r["transcript"]})
    overall = {"clips": len(done), "amounts": sum(r["total"] for r in done), "exact": sum(r["hits"] for r in done)}
    overall["rate"] = _pct(overall["exact"], overall["amounts"])
    noisy_all = {"clips": len(noisy), "amounts": sum(r["total"] for r in noisy), "exact": sum(r["hits"] for r in noisy)}
    noisy_all["rate"] = _pct(noisy_all["exact"], noisy_all["amounts"])
    hard = next((p for p in per if p["condition"] == HARDEST), None)
    headline = None
    if noisy_all["amounts"]:
        names = [PHRASE[p["condition"]] for p in per if p["condition"] != "clean"]
        headline = {"exact": noisy_all["exact"], "amounts": noisy_all["amounts"], "clips": noisy_all["clips"],
                    "rate": noisy_all["rate"], "conditions": [p["condition"] for p in per if p["condition"] != "clean"],
                    "text": (f"Baaki heard {noisy_all['exact']} of {noisy_all['amounts']} rupee amounts exactly "
                             f"in {noisy_all['clips']} noisy clips (" + _join(names) + ")."),
                    "hardest": ({"condition": HARDEST, "exact": hard["exact"], "amounts": hard["amounts"],
                                 "text": (f"{hard['exact']} of {hard['amounts']} with kitchen noise, a phone line "
                                          f"and WhatsApp compression all at once.")} if hard else None)}
    slips = sum(len(r.get("word_slips") or []) for r in done)
    return {"headline": headline, "per_condition": per, "overall": overall, "noisy": noisy_all, "misses": misses,
            "word_slips": slips, "clips_with_word_slips": sum(1 for r in done if r.get("word_slips"))}
