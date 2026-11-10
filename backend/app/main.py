"""Baaki API. Every app route is under /api; the web app codes against these shapes.

Run (from the project root):
  backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --port 8000
"""
from __future__ import annotations

import dataclasses
import inspect
import logging
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import audio, config, db, gnani, llm, security, tts_cache
from .gnani import DEFAULT_VOICE, DEFAULT_VOICE_V25, TIMBRE_V3_VOICES, TTS_MODEL_V25, TTS_MODEL_V3, GnaniError
from .routes import ROUTERS
from .stt_service import DEFAULT_LANGS, LANG_PRESETS, MODES, transcribe_upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # request lines only; never headers
log = logging.getLogger("baaki")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TTS_CHARS = 1500
ACCEPTED_AUDIO = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}
LAN_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?"


async def _seed_if_empty() -> None:
    """Fresh server: seed the synthetic demo story when the database is empty (F4's seed.ensure_seeded).
    One switch: BAAKI_SEED_ON_BOOT (config.seed_on_boot(): default on in public mode, off on localhost).
    ensure_seeded may be sync (run in a thread) or async (awaited)."""
    if not config.seed_on_boot():
        return
    try:
        from .seed import ensure_seeded  # type: ignore[attr-defined]
    except ImportError:
        log.warning("seed on boot requested but seed.ensure_seeded() is not available yet")
        return
    try:
        if inspect.iscoroutinefunction(ensure_seeded):
            out = await ensure_seeded()
        else:
            out = await run_in_threadpool(ensure_seeded)
            if inspect.isawaitable(out):
                out = await out
        if out:
            log.info("seeded the synthetic demo story on boot (empty database)")
    except Exception:  # never block startup on the demo seed
        log.exception("seed on boot failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()  # create tables on startup (SQLite locally, DATABASE_URL in production); includes workerkey
    await _seed_if_empty()
    if config.baaki_public():
        log.info("BAAKI_PUBLIC on: worker keys, admin-gated demo routes, Gnani budget, cache-only TTS, no cloning")
    yield


# One app-level dependency: security.guard classifies every route (public mode) and records the route for
# the Gnani budget. Unset BAAKI_PUBLIC (localhost filming): it only records the route.
app = FastAPI(title="Baaki API", version="0.1.0", lifespan=lifespan, dependencies=[Depends(security.guard)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    # any 192.168.* phone on the LAN only for localhost filming, never on a public deploy
    allow_origin_regex=None if config.baaki_public() else LAN_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Duration-S", "X-TTS-Cache", "X-TTS-Voice", "X-Request-ID"],
)
app.add_middleware(security.RequestContextMiddleware)  # outermost: request id, client IP, security headers


@app.exception_handler(audio.AudioTooLong)
async def _too_long(_request: Request, exc: audio.AudioTooLong) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": exc.as_dict()})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    rid = request.scope.get("baaki_request_id") or security.request_id() or "-"
    log.error("unhandled error on %s %s [request %s]", request.method, request.url.path, rid, exc_info=exc)
    return JSONResponse(status_code=500, headers={"X-Request-ID": rid},
                        content={"detail": {"error": "internal", "message": "Something went wrong on our side.",
                                            "request_id": rid}})


def _gnani_http(e: GnaniError) -> HTTPException:
    status = 503 if e.status == 429 else 502
    return HTTPException(status_code=status, detail=e.as_dict())


# --------------------------------------------------------------------------- health / voices
def _readiness() -> dict:
    """Readiness facts, never secrets: database, ffmpeg, seed rows, Gnani breaker and remaining budget."""
    from sqlalchemy import text
    from sqlmodel import func, select

    from .models import Worker

    out: dict = {"public": config.baaki_public()}
    try:
        with db.session() as s:
            s.exec(text("SELECT 1"))
            out["db"] = True
            out["seeded"] = (s.exec(select(func.count()).select_from(Worker)).one() or 0) > 0
    except Exception:
        out["db"], out["seeded"] = False, False
    try:
        audio.ffmpeg_exe()
        out["ffmpeg"] = True
    except Exception:
        out["ffmpeg"] = False
    out["gnani_breaker"] = gnani.get_client().breaker_state()
    out["gnani_budget"] = security.BUDGET.remaining()
    out["gnani_lock"] = dict(gnani.LOCK_STATS)
    out["ready"] = bool(out["db"] and out["ffmpeg"])
    return out


def _health() -> dict:
    return {"ok": True, "gnani": bool(config.gnani_key()), "llm": llm.configured(),
            "llm_provider": config.llm_provider(),
            # successful Gnani calls since this process started (credit tracking for demo runs)
            "gnani_calls": dataclasses.asdict(gnani.STATS),
            "readiness": _readiness()}


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


@app.post("/api/stt", response_model=STTOut)  # 404 on a public deploy (security.ROUTE_RULES: OFF)
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


@app.post("/api/tts")  # 404 on a public deploy (security.ROUTE_RULES: OFF)
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

# Messages and the employer side (letters is already in ROUTERS)
from .routes.employer import router as _employer_router  # noqa: E402
from .routes.onboard import router as _onboard_router  # noqa: E402
from .routes.voice_profile import router as _voice_profile_router  # noqa: E402

for _r in (_employer_router, _voice_profile_router, _onboard_router):
    app.include_router(_r)
