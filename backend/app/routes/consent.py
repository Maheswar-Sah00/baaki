"""G13 Spoken consent is the voice sample: the consent sentence she reads is also the clone sample.

  GET  /api/consent?worker_id=1&lang=te     sentence, karaoke words, cached prompt, profile, consent log
  POST /api/consent/prompt                  JSON {worker_id, lang}: Timbre reads it slowly (cached)
  GET  /api/consent/audio/{key}.ogg         the cached prompt audio
  POST /api/consent/match                   JSON {worker_id, lang, transcript}: the matcher only (no Gnani)
  POST /api/consent/attempt                 multipart worker_id, lang, method=spoken|tap, audio (10-20 s)
                                            -> status ready | not_matched | too_short | too_long
  POST /api/consent/withdraw                JSON {worker_id}: deletes the profile, logs "consent withdrawn"

The gate never blocks: not_matched always offers retry and confirm-by-tap (method=tap with the same audio).
The old /api/voice-profile endpoints are unchanged.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .. import audio, consent_flow, consent_text, db, tts_cache
from ..gnani import GnaniError
from ..models import Worker

router = APIRouter(prefix="/api/consent", tags=["consent"])


class PromptIn(BaseModel):
    worker_id: int
    lang: Optional[str] = None


class MatchIn(BaseModel):
    worker_id: int
    lang: Optional[str] = None
    transcript: str = ""


class WithdrawIn(BaseModel):
    worker_id: int


def _worker(s, worker_id: int) -> Worker:
    w = s.get(Worker, worker_id)
    if w is None:
        raise HTTPException(404, "worker not found")
    return w


@router.get("")
async def get_consent(worker_id: int = Query(...), lang: Optional[str] = Query(None)) -> dict:
    with db.session() as s:
        return consent_flow.status(s, _worker(s, worker_id), lang)


@router.post("/prompt")
async def post_prompt(body: PromptIn) -> dict:
    with db.session() as s:
        w = _worker(s, body.worker_id)
    return await consent_flow.prompt(w, body.lang)


@router.get("/audio/{name}")
async def prompt_audio(name: str) -> Response:
    key, _, fmt = name.partition(".")
    p = tts_cache.lookup(key, "ogg") if fmt in ("", "ogg") else None
    if p is None:
        raise HTTPException(404, "not cached")
    data = await run_in_threadpool(p.read_bytes)
    return Response(content=data, media_type="audio/ogg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("/match")
async def post_match(body: MatchIn) -> dict:
    with db.session() as s:
        w = _worker(s, body.worker_id)
    lg = consent_text.lang_for_worker(w.language, body.lang)
    return consent_text.match(body.transcript, w.name, lg)


@router.post("/attempt")
async def post_attempt(worker_id: int = Form(...), lang: Optional[str] = Form(None), method: str = Form("spoken"),
                       audio_file: UploadFile = File(..., alias="audio")) -> dict:
    method = (method or "spoken").strip().lower()
    if method not in consent_flow.METHODS:
        raise HTTPException(400, {"error": "bad_method", "message": "method must be spoken or tap"})
    data = await audio_file.read()
    if len(data) > consent_flow.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "recording larger than 10 MB")
    name = audio_file.filename or "voice.webm"
    if not audio.ext_of(name):
        name = "voice." + ((audio_file.content_type or "audio/webm").split("/")[-1].split(";")[0] or "webm")
    with db.session() as s:
        w = _worker(s, worker_id)
        try:
            return await consent_flow.attempt(s, w, data, name, lang, method)
        except audio.AudioError as e:
            raise HTTPException(415, f"could not decode audio: {e}")
        except ValueError as e:
            raise HTTPException(400, {"error": "bad_recording", "message": str(e)})
        except GnaniError as e:
            raise HTTPException(503 if e.status == 429 else 502, e.as_dict())


@router.post("/withdraw")
async def post_withdraw(body: WithdrawIn) -> dict:
    with db.session() as s:
        return consent_flow.withdraw(s, _worker(s, body.worker_id))
