"""Baaki API. Every app route is under /api; the web app codes against these shapes.

Run (from the project root):
  backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import audio, config, db, llm, tts_cache
from .gnani import DEFAULT_VOICE, DEFAULT_VOICE_V25, TIMBRE_V3_VOICES, TTS_MODEL_V25, TTS_MODEL_V3, GnaniError
from .routes import ROUTERS
from .stt_service import DEFAULT_LANGS, LANG_PRESETS, MODES, transcribe_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # request lines only; never headers

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TTS_CHARS = 1500
ACCEPTED_AUDIO = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()  # create tables on startup (SQLite locally, DATABASE_URL in production)
    yield


app = FastAPI(title="Baaki API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Duration-S", "X-TTS-Cache", "X-TTS-Voice"],
)


def _gnani_http(e: GnaniError) -> HTTPException:
    status = 503 if e.status == 429 else 502
    return HTTPException(status_code=status, detail=e.as_dict())


# --------------------------------------------------------------------------- health / voices
def _health() -> dict:
    return {"ok": True, "gnani": bool(config.gnani_key()), "llm": llm.configured(),
            "llm_provider": config.llm_provider()}


@app.get("/health")
async def health_root() -> dict:
    return _health()


@app.get("/api/health")
async def health() -> dict:
    return _health()


@app.get("/api/voices")
async def voices() -> dict:
    catalog = [{"name": n, **meta} for n, meta in TIMBRE_V3_VOICES.items()]
    return {
        "model": TTS_MODEL_V3,
        "defaults": {TTS_MODEL_V3: DEFAULT_VOICE, TTS_MODEL_V25: DEFAULT_VOICE_V25},
        "voices": catalog,
        "stt_lang_presets": LANG_PRESETS,
        "note": "Timbre v3.0: every voice speaks all 10 languages. Hinglish: lang hi-en.",
    }


# --------------------------------------------------------------------------- STT
class Chunk(BaseModel):
    start_s: float
    end_s: float
    transcript: str


class STTOut(BaseModel):
    transcript: str
    detected_language_code: Optional[str]
    language_code: str
    mode: str
    chunks: list[Chunk]
    duration_s: float
    model: str


@app.post("/api/stt", response_model=STTOut)
async def stt(audio_file: UploadFile = File(..., alias="audio"), lang: str = Form(DEFAULT_LANGS),
              mode: str = Form("transcribe")) -> dict:
    """Audio upload -> Gnani Prisma v3.0 transcript.

    lang: te | hinglish | auto (default) | indic-auto | 1-4 codes such as "te-IN,en-IN".
    mode: transcribe (digits, default) | codemix | verbatim | transliterate.
    Any length: clips over 28 s are split at silences and sent one by one (1 active request).
    """
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {list(MODES)}")
    name = audio_file.filename or "upload"
    ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
    if ext not in ACCEPTED_AUDIO:
        raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
    data = await audio_file.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "audio larger than 25 MB")
    try:
        return await transcribe_upload(data, f"upload.{ext}", lang=lang, mode=mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except audio.AudioError as e:
        raise HTTPException(415, f"could not decode audio: {e}")
    except GnaniError as e:
        raise _gnani_http(e)


# --------------------------------------------------------------------------- TTS
class TTSIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TTS_CHARS)
    lang: Literal["te-IN", "hi-IN", "hi-en", "en-IN"]
    voice: Optional[str] = None
    model: Literal["timbre-v3.0", "timbre-v2.5"] = "timbre-v3.0"
    format: Literal["ogg", "mp3"] = "ogg"


@app.post("/api/tts")
async def tts(body: TTSIn) -> Response:
    """Timbre through the disk cache: a text is never synthesised twice. Returns audio bytes.

    lang hi-en = Hinglish. Default voices: v3.0 Kalpana (te), Shivani (hi, hi-en); v2.5 Poorvi (hi-en).
    """
    voice = body.voice or tts_cache.default_voice(body.lang, body.model)
    if body.model == TTS_MODEL_V3 and voice not in TIMBRE_V3_VOICES:
        raise HTTPException(400, f"unknown voice '{voice}'; see /api/voices")
    try:
        entry = await tts_cache.synth(body.text, body.lang, voice, fmt=body.format, model=body.model)
    except GnaniError as e:
        raise _gnani_http(e)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except audio.AudioError as e:
        raise HTTPException(502, f"TTS returned undecodable audio: {e}")
    media = "audio/ogg" if body.format == "ogg" else "audio/mpeg"
    data = await run_in_threadpool(entry.path.read_bytes)
    return Response(content=data, media_type=media,
                    headers={"X-Duration-S": f"{entry.duration_s:.2f}", "X-TTS-Cache": "hit" if entry.cached else "miss",
                             "X-TTS-Voice": voice})


# --------------------------------------------------------------------------- domain routers (placeholders)
for _r in ROUTERS:
    app.include_router(_r)
