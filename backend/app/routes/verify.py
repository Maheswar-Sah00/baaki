"""Listen-twice guard (G07). Owned by the tournament feature agent for this module.

  POST /api/verify/messages/{message_id}   re-hear the message's voice note with Prisma (cached)
  GET  /api/verify/messages/{message_id}   the cached result for the current audio, or 404

The check only warns: the worker can always send the note.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from .. import audio, db, storage, verify_guard
from ..gnani import GnaniError
from ..messages import load_ctx
from ..models import Message

log = logging.getLogger("verify")
router = APIRouter(prefix="/api/verify", tags=["verify"])


def _load(message_id: int) -> tuple[Message, dict[str, Any]]:
    """The message and what the check needs from its case (worker name, balance, phone masks)."""
    with db.session() as s:
        m = s.get(Message, message_id)
        if m is None:
            raise HTTPException(404, {"error": "message_not_found", "message": "message not found"})
        ctx = load_ctx(s, m.case_id)
        info: dict[str, Any] = {"worker_name": None, "balance": None, "mask": []}
        if ctx is not None:
            info = {"worker_name": ctx.worker.name, "balance": ctx.balance,
                    "mask": [ctx.worker.phone or "", ctx.employer.phone or "", ctx.worker.upi_vpa or ""]}
        s.expunge(m)
        return m, info


async def _audio(m: Message) -> tuple[bytes, str]:
    if not m.audio_path:
        raise HTTPException(409, {"error": "no_audio", "message": "this message has no voice note"})
    try:
        p = storage.get_storage().local_path(m.audio_path)
    except ValueError:
        p = None
    if p is None:
        raise HTTPException(409, {"error": "audio_missing", "message": "the voice note file is not available"})
    return await run_in_threadpool(p.read_bytes), p.name


def _view(m: Message, sha: str, result: dict[str, Any], cached: bool) -> dict[str, Any]:
    return {"message_id": m.id, "step": m.step, **result, "audio_sha256": sha, "cached": cached}


@router.post("/messages/{message_id}")
async def verify_message(message_id: int, force: bool = False) -> dict:
    """Prisma re-hears the voice note: are the ₹ amounts and the AI disclosure audible?"""
    m, info = _load(message_id)
    data, name = await _audio(m)
    sha = verify_guard.audio_sha256(data)
    async with verify_guard.lock_for(f"{message_id}:{sha}"):
        if not force:
            hit = verify_guard.read_cache(message_id, sha)
            if hit is not None:
                return _view(m, sha, hit, cached=True)
        try:
            result = await verify_guard.listen_twice(data, name, text=m.text, lang=m.language,
                                                     worker_name=info["worker_name"], balance=info["balance"],
                                                     mask=info["mask"])
        except GnaniError as e:
            log.warning("listen-twice STT failed: %s", str(e)[:160])
            raise HTTPException(502, {"error": "stt_failed", "message": "could not re-hear the voice note",
                                      "gnani": e.as_dict()})
        except audio.AudioError as e:
            raise HTTPException(422, {"error": "audio_unreadable", "message": str(e)[:200]})
        result["checked_at"] = db.now_iso()
        verify_guard.write_cache(message_id, sha, result)
        return _view(m, sha, result, cached=False)


@router.get("/messages/{message_id}")
async def cached_result(message_id: int) -> dict:
    """The stored result for the message's current audio (no Gnani call)."""
    m, _ = _load(message_id)
    data, _ = await _audio(m)
    sha = verify_guard.audio_sha256(data)
    hit = verify_guard.read_cache(message_id, sha)
    if hit is None:
        raise HTTPException(404, {"error": "not_checked", "message": "this voice note has not been checked yet"})
    return _view(m, sha, hit, cached=True)
