"""Letters: the demand letter (Telugu and English PDF) and the voice note for the employer. PLACEHOLDERS (501).

PDF plumbing is ready in app/pdf.py (fpdf2 + uharfbuzz, Noto fonts). Letter text is NOT written yet:
it waits for the law research. Never claim a legal outcome; hand over to legal aid at the last step.
"""
from __future__ import annotations

from fastapi import APIRouter

from .common import not_implemented

router = APIRouter(prefix="/api/cases/{case_id}/letters", tags=["letters"])


@router.post("")
async def draft_letter(case_id: int) -> dict:
    """TODO: draft the demand letter from confirmed facts and computed dues, in the employer's
    language plus English. Shows a back-translation to the worker before anything is sent."""
    raise not_implemented("draft_letter")


@router.get("/{letter_id}/pdf")
async def letter_pdf(case_id: int, letter_id: int) -> dict:
    """TODO: render the letter PDF with app.pdf.render_pdf (Telugu / Devanagari shaped)."""
    raise not_implemented("letter_pdf")


@router.post("/{letter_id}/voice")
async def letter_voice(case_id: int, letter_id: int) -> dict:
    """TODO: Timbre voice note of the letter for the employer (te-IN or hi-en), starting with an AI
    disclosure; served through tts_cache. The worker presses Send/Share every time."""
    raise not_implemented("letter_voice")
