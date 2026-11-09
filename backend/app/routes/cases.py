"""Cases: one worker's wage claim against one employer. PLACEHOLDERS (501).

Planned flow (do not build until the law and numbers research lands):
  worker speaks (Telugu or Hinglish) -> /api/stt -> facts extracted -> read back -> worker confirms
  -> calculator computes dues and the shortfall against the minimum wage -> letter -> follow-up.
"""
from __future__ import annotations

from fastapi import APIRouter

from .common import not_implemented

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("")
async def create_case() -> dict:
    """TODO: create a case (worker name, worker language, employer name, employer language, work type).
    Synthetic data only in the demo."""
    raise not_implemented("create_case")


@router.get("/{case_id}")
async def get_case(case_id: int) -> dict:
    """TODO: the case with its confirmed facts, computed dues, letters and follow-ups."""
    raise not_implemented("get_case")


@router.post("/{case_id}/extract")
async def extract_facts(case_id: int) -> dict:
    """TODO: transcript -> proposed facts (employer, work type, days/months, promised wage, amount paid).
    Amounts and dates come from app.lang parsers; the LLM (app.llm.json_call) only labels and
    structures them. Every fact is read back and confirmed by the worker before it is used."""
    raise not_implemented("extract_facts")


@router.post("/{case_id}/facts/{fact_id}/confirm")
async def confirm_fact(case_id: int, fact_id: int) -> dict:
    """TODO: the worker confirms or edits one proposed fact."""
    raise not_implemented("confirm_fact")


@router.get("/{case_id}/dues")
async def compute_dues(case_id: int) -> dict:
    """TODO: calculator output: wages due, paid, balance (baaki), shortfall against the notified
    minimum wage. Numbers and legal basis come from the research team; never claim an outcome."""
    raise not_implemented("compute_dues")


@router.get("/{case_id}/followups")
async def list_followups(case_id: int) -> dict:
    """TODO: follow-up tracker (sent, reminded, employer reply, paid)."""
    raise not_implemented("list_followups")
