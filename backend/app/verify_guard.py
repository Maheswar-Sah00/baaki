"""Listen-twice guard (G07): Prisma re-hears the voice note before the worker shares it.

The note was spoken by Timbre (or her opted-in clone). Before Lakshmi sends it, Prisma STT
transcribes the generated audio and we check two things:

1. every rupee amount written in the message (and so the total) is heard, and nothing else is;
2. the spoken AI disclosure is heard at the start of the note.

The result only warns. The worker can always send (02_law section 8; FINAL_TOP5 judge condition:
"on a mismatch it warns and still lets her send; it never silently blocks").

STT settings (docs/research/04_gnani_feasibility.md, test 3): Hinglish hi-IN,en-IN and Telugu
te-IN,en-IN, both with `codemix`, so numbers stay as words and app.lang turns them into rupees
(`transcribe` with two languages dropped "बारह"). Notes run about 29 s; stt_service splits anything
over 28 s at a pause, so the 30 s REST limit is never hit.

Results are cached per (message, audio sha256) as JSON under backend/data/verify/, so a repeat
check of the same audio costs no Gnani credits.
"""
from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from . import config, stt_service
from .lang._text import norm_deva, norm_telu
from .messages import DISCLOSURE, amounts_in, disclosure, norm_lang

# Message language -> (stt_service preset, mode). Multi-language lists always use codemix.
STT_SETTINGS = {
    "hi-en": ("hinglish", "codemix"),   # hi-IN,en-IN
    "te-IN": ("te", "codemix"),         # te-IN,en-IN
    "en": ("en-IN", "transcribe"),      # one language: digits are safe
}
WINDOW_WORDS = 15          # the disclosure must be heard within the first ~15 words (plus its length)
DISCLOSURE_MIN = 0.6       # share of disclosure words heard
TOKEN_SIM = 0.75           # per-word fuzzy match (ASR spelling drift: संदेश / सन्देश)

# Words Prisma writes in more than one way. Each maps to one canonical token.
CANON = {
    "ai": "ai", "एआई": "ai", "ए.आई": "ai", "ए.आई.": "ai", "ఏఐ": "ai", "ఎఐ": "ai", "ఏ.ఐ": "ai", "a.i": "ai",
    "a.i.": "ai",
    "voice": "voice", "वॉइस": "voice", "वाइस": "voice", "वॉयस": "voice", "वोइस": "voice", "वायस": "voice",
    "వాయిస్": "voice", "వాయిసు": "voice",
    "baaki": "baaki", "baki": "baaki", "बाकी": "baaki", "बाक़ी": "baaki", "बाक़ि": "baaki", "బాకీ": "baaki",
    "బాకి": "baaki",
    "app": "app", "ऐप": "app", "एप": "app", "ऍप": "app", "एप्प": "app", "యాప్": "app", "ఆప్": "app",
    "message": "message", "मैसेज": "message", "मेसेज": "message", "మెసేజ్": "message",
}
# Spaced spellings joined before tokenising ("ए आई" -> "ai").
SPACED = [(re.compile(r"(?<!\S)ए\s*\.?\s*आई\.?(?!\S)"), " ai "), (re.compile(r"(?<!\S)ఏ\s*\.?\s*ఐ\.?(?!\S)"), " ai "),
          (re.compile(r"(?<![A-Za-z])a\s*\.\s*i\s*\.?(?![A-Za-z])", re.I), " ai ")]
_WORD = re.compile(r"[A-Za-z0-9ऀ-ॣॱ-ॿఀ-౿‌‍.]+")


# --------------------------------------------------------------------------- disclosure matching
def _norm_token(w: str) -> str:
    w = unicodedata.normalize("NFC", w.strip(".").lower())
    if not w:
        return ""
    if re.search(r"[ऀ-ॿ]", w):
        w = norm_deva(w)
    elif re.search(r"[ఀ-౿]", w):
        w = norm_telu(w)
    return CANON.get(w, w)


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text or "")
    for rx, rep in SPACED:
        t = rx.sub(rep, t)
    out = [_norm_token(m.group(0)) for m in _WORD.finditer(t)]
    return [w for w in out if w and w != "."]


