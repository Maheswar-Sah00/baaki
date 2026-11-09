"""G13: her spoken consent IS the voice sample. Orchestration on top of the existing clone flow.

  prompt   Timbre reads the consent sentence slowly (<slow>, <pauses>), through tts_cache (cached).
  attempt  one recording -> duration check (local) -> Prisma STT (codemix) -> consent_text.match
           -> if heard (or she confirms by tap): voice_profile.create_profile (the SAME audio is the
              clone sample) -> DiaryEntry(kind="consent") in her hash chain. The raw audio is never stored;
              only its sha256 goes into the diary.
  withdraw voice_profile.delete_profiles + DiaryEntry(kind="consent", "Voice consent withdrawn ...").

The gate never blocks (judge condition): a failed match, or STT being down, returns the matched / missed
words and lets her retry or confirm by tap; a tap is logged as method "tap". A tap is accepted only for a
recording (same sha256) that was first sent as a spoken attempt (status "spoken_first" otherwise), so a
client flag alone can never make a clone. POST /api/voice-profile goes through attempt(method="spoken").
On a public deploy (BAAKI_PUBLIC=1) cloning is off: CloningDisabled before any Gnani call.
"""
from __future__ import annotations

import re
import time
from typing import Any

from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from . import audio, db, tts_cache
from . import consent_text as ct
from . import voice_profile as vp
from .gnani import GnaniError
from .models import DiaryEntry, Worker
from .stt_service import transcribe_upload

METHODS = ("spoken", "tap")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ATTEMPT_TTL_S = 3600
_ATTEMPTS: dict[tuple[int, str], dict[str, Any]] = {}   # (worker_id, audio sha256) -> transcript + match; never audio


class TooShortOrLong(ValueError):
    def __init__(self, status: str, duration_s: float, message: str):
        super().__init__(message)
        self.status, self.duration_s, self.message = status, duration_s, message


# --------------------------------------------------------------------------- text + prompt
def text_view(worker: Worker, lang: str | None = None) -> dict[str, Any]:
    lg = ct.lang_for_worker(worker.language, lang)
    return {
        "worker_id": worker.id,
        "lang": lg,
        "tts_lang": ct.TTS_LANG[lg],
        "name": ct.display_name(worker.name, lg),
        "text": ct.consent_sentence(worker.name, lg),
        "sentences": ct.sentences(worker.name, lg),
        "meaning_en": ct.meaning_en(worker.name),
        "words": ct.blank_words(worker.name, lg),
        "rule": {"name_required": True, "content_ratio": ct.PASS_RATIO},
        "duration_hint_s": [vp.MIN_S, vp.MAX_S],
    }


def _prompt_key(worker: Worker, lg: str) -> tuple[str, str, str]:
    speech = ct.speech_text(worker.name, lg)
    tl = ct.TTS_LANG[lg]
    return speech, tl, tts_cache.cache_key(speech, tl, tts_cache.default_voice(tl))


def audio_url(key: str) -> str:
    return f"/api/consent/audio/{key}.ogg"


def cached_prompt(worker: Worker, lang: str | None = None) -> dict[str, Any] | None:
    lg = ct.lang_for_worker(worker.language, lang)
    _, _, key = _prompt_key(worker, lg)
    p = tts_cache.lookup(key)
    if not p:
        return None
    return {"audio_url": audio_url(key), "duration_s": round(tts_cache.duration_of(p), 2), "cached": True}


async def prompt(worker: Worker, lang: str | None = None) -> dict[str, Any]:
    """Timbre reads the sentence slowly so she can repeat it. Never raises: on a TTS error the screen
    still shows the words (audio_url None)."""
    lg = ct.lang_for_worker(worker.language, lang)
    speech, tl, _ = _prompt_key(worker, lg)
    base = {"lang": lg, "tts_lang": tl, "text": ct.consent_sentence(worker.name, lg), "speech": speech}
    try:
        e = await tts_cache.synth(speech, tl)
    except (GnaniError, ValueError, audio.AudioError) as err:
        info = err.as_dict() if isinstance(err, GnaniError) else {"message": str(err)}
        return {**base, "audio_url": None, "duration_s": None, "cached": False, "tts_error": info}
    return {**base, "audio_url": audio_url(e.key), "duration_s": round(e.duration_s, 2), "cached": e.cached, "tts_error": None}


