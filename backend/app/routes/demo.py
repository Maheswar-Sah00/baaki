"""Demo controls: POST /api/demo/reset rebuilds the synthetic story (Lakshmi's three homes, Rafiq and Rao garu)."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from .. import seed

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
async def reset() -> dict:
    """Wipe every table and re-create the demo story. Returns the ids and employer tokens."""
    return await run_in_threadpool(seed.reset)
