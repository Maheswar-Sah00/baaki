"""Opt-in voice profile (Gnani voice clone). Consent first; the embedding is stored, never the audio.

  GET    /api/voice-profile?worker_id=1     status + consent text (never the embedding)
  POST   /api/voice-profile                 multipart: worker_id, consent=true, audio (10-20 s)
  DELETE /api/voice-profile?worker_id=1     deletes the profile and every clip spoken in that voice

POST is no longer a client flag (GAP_AUDIT #13): consent=true is still required, and the recording then goes
through the spoken consent check (consent_flow.attempt, method "spoken"): she must read the consent sentence
(GET /api/consent gives it). Not heard -> 400 consent_not_heard, with the words; the tap fallback lives on
/api/consent/attempt. Public deploy (BAAKI_PUBLIC=1): 403 cloning_disabled.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .. import audio, consent_flow, db
from ..gnani import GnaniError
from ..models import Worker
from ..voice_profile import CloningDisabled, ConsentRequired, active_profile, consent_text, delete_profiles, public_view

router = APIRouter(prefix="/api/voice-profile", tags=["voice-profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _consent(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


@router.get("")
async def get_profile(worker_id: int = Query(...)) -> dict:
    with db.session() as s:
        w = s.get(Worker, worker_id)
        if w is None:
            raise HTTPException(404, "worker not found")
        return public_view(active_profile(s, worker_id), w.language)


@router.post("")
async def post_profile(worker_id: int = Form(...), consent: str = Form("false"),
                       audio_file: UploadFile = File(..., alias="audio")) -> dict:
    """Needs consent=true AND the consent sentence read aloud in the recording (10-20 s; longer is trimmed)."""
    with db.session() as s:
        w = s.get(Worker, worker_id)
        if w is None:
            raise HTTPException(404, "worker not found")
        if not _consent(consent):
            raise HTTPException(400, {"error": "consent_required", "message": "send consent=true to opt in",
                                      "consent_text": consent_text(w.language)})
        data = await audio_file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "recording larger than 10 MB")
        name = audio_file.filename or "voice.webm"
        if not audio.ext_of(name):
            name = "voice." + ((audio_file.content_type or "audio/webm").split("/")[-1].split(";")[0] or "webm")
        try:
            res = await consent_flow.attempt(s, w, data, name, None, "spoken")
        except CloningDisabled as e:
            raise HTTPException(403, {"error": "cloning_disabled", "message": str(e)})
        except ConsentRequired as e:
            raise HTTPException(400, {"error": "consent_required", "message": str(e)})
        except audio.AudioError as e:
            raise HTTPException(415, f"could not decode audio: {e}")
        except ValueError as e:
            raise HTTPException(400, {"error": "bad_recording", "message": str(e)})
        except GnaniError as e:
            raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
        status = res.get("status")
        if status in ("too_short", "too_long"):
            raise HTTPException(400, {"error": "bad_recording", "message": res.get("message", status)})
        if status != "ready":
            raise HTTPException(400, {"error": "consent_not_heard", "message": res.get("message", ""),
                                      "words": res.get("words"), "missed": res.get("missed", []),
                                      "stt_error": res.get("stt_error"), "consent_page": "/voice/consent"})
        return {**res["profile"], "consent": res.get("consent")}


@router.delete("")
async def delete_profile(worker_id: int = Query(...)) -> dict:
    with db.session() as s:
        if s.get(Worker, worker_id) is None:
            raise HTTPException(404, "worker not found")
        n = delete_profiles(s, worker_id)
        return {"worker_id": worker_id, "deleted": n, "exists": False, "voice": "stock Timbre voice"}