# --------------------------------------------------------------------------- attempt
def _remember(worker_id: int, sha: str, data: dict[str, Any]) -> None:
    now = time.time()
    for k in [k for k, v in _ATTEMPTS.items() if now - v["at"] > ATTEMPT_TTL_S]:
        _ATTEMPTS.pop(k, None)
    if len(_ATTEMPTS) > 200:
        _ATTEMPTS.pop(next(iter(_ATTEMPTS)))
    _ATTEMPTS[(worker_id, sha)] = {**data, "at": now}


def _recall(worker_id: int, sha: str) -> dict[str, Any] | None:
    v = _ATTEMPTS.get((worker_id, sha))
    if v and time.time() - v["at"] <= ATTEMPT_TTL_S:
        return v
    return None


def check_duration(data: bytes, filename: str) -> float:
    """Local check before any Gnani call: the clone needs 10-20 s (longer is trimmed to 20 s)."""
    dur = audio.probe(data, audio.ext_of(filename) or "bin").duration_s
    if dur is None:
        raise ValueError("could not read the recording length")
    if dur < vp.MIN_S - vp.TOLERANCE_S:
        raise TooShortOrLong("too_short", dur, f"The recording is {dur:.1f} s. Read the whole sentence slowly "
                                               f"(at least {vp.MIN_S:.0f} seconds).")
    if dur > vp.MAX_UPLOAD_S:
        raise TooShortOrLong("too_long", dur, f"The recording is {dur:.1f} s. Keep it under {vp.MAX_S:.0f} seconds.")
    return dur


async def transcribe(data: bytes, filename: str, lg: str) -> dict[str, Any]:
    stt_lang, mode = ct.STT_ARGS[lg]
    return await transcribe_upload(data, filename, lang=stt_lang, mode=mode, use_context=False)


def diary_text(method: str, lg: str, m: dict[str, Any] | None, transcript: str) -> str:
    """English, key facts first (the legal-pack annex cuts at 140 characters)."""
    if m:
        score = f"{m['content_matched']}/{m['content_total']} words, name {'heard' if m['name_matched'] else 'not heard'}"
    else:
        score = "spoken check skipped"
    head = {"spoken": "Voice consent given by voice", "tap": "Voice consent given by tap"}[method]
    said = transcript.strip() or "(no transcript)"
    return f"{head} (method: {method}, {lg}, {score}). Said: {said}"


def add_entry(s: Session, worker_id: int, text: str, audio_sha256: str | None = None) -> DiaryEntry:
    from .routes.cases import add_diary_entry   # the one place that knows the chain hash

    return add_diary_entry(s, worker_id, text, kind="consent", audio_sha256=audio_sha256)


