"""Onboarding: a new worker and her secret key.

  POST /api/onboard   JSON {name, language} -> {worker_id, key, name, language}

The key is returned ONCE and only its sha256 is stored (security.WorkerKey). On a public deploy
(BAAKI_PUBLIC=1) every worker route needs it in the X-Baaki-Key header; the web client keeps it next to
workerId (lib/store.ts) and sends it on every request. Synthetic data only in the demo: use a made-up name.
Works on localhost too (it was the missing onboarding: an empty database had no worker to start with).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config, db, security
from ..models import Worker

router = APIRouter(prefix="/api", tags=["onboard"])

LANGS = {"te-IN": "te-IN", "te": "te-IN", "telugu": "te-IN",
         "hi-en": "hi-en", "hinglish": "hi-en", "hi-IN": "hi-IN", "hi": "hi-IN", "hindi": "hi-IN",
         "en-IN": "en-IN", "en": "en-IN", "english": "en-IN"}
WORK_TYPES = ("housekeeping", "cooking", "childcare", "eldercare", "other")


class OnboardIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    language: str = Field("te-IN", max_length=16)
    work_type: Optional[str] = None


@router.post("/onboard", status_code=201)
async def onboard(body: OnboardIn, request: Request) -> dict:
    lang = LANGS.get(body.language.strip()) or LANGS.get(body.language.strip().lower())
    if not lang:
        raise HTTPException(400, {"error": "bad_language", "message": "language must be te-IN, hi-en, hi-IN or en-IN"})
    name = security.clean_name(body.name)
    if not name or name == "Employer":
        raise HTTPException(400, {"error": "bad_name", "message": "say or type a short name"})
    if not security.ONBOARD_LIMIT.take(security.client_ip(request), config.onboard_per_ip_day()):
        raise HTTPException(429, {"error": "rate_limited", "message": "Too many new profiles from here today."})
    work_type = body.work_type if body.work_type in WORK_TYPES else "housekeeping"
    with db.session() as s:
        w = Worker(name=name, language=lang, work_type=work_type)
        s.add(w)
        s.flush()
        key = security.issue_key(s, w.id)
        s.commit()
        return {"worker_id": w.id, "key": key, "name": w.name, "language": w.language,
                "key_header": "X-Baaki-Key",
                "note": "Keep this key on the phone. It is shown only once and opens her data."}