def _similar(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 3:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= TOKEN_SIM


def disclosure_match(expected: str, transcript: str, window: int = WINDOW_WORDS) -> dict[str, Any]:
    """Token-overlap ratio of the expected disclosure against the first words of the transcript."""
    exp = tokens(expected)
    head = tokens(transcript)[: max(window, len(exp) + 5)]
    pool = list(head)
    hit = 0
    for w in exp:
        for i, h in enumerate(pool):
            if _similar(w, h):
                hit += 1
                pool.pop(i)
                break
    score = round(hit / len(exp), 3) if exp else 0.0
    ai_heard = "ai" in head
    return {"score": score, "ai_word_heard": ai_heard, "heard": bool(ai_heard and score >= DISCLOSURE_MIN),
            "expected_words": len(exp)}


def expected_disclosure(text: str, worker_name: str | None, lang: str) -> str:
    """The disclosure this message starts with (stock or clone wording), else the stock one."""
    lang = norm_lang(lang)
    name = worker_name or ""
    for mode in ("clone", "stock"):
        d = disclosure(name, lang, mode)
        if name and text.startswith(d):
            return d
    # unknown worker name: use the template's first sentence without the name slot
    first = re.split(r"(?<=[।.])\s+", text.strip(), maxsplit=1)[0] if text.strip() else ""
    if first and "AI" in first:
        return first
    return DISCLOSURE[(lang, "stock")].format(worker=name)


# --------------------------------------------------------------------------- amounts
def amounts_of(text: str, lang: str, mask: list[str] | None = None) -> list[int]:
    return [int(round(a)) for a in amounts_in(text or "", lang, mask or [])]


def compare_amounts(expected: list[int], heard: list[int]) -> dict[str, Any]:
    """Multiset comparison: missing = said in the text but not heard; extra = heard but not written."""
    ce, ch = Counter(expected), Counter(heard)
    missing = sorted((ce - ch).elements())
    extra = sorted((ch - ce).elements())
    return {"ok": not missing and not extra, "missing": missing, "extra": extra}


def pick_total(expected: list[int], balance: float | None) -> int | None:
    if not expected:
        return None
    if balance and int(round(balance)) in expected:
        return int(round(balance))
    return max(expected)


# --------------------------------------------------------------------------- cache
def cache_dir() -> Path:
    return config.DATA_DIR / "verify"


def cache_path(message_id: int, audio_sha: str) -> Path:
    return cache_dir() / f"m{int(message_id)}_{audio_sha[:16]}.json"


def read_cache(message_id: int, audio_sha: str | None = None) -> dict[str, Any] | None:
    d = cache_dir()
    if audio_sha:
        paths = [cache_path(message_id, audio_sha)]
    else:
        paths = sorted(d.glob(f"m{int(message_id)}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if d.exists() else []
    for p in paths:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None


def write_cache(message_id: int, audio_sha: str, result: dict[str, Any]) -> None:
    p = cache_path(message_id, audio_sha)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


_locks: dict[str, asyncio.Lock] = {}


def lock_for(key: str) -> asyncio.Lock:
    lk = _locks.get(key)
    if lk is None:
        lk = _locks[key] = asyncio.Lock()
    return lk


# --------------------------------------------------------------------------- the check
async def listen_twice(audio_bytes: bytes, filename: str, *, text: str, lang: str,
                       worker_name: str | None = None, balance: float | None = None,
                       mask: list[str] | None = None) -> dict[str, Any]:
    """Transcribe the note with Prisma and compare it with the message text. One STT call per
    <=28 s chunk (a ~29 s note may be split into two)."""
    lang = norm_lang(lang)
    preset, mode = STT_SETTINGS[lang]
    t0 = time.perf_counter()
    stt = await stt_service.transcribe_upload(audio_bytes, filename, lang=preset, mode=mode)
    ms = int(round((time.perf_counter() - t0) * 1000))
    transcript = stt.get("transcript") or ""
    expected = amounts_of(text, lang, mask)
    heard = amounts_of(transcript, lang, mask)
    cmp = compare_amounts(expected, heard)
    total = pick_total(expected, balance)
    disc = disclosure_match(expected_disclosure(text, worker_name, lang), transcript)
    return {
        "verified": bool(cmp["ok"] and disc["heard"] and expected),
        "amounts_ok": cmp["ok"],
        "amounts_expected": expected,
        "amounts_heard": heard,
        "missing": cmp["missing"],
        "extra": cmp["extra"],
        "total_expected": total,
        "total_heard": total is not None and total in heard,
        "disclosure_heard": disc["heard"],
        "disclosure_score": disc["score"],
        "ai_word_heard": disc["ai_word_heard"],
        "transcript": transcript,
        "language_code": stt.get("language_code"),
        "stt_mode": stt.get("mode"),
        "detected_language_code": stt.get("detected_language_code"),
        "message_language": lang,
        "duration_s": stt.get("duration_s"),
        "stt_calls": len(stt.get("chunks") or []),
        "ms": ms,
    }


def audio_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
