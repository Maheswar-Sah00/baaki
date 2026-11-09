"""Listen-twice guard (G07). Owned by the tournament feature agent for this module."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/verify", tags=["verify"])
