"""Exit Kit (W03). Owned by the tournament feature agent for this module."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/exit", tags=["exit"])
