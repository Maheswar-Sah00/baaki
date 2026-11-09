"""Noise proof bench (G04+V14). Owned by the tournament feature agent for this module."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/proof", tags=["proof"])
