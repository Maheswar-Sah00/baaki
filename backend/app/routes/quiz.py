"""V08 Fair or Not?: five-card Code on Wages quiz for employers (information, not advice).

Public, no login, and nothing is stored: no database rows, no files, no logging of answers.

  GET  /api/quiz?lang=en|hi-en|te      -> the deck: five statements, no answers
  POST /api/quiz/answer {card_id, choice, lang} -> the rule for one card, its section, source and disclaimer
  POST /api/quiz/score  {answers: {card_id: choice}, lang} -> score card ("4/5"), every answer, share text
  GET  /api/quiz/audio/{key}.ogg       -> cached Hinglish narration (cache lookup only, never a live Gnani call)

Every card text and number lives in app/quiz_data.py and is derived from app.wages.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .. import quiz_data as qd
from .. import tts_cache

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

NARRATION_LANG = "hi-en"  # Timbre Hinglish
Choice = Literal["fair", "not_fair"]


class AnswerIn(BaseModel):
    card_id: str = Field(..., min_length=1, max_length=32)
    choice: Optional[Choice] = None
    lang: str = "en"


class ScoreIn(BaseModel):
    answers: dict[str, Choice] = Field(default_factory=dict)
    lang: str = "en"


def narration_key(card_id: str) -> str:
    text = qd.narration_text(card_id, NARRATION_LANG)
    return tts_cache.cache_key(text, NARRATION_LANG, tts_cache.default_voice(NARRATION_LANG))


def narration_url(card_id: str) -> str | None:
    """URL of the cached Hinglish narration for a card, or None. Never synthesises."""
    key = narration_key(card_id)
    return f"/api/quiz/audio/{key}.ogg" if tts_cache.lookup(key) else None


def _with_audio(r: dict) -> dict:
    r["audio_url"] = narration_url(r["id"])
    r["audio_lang"] = NARRATION_LANG if r["audio_url"] else None
    return r


@router.get("")
def get_deck(lang: str = "en") -> dict:
    return qd.deck(lang)


@router.post("/answer")
def post_answer(body: AnswerIn) -> dict:
    if body.card_id not in qd.CARD_IDS:
        raise HTTPException(404, "unknown card")
    return _with_audio(qd.reveal(body.card_id, body.choice, body.lang))


@router.post("/score")
def post_score(body: ScoreIn) -> dict:
    unknown = [k for k in body.answers if k not in qd.CARD_IDS]
    if unknown:
        raise HTTPException(422, f"unknown card: {unknown[0][:32]}")
    out = qd.score(body.answers, body.lang)
    out["results"] = [_with_audio(r) for r in out["results"]]
    return out


@router.get("/audio/{name}")
async def quiz_audio(name: str) -> Response:
    key, _, fmt = name.partition(".")
    fmt = fmt or "ogg"
    p = tts_cache.lookup(key, fmt) if fmt in ("ogg", "mp3") else None
    if p is None:
        raise HTTPException(404, "not cached")
    data = await run_in_threadpool(p.read_bytes)
    return Response(content=data, media_type="audio/ogg" if fmt == "ogg" else "audio/mpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
