"""Fair Pay Check (V01). Owned by the tournament feature agent for this module."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/check", tags=["check"])
