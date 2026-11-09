"""Haq Raise: ask for a raise to the legal minimum, with a step-up plan. Owned by the Haq Raise agent."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/raise", tags=["raise"])
