"""Voice notes for the employer (and alerts for the worker).

- One sentence per Gnani call, joined with 300 ms gaps (VC speech has no pauses of its own,
  04_gnani_feasibility.md test 1; for stock Timbre it also means each sentence is cached on its own,
  so the disclosure and greeting are never synthesised twice).
- Stock Timbre v3.0 voice by default (through tts_cache). Only a worker with an opted-in
  VoiceProfile (consent=true) gets vc_tts with her stored embedding.
- Loudness normalised (ffmpeg loudnorm, -16 LUFS): Shivani v3 is about 7 dB quieter than the others.
- Written as Ogg/Opus with the AI label in the metadata: COMMENT=AI-generated voice ... ID=<uuid>,
  plus a separate ID tag (IT Rules 2026 provenance; 02_law section 6).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from . import audio, config, gnani, tts_cache
from .gnani import TTS_MODEL_V3

SR = 48000
GAP_S = 0.3
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


@dataclass
class VoiceNote:
    id: str
    data: bytes
    duration_s: float
    voice_mode: str                 # stock | clone
    voice: str                      # Timbre voice name, or "worker-clone"
    lang: str
    sentences: list[str]
    gnani_calls: int = 0
    cache_hits: int = 0
    comment: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def embedding_fingerprint(embedding: dict[str, Any]) -> str:
    return hashlib.sha256(str(embedding.get("embedding", "")).encode()).hexdigest()[:24]


def vc_cache_dir(embedding: dict[str, Any] | None = None, fingerprint: str | None = None) -> Path:
    fp = fingerprint or embedding_fingerprint(embedding or {})
    return config.DATA_DIR / "vc_cache" / fp


def purge_vc_cache(embedding: dict[str, Any] | None = None, fingerprint: str | None = None) -> bool:
    """Delete every clip spoken in a cloned voice (run when the worker deletes her profile)."""
    d = vc_cache_dir(embedding, fingerprint)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


async def _vc_clip(text: str, embedding: dict[str, Any]) -> tuple[bytes, bool]:
    d = vc_cache_dir(embedding)
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    p = d / f"{key}.wav"
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes(), True
    wav = await gnani.get_client().vc_tts(text, embedding)
    d.mkdir(parents=True, exist_ok=True)
    p.write_bytes(wav)
    return wav, False


def _pcm(data: bytes, ext: str) -> bytes:
    return audio._convert(data, ext, "raw", ["-ac", "1", "-ar", str(SR), "-f", "s16le", "-c:a", "pcm_s16le"])


def assemble(clips: list[tuple[bytes, str]], tags: dict[str, str], gap_s: float = GAP_S,
             normalise: bool = True) -> tuple[bytes, float]:
    """Join clips with silence, normalise loudness, encode Ogg/Opus with metadata tags."""
    if not clips:
        raise audio.AudioError("no clips")
    gap = b"\x00\x00" * int(SR * gap_s)
    parts: list[bytes] = []
    for i, (data, ext) in enumerate(clips):
        if i:
            parts.append(gap)
        parts.append(_pcm(data, ext))
    wav = audio.wav_from_pcm(b"".join(parts), SR)
    args = ["-ac", "1"]
    if normalise:
        args += ["-af", LOUDNORM]
    args += ["-ar", str(SR), "-c:a", "libopus", "-b:a", "32k", "-vbr", "on", "-application", "voip",
             "-map_metadata", "-1"]
    for k, v in tags.items():
        args += ["-metadata", f"{k}={v}"]
    out = audio._convert(wav, "wav", "ogg", args + ["-f", "ogg"])
    return out, float(audio.probe(out, "ogg").duration_s or 0.0)


def ai_comment(note_id: str, worker_name: str | None, voice_mode: str, purpose: str = "voice note") -> str:
    who = f" on behalf of {worker_name}" if worker_name else ""
    how = "cloned voice, with the worker's consent" if voice_mode == "clone" else "stock Timbre voice"
    return f"AI-generated voice. Baaki app {purpose}{who} ({how}). ID={note_id}"


async def make_voice_note(sentences: list[str], lang: str, *, worker_name: str | None = None,
                          embedding: dict[str, Any] | None = None, voice: str | None = None,
                          note_id: str | None = None, purpose: str = "voice note",
                          gap_s: float = GAP_S) -> VoiceNote:
    """Synthesise `sentences` (one Gnani call each, cached) and return one tagged Ogg/Opus note.

    lang is a Timbre language code (hi-en, te-IN, hi-IN, en-IN). With `embedding`, the cloned voice
    is used (vachana-vc-v1 has no language field and no audio tags)."""
    sentences = [s.strip() for s in sentences if s and s.strip()]
    if not sentences:
        raise ValueError("no text to speak")
    note_id = note_id or str(uuid.uuid4())
    mode = "clone" if embedding else "stock"
    clips: list[tuple[bytes, str]] = []
    calls = hits = 0
    v = voice or tts_cache.default_voice(lang)
    for s in sentences:
        if embedding:
            if "<" in s:  # audio tags are a Timbre v3.0 feature; never let VC read them aloud
                s = re.sub(r"<[a-z ]+>", "", s).strip()
            data, hit = await _vc_clip(s, embedding)
            clips.append((data, "wav"))
        else:
            entry = await tts_cache.synth(s, lang, v, fmt="ogg", model=TTS_MODEL_V3)
            data, hit = await run_in_threadpool(entry.path.read_bytes), entry.cached
            clips.append((data, "ogg"))
        hits += int(hit)
        calls += int(not hit)
    comment = ai_comment(note_id, worker_name, mode, purpose)
    tags = {"COMMENT": comment, "ID": note_id, "TITLE": f"Baaki {purpose}", "ARTIST": "Baaki app (AI voice)"}
    data, dur = await run_in_threadpool(assemble, clips, tags, gap_s)
    return VoiceNote(id=note_id, data=data, duration_s=round(dur, 3), voice_mode=mode,
                     voice="worker-clone" if embedding else v, lang=lang, sentences=sentences,
                     gnani_calls=calls, cache_hits=hits, comment=comment)


def load_embedding(profile) -> dict[str, Any] | None:
    """VoiceProfile.embedding_json -> the {embedding, shape, dtype} dict, or None."""
    if profile is None or not getattr(profile, "consent", False):
        return None
    try:
        emb = json.loads(profile.embedding_json or "null")
    except ValueError:
        return None
    if isinstance(emb, dict) and emb.get("embedding"):
        return emb
    return None
