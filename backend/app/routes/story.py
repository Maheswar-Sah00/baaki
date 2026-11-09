"""V12 Case Replay: one case's real stored events as a timeline. Owned by the story agent (tournament ranks 6-10).

  GET /api/story/{case_id}   the case summary, total due and every stored event in stored-time order

Read-only. Private like the other worker pages: it needs the case id, and there is no listing route.
No Gnani or LLM calls; audio chips point at files already stored (/api/media/...).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from .. import db
from ..story_core import build_story

router = APIRouter(prefix="/api/story", tags=["story"])


def _story(case_id: int) -> dict | None:
    with db.session() as s:
        return build_story(s, case_id)


@router.get("/{case_id}")
async def story(case_id: int) -> dict:
    out = await run_in_threadpool(_story, case_id)
    if out is None:
        raise HTTPException(404, "case not found")
    return out
