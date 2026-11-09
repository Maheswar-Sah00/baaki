"""Disk cache for Timbre TTS, keyed by sha256(voice|lang|text) (mp3 adds "|mp3", v2.5 adds "|timbre-v2.5").

A text is never synthesised twice. Lookup order:
  1. backend/data/tts_cache (runtime, gitignored)
  2. backend/seed_cache/tts (committed: the demo's pre-rendered audio, so a cold deploy spends nothing)
Files: {key}.ogg (or .mp3) plus {key}.json with model, voice, lang, text and duration.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from . import audio, config, gnani, security
from .gnani import DEFAULT_VOICE, DEFAULT_VOICE_V25, TTS_MODEL_V3

SYNTH_CALLS = {"count": 0}  # real Timbre calls made through this cache (budget tracking)
_locks: dict[str, asyncio.Lock] = {}


@dataclass
class Entry:
    key: str
    path: Path
    duration_s: float
    cached: bool
    fmt: str = "ogg"
    # (No `url`: there is no /api/tts-cache route. Callers serve cached audio through their own routes,
    # e.g. /api/consent/audio/{key}.ogg and /api/exit/audio/{key}.ogg, or copy it into /api/media.)


def cache_key(text: str, lang: str, voice: str, fmt: str = "ogg", model: str = TTS_MODEL_V3) -> str:
    base = f"{voice}|{lang}|{text}" + ("" if fmt == "ogg" else f"|{fmt}") + ("" if model == TTS_MODEL_V3 else f"|{model}")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def default_voice(lang: str, model: str = TTS_MODEL_V3) -> str:
    table = DEFAULT_VOICE if model == TTS_MODEL_V3 else DEFAULT_VOICE_V25
    return table.get(lang) or ("Shivani" if model == TTS_MODEL_V3 else "Nalini")


def _dirs() -> list[Path]:
    return [config.tts_cache_dir(), config.SEED_CACHE_DIR / "tts"]


def lookup(key: str, fmt: str = "ogg") -> Path | None:
    if not all(c in "0123456789abcdef" for c in key) or len(key) != 64:
        return None
    for d in _dirs():
        p = d / f"{key}.{fmt}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _meta(path: Path) -> dict:
    m = path.with_suffix(".json")
    try:
        return json.loads(m.read_text(encoding="utf-8"))
    except Exception:
        return {}


def duration_of(path: Path) -> float:
    meta = _meta(path)
    if meta.get("duration_s") is not None:
        return float(meta["duration_s"])
    try:
        return float(audio.probe(path.read_bytes(), path.suffix.lstrip(".")).duration_s or 0.0)
    except audio.AudioError:
        return 0.0


def finish(raw: bytes, fmt: str) -> tuple[bytes, float]:
    """Make sure the bytes are a voice note WhatsApp accepts; return (bytes, duration)."""
    info = audio.probe(raw, fmt)
    if fmt == "ogg" and not (info.codec == "opus" and info.channels == "mono" and info.container and "ogg" in info.container):
        raw = audio.to_ogg_opus(raw, "ogg", bitrate="24k", sample_rate=48000)
        info = audio.probe(raw, "ogg")
    return raw, float(info.duration_s or 0.0)


def _write(key: str, data: bytes, fmt: str, meta: dict) -> Path:
    d = config.tts_cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{key}.{fmt}"
    tmp = p.with_suffix(f".{fmt}.part")
    tmp.write_bytes(data)
    tmp.replace(p)
    p.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


async def synth(text: str, lang: str, voice: str | None = None, fmt: str = "ogg",
                model: str = TTS_MODEL_V3) -> Entry:
    """Cached Timbre synthesis. Raises gnani.GnaniError / ValueError / audio.AudioError on failure."""
    text = text.strip()
    voice = voice or default_voice(lang, model)
    key = cache_key(text, lang, voice, fmt, model)
    hit = lookup(key, fmt)
    if hit:
        return Entry(key, hit, duration_of(hit), True, fmt)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        hit = lookup(key, fmt)
        if hit:
            return Entry(key, hit, duration_of(hit), True, fmt)
        if not security.tts_live_allowed():  # public deploy: cache hits only outside the allowlist
            _locks.pop(key, None)
            raise security.cache_only_error()
        raw = await gnani.get_client().tts(text, lang, voice=voice, container=fmt, model=model)
        SYNTH_CALLS["count"] += 1
        data, dur = await run_in_threadpool(finish, raw, fmt)
        p = _write(key, data, fmt, {"model": model, "voice": voice, "lang": lang, "text": text, "fmt": fmt,
                                    "duration_s": round(dur, 3), "bytes": len(data)})
    _locks.pop(key, None)
    return Entry(key, p, dur, False, fmt)


def export_to_seed(key: str, fmt: str = "ogg") -> Path | None:
    """Copy a runtime cache entry into backend/seed_cache/tts (committed with the repo)."""
    src = lookup(key, fmt)
    if not src:
        return None
    dst_dir = config.SEED_CACHE_DIR / "tts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
        if src.with_suffix(".json").exists():
            shutil.copyfile(src.with_suffix(".json"), dst.with_suffix(".json"))
    return dst
