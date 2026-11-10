"""Fair Pay Check (V01).

Public, no login, and nothing is stored: no database rows, no files, no logging of inputs or transcripts.
Every endpoint that takes inputs is a POST, so the inputs never appear in access-log query strings.

  POST /api/check          {work_type, hours_per_day, days_per_week, monthly_pay} -> the check
  POST /api/check/parse    {text}  -> fields parsed from typed Hinglish/English (no Gnani, free)
  POST /api/check/speak    multipart audio (<= 25 s) -> Gnani Prisma hi-IN,en-IN codemix -> parsed fields (+ the check)
  GET  /api/check/speak/quota -> how many live mic tries this visitor has left today

The mic is capped per IP per IST day (CHECK_STT_PER_IP_DAY, default 3) and in total
(CHECK_STT_GLOBAL_DAY, default 150), in memory. Over the cap -> 429 with fallback "tap".
"""
from __future__ import annotations

import datetime as dt
import os
import threading
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .. import audio, security
from ..check_core import IST, WORK_TYPES, compute, parse_spoken
from ..gnani import GnaniError
from ..stt_service import transcribe_upload

router = APIRouter(prefix="/api/check", tags=["check"])

NO_STORE = {"Cache-Control": "no-store"}
MAX_SPEAK_BYTES = 3 * 1024 * 1024
MAX_SPEAK_SECONDS = 25.0
SPEAK_EXTS = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}
WorkType = Literal["maid", "cooking", "both", "care"]


class CheckIn(BaseModel):
    work_type: WorkType
    hours_per_day: float = Field(..., gt=0, le=16)
    days_per_week: float = Field(..., ge=1, le=7)
    monthly_pay: float = Field(..., ge=0, le=500_000)


class ParseIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)
    work_type: Optional[WorkType] = None


# --------------------------------------------------------------------------- the cap (in memory)
class SpeakGuard:
    """Per-IP and global daily counters for live STT. Resets at IST midnight and on restart."""

    def __init__(self):
        self._lock = threading.Lock()
        self._day: dt.date | None = None
        self._per_ip: dict[str, int] = {}
        self._total = 0

    @staticmethod
    def per_ip_cap() -> int:
        return max(0, int(os.environ.get("CHECK_STT_PER_IP_DAY", "3")))

    @staticmethod
    def global_cap() -> int:
        return max(0, int(os.environ.get("CHECK_STT_GLOBAL_DAY", "150")))

    def _roll(self) -> None:
        today = dt.datetime.now(IST).date()
        if self._day != today:
            self._day, self._per_ip, self._total = today, {}, 0

    def remaining(self, ip: str) -> int:
        with self._lock:
            self._roll()
            return max(0, min(self.per_ip_cap() - self._per_ip.get(ip, 0), self.global_cap() - self._total))

    def take(self, ip: str) -> bool:
        with self._lock:
            self._roll()
            if self._per_ip.get(ip, 0) >= self.per_ip_cap() or self._total >= self.global_cap():
                return False
            self._per_ip[ip] = self._per_ip.get(ip, 0) + 1
            self._total += 1
            return True

    def reset(self) -> None:
        with self._lock:
            self._day, self._per_ip, self._total = None, {}, 0


GUARD = SpeakGuard()


def client_ip(request: Request) -> str:
    """Visitor IP: one rule for the whole app (security.client_ip): proxy headers are trusted only with
    TRUSTED_PROXY=1 (on localhost, unset, the old order: cf-connecting-ip, first X-Forwarded-For hop,
    X-Real-IP, socket peer)."""
    return security.client_ip(request)


def _fallback(status: int, code: str, message: str, remaining: int = 0) -> JSONResponse:
    return JSONResponse(status_code=status, headers=NO_STORE,
                        content={"error": code, "message": message, "fallback": "tap", "remaining_today": remaining})


def _fill_work_type(parsed: dict, work_type: str | None) -> dict:
    if work_type in WORK_TYPES and parsed["work_type"] is None:
        parsed["work_type"] = work_type
        parsed["missing"] = [m for m in parsed["missing"] if m != "work_type"]
    return parsed


def _with_result(parsed: dict) -> dict:
    out = {"parsed": parsed, "result": None}
    if not parsed["missing"]:
        out["result"] = compute(parsed["work_type"], parsed["hours_per_day"], parsed["days_per_week"],
                                parsed["monthly_pay"])
    return out


# --------------------------------------------------------------------------- routes
@router.post("")
async def check(body: CheckIn) -> JSONResponse:
    return JSONResponse(compute(body.work_type, body.hours_per_day, body.days_per_week, body.monthly_pay),
                        headers=NO_STORE)


@router.get("/options")
async def options() -> dict:
    return {"work_types": [{"id": k, "label": v["label"], "order_line": v["order_line"]} for k, v in WORK_TYPES.items()],
            "hours": {"min": 0.5, "max": 16, "full_time": 8}, "days_per_week": {"min": 1, "max": 7, "full_time": 6}}


@router.post("/parse")
async def parse(body: ParseIn) -> JSONResponse:
    parsed = _fill_work_type(parse_spoken(body.text), body.work_type)
    return JSONResponse(_with_result(parsed), headers=NO_STORE)


@router.get("/speak/quota")
async def speak_quota(request: Request) -> JSONResponse:
    return JSONResponse({"remaining_today": GUARD.remaining(client_ip(request)), "per_day": GUARD.per_ip_cap()},
                        headers=NO_STORE)


@router.post("/speak")
async def speak(request: Request, audio_file: UploadFile = File(..., alias="audio"),
                work_type: Optional[str] = Form(None)) -> JSONResponse:
    ip = client_ip(request)
    name = audio_file.filename or "upload"
    ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
    if ext not in SPEAK_EXTS:
        raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
    data = await audio_file.read()
    if not data:
        raise HTTPException(400, "empty audio")
    too_long = "Keep it to one sentence (under 25 seconds)."
    if len(data) > MAX_SPEAK_BYTES:
        return _fallback(413, "too_long", too_long, GUARD.remaining(ip))
    try:
        seconds = await run_in_threadpool(audio.duration_s, data, ext)
    except audio.AudioError:
        raise HTTPException(415, "could not decode audio")
    if seconds > MAX_SPEAK_SECONDS:
        return _fallback(413, "too_long", too_long, GUARD.remaining(ip))
    if not GUARD.take(ip):
        return _fallback(429, "daily_cap", "The voice check is resting for today. Tap your answers instead.")
    try:
        stt = await transcribe_upload(data, f"check.{ext}", lang="hinglish", mode="codemix")
    except GnaniError:
        return _fallback(503, "stt_unavailable", "Voice is busy right now. Tap your answers instead.",
                         GUARD.remaining(ip))
    except (ValueError, audio.AudioError):
        raise HTTPException(415, "could not decode audio")
    transcript = stt.get("transcript", "")
    out = _with_result(_fill_work_type(parse_spoken(transcript), work_type))
    out.update(transcript=transcript, remaining_today=GUARD.remaining(ip))
    return JSONResponse(out, headers=NO_STORE)
