"""Opt-in voice profile: a Gnani voice-clone embedding of the worker's own voice.

- Only with explicit consent=true. Without it nothing is processed. The API reaches create_profile only
  through the spoken consent check (consent_flow.attempt); never on a public deploy (CloningDisabled).
- The recording (10-20 s) is converted in memory / a temp dir that is deleted at once, sent to the
  embeddings endpoint, and discarded. Only the embedding is stored (VoiceProfile.embedding_json).
- Delete removes the profile row and every cached clip spoken in the cloned voice.
- The default everywhere is a stock Timbre voice; a profile only changes the employer voice note.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from . import audio, gnani, voice_note
from .db import now_iso
from .gnani import VC_MODEL
from .models import VoiceProfile, Worker

MIN_S = 10.0
MAX_S = 20.0
TOLERANCE_S = 0.5      # a 9.6 s recording is fine; anything past 20 s is trimmed to 20 s
MAX_UPLOAD_S = 60.0

CONSENT_TEXT = {
    "te-IN": "మీ గొంతుతో యజమానికి సందేశం పంపడానికి, మీ 10–20 సెకన్ల రికార్డింగ్ నుండి ఒక వాయిస్ ప్రొఫైల్ తయారు చేస్తాము. "
             "రికార్డింగ్ దాచము, ప్రొఫైల్ మాత్రమే ఉంచుతాము. ప్రతి సందేశం AI సందేశం అని ముందే చెబుతుంది. ఎప్పుడైనా తొలగించవచ్చు.",
    "hi-en": "आपकी आवाज़ में employer को message भेजने के लिए, आपकी 10–20 second की recording से एक voice profile बनेगी। "
             "Recording रखी नहीं जाती, सिर्फ़ profile रहती है। हर message पहले बताता है कि यह AI संदेश है। आप इसे कभी भी delete कर सकती हैं।",
    "en": "To send messages to your employer in your own voice, we make a voice profile from a 10-20 second recording. "
          "The recording is not kept, only the profile. Every message says first that it is an AI message. Delete it any time.",
}


class ConsentRequired(ValueError):
    pass


class CloningDisabled(Exception):
    """Voice cloning is switched off on a public deploy (BAAKI_PUBLIC=1)."""


def check_cloning_enabled() -> None:
    from . import security

    if not security.cloning_enabled():
        raise CloningDisabled("Voice cloning is switched off on the public demo. Messages use a stock voice.")


@dataclass
class ProfileResult:
    profile: VoiceProfile
    duration_s: float
    trimmed: bool


def consent_text(lang: str | None) -> str:
    from .messages import norm_lang

    return CONSENT_TEXT[norm_lang(lang)]


def active_profile(s: Session, worker_id: int) -> VoiceProfile | None:
    return s.exec(select(VoiceProfile).where(VoiceProfile.worker_id == worker_id, VoiceProfile.consent == True)  # noqa: E712
                  .order_by(VoiceProfile.id.desc())).first()


def _prepare(data: bytes, filename: str) -> tuple[bytes, float, bool]:
    """Any upload -> 24 kHz mono 16-bit WAV (the verified reference format), max 20 s."""
    ext = audio.ext_of(filename) or "bin"
    dur = audio.probe(data, ext).duration_s
    if dur is None:
        raise ValueError("could not read the recording length")
    if dur < MIN_S - TOLERANCE_S:
        raise ValueError(f"recording is {dur:.1f} s; record at least {MIN_S:.0f} seconds")
    if dur > MAX_UPLOAD_S:
        raise ValueError(f"recording is {dur:.1f} s; keep it under {MAX_S:.0f} seconds")
    trimmed = dur > MAX_S + TOLERANCE_S
    args = ["-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le"]
    if trimmed:
        args = ["-t", f"{MAX_S}"] + args
    wav = audio._convert(data, ext, "wav", args + ["-f", "wav"])
    return wav, min(dur, MAX_S), trimmed


async def create_profile(s: Session, worker_id: int, consent: bool, data: bytes, filename: str) -> ProfileResult:
    check_cloning_enabled()
    if consent is not True:
        raise ConsentRequired("explicit consent=true is required to make a voice profile")
    if s.get(Worker, worker_id) is None:
        raise LookupError("worker not found")
    if not data:
        raise ValueError("empty audio")
    wav, dur, trimmed = await run_in_threadpool(_prepare, data, filename)
    emb = await gnani.get_client().vc_embedding(wav, "reference.wav")
    del wav, data  # the recording is never written to storage
    delete_profiles(s, worker_id, commit=False)
    prof = VoiceProfile(worker_id=worker_id, consent=True, consent_at=now_iso(),
                        embedding_json=json.dumps(emb), model=VC_MODEL, duration_s=round(dur, 2))
    s.add(prof)
    s.commit()
    s.refresh(prof)
    return ProfileResult(prof, dur, trimmed)


def delete_profiles(s: Session, worker_id: int, commit: bool = True) -> int:
    """Remove every profile of this worker and the cached clips spoken in that voice."""
    rows = list(s.exec(select(VoiceProfile).where(VoiceProfile.worker_id == worker_id)))
    for p in rows:
        emb = voice_note.load_embedding(p) or _raw_embedding(p)
        if emb:
            voice_note.purge_vc_cache(emb)
        s.delete(p)
    if commit:
        s.commit()
    return len(rows)


def _raw_embedding(p: VoiceProfile) -> dict[str, Any] | None:
    try:
        e = json.loads(p.embedding_json or "null")
    except ValueError:
        return None
    return e if isinstance(e, dict) and e.get("embedding") else None


def public_view(p: VoiceProfile | None, worker_lang: str | None = None) -> dict[str, Any]:
    """What the API shows: never the embedding itself."""
    out: dict[str, Any] = {"exists": p is not None, "consent_text": consent_text(worker_lang),
                           "default_voice": "stock Timbre voice"}
    if p is not None:
        try:
            shape = json.loads(p.embedding_json).get("shape")
        except Exception:
            shape = None
        out.update({"profile_id": p.id, "worker_id": p.worker_id, "consent": p.consent, "consent_at": p.consent_at,
                    "model": p.model, "duration_s": p.duration_s, "embedding_shape": shape,
                    "stored": "embedding only", "audio_stored": False})
    return out