async def attempt(s: Session, worker: Worker, data: bytes, filename: str, lang: str | None = None,
                  method: str = "spoken") -> dict[str, Any]:
    """One recording. Returns a body with status ready | not_matched | too_short | too_long.
    Raises GnaniError only when the clone itself (embeddings) fails; ValueError for a bad recording."""
    if method not in METHODS:
        raise ValueError("method must be spoken or tap")
    vp.check_cloning_enabled()  # public deploy: raises CloningDisabled before any Gnani call
    if not data:
        raise ValueError("empty audio")
    lg = ct.lang_for_worker(worker.language, lang)
    sha = db.sha256_hex(data)
    base: dict[str, Any] = {"worker_id": worker.id, "lang": lg, "method": method, "audio_sha256": sha,
                            "audio_stored": False}
    try:
        dur = await run_in_threadpool(check_duration, data, filename)
    except TooShortOrLong as e:
        return {**base, "status": e.status, "duration_s": round(e.duration_s, 2), "message": e.message,
                "can_retry": True, "can_confirm_by_tap": False, "words": ct.blank_words(worker.name, lg)}
    base["duration_s"] = round(dur, 2)

    transcript, m, stt_error = "", None, None
    if method == "spoken":
        try:
            r = await transcribe(data, filename, lg)
            transcript = r.get("transcript") or ""
            m = ct.match(transcript, worker.name, lg)
        except GnaniError as e:                    # STT down: never block, offer the tap
            stt_error = e.as_dict()
        _remember(worker.id, sha, {"transcript": transcript, "match": m, "lang": lg, "stt_error": stt_error})
        if m is None or not m["passed"]:
            return {**base, "status": "not_matched", "transcript": transcript, "match": m,
                    "words": (m or {}).get("words") or ct.blank_words(worker.name, lg),
                    "missed": (m or {}).get("missed", []), "stt_error": stt_error,
                    "can_retry": True, "can_confirm_by_tap": True,
                    "message": ("Could not check the words right now. Try again, or tap to confirm."
                                if stt_error else "Some words were not heard. Try again, or tap to confirm.")}
    else:                                          # tap: only after a spoken attempt of this same recording
        prev = _recall(worker.id, sha)
        if prev is None:
            return {**base, "status": "spoken_first", "can_retry": True, "can_confirm_by_tap": False,
                    "words": ct.blank_words(worker.name, lg),
                    "message": "Read the sentence aloud first. If some words are not heard, you can then confirm by tap."}
        transcript, m = prev["transcript"], prev["match"]

    # Consent is established (heard, or confirmed by tap): only now is the embedding made.
    res = await vp.create_profile(s, worker.id, True, data, filename)
    entry = add_entry(s, worker.id, diary_text(method, lg, m, transcript), audio_sha256=sha)
    s.commit()
    s.refresh(entry)
    _ATTEMPTS.pop((worker.id, sha), None)
    return {**base, "status": "ready", "consent_method": method, "transcript": transcript, "match": m,
            "words": (m or {}).get("words") or ct.blank_words(worker.name, lg),
            "missed": (m or {}).get("missed", []),
            "consent": entry_view(entry),
            "profile": {**vp.public_view(res.profile, worker.language), "trimmed_to_20s": res.trimmed},
            "message": "Consent heard" if method == "spoken" else "Consent confirmed by tap"}


# --------------------------------------------------------------------------- log + withdraw
_METHOD_RE = re.compile(r"\(method: (\w+)")


def entry_view(e: DiaryEntry) -> dict[str, Any]:
    mm = _METHOD_RE.search(e.text or "")
    withdrawn = (e.text or "").startswith("Voice consent withdrawn")
    return {"diary_entry_id": e.id, "timestamp": e.timestamp, "event": "withdrawn" if withdrawn else "given",
            "consent_method": mm.group(1) if mm else None, "text": e.text, "audio_sha256": e.audio_sha256,
            "hash": e.hash, "prev_hash": e.prev_hash}


def consent_log(s: Session, worker_id: int) -> list[dict[str, Any]]:
    rows = s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == worker_id, DiaryEntry.kind == "consent")
                  .order_by(DiaryEntry.id)).all()
    return [entry_view(e) for e in rows]


def status(s: Session, worker: Worker, lang: str | None = None) -> dict[str, Any]:
    log = consent_log(s, worker.id)
    prof = vp.active_profile(s, worker.id)
    return {**text_view(worker, lang), "prompt": cached_prompt(worker, lang),
            "profile": vp.public_view(prof, worker.language),
            "consent_active": bool(prof) and bool(log) and log[-1]["event"] == "given",
            "log": log}


def withdraw(s: Session, worker: Worker) -> dict[str, Any]:
    log = consent_log(s, worker.id)
    had_profile = vp.active_profile(s, worker.id) is not None
    n = vp.delete_profiles(s, worker.id, commit=False)
    entry = None
    if n or had_profile or (log and log[-1]["event"] == "given"):
        last_method = next((x["consent_method"] for x in reversed(log) if x["event"] == "given"), None)
        text = (f"Voice consent withdrawn (method: {last_method or 'unknown'}). "
                f"Voice profile deleted ({n}); clips in her voice removed.")
        entry = add_entry(s, worker.id, text)
    s.commit()
    if entry is not None:
        s.refresh(entry)
    return {"worker_id": worker.id, "deleted": n, "exists": False, "voice": "stock Timbre voice",
            "logged": entry is not None, "consent": entry_view(entry) if entry else None}
