"""Demo controls: POST /api/demo/reset rebuilds the synthetic story (Lakshmi's three homes, Rafiq and Rao garu).

Public deploy (BAAKI_PUBLIC=1): 404 unless X-Admin-Token equals BAAKI_ADMIN_TOKEN (security.ROUTE_RULES).
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from .. import db, security, seed

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _reset() -> dict:
    out = seed.reset()
    # worker ids are reused after the wipe: no old key may attach to a new (synthetic) worker
    with db.session() as s:
        security.wipe_keys(s)
        s.commit()
    return out


@router.post("/reset")
async def reset() -> dict:
    """Wipe every table and re-create the demo story. Returns the ids and employer tokens."""
    return await run_in_threadpool(_reset)
