"""Baaki settings, loaded from the project-root .env.

Keys are read here and nowhere else. Never print, log or persist them.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"  # gitignored
TMP_DIR = Path(os.environ.get("AUDIO_TMP_DIR", str(DATA_DIR / "tmp")))
FONTS_DIR = BACKEND_DIR / "fonts"  # Noto Sans Telugu / Devanagari for PDFs (fpdf2 + uharfbuzz)
SEED_CACHE_DIR = BACKEND_DIR / "seed_cache"  # committed: pre-rendered demo TTS, so a cold deploy spends no credits

# override=False: real environment variables (e.g. on Render/Fly) win over .env.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def gnani_key() -> str:
    return os.environ.get("GNANI_API_KEY", "").strip()


def gnani_base() -> str:
    return os.environ.get("GNANI_API_BASE", "https://api.vachana.ai").strip().rstrip("/")


def groq_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def llm_provider() -> str:
    """groq (default) | gemini (Gemini first) | none (LLM off)."""
    return os.environ.get("LLM_PROVIDER", "groq").strip().lower()


def groq_model() -> str:
    # Strict json_schema works on gpt-oss. Llama 3.x was shut down for free/developer tiers on
    # 16 Aug 2026 (deposit-wapas docs/research/deep/04_tech_feasibility.md 5a).
    return os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()


def groq_fallback_model() -> str:
    return os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b").strip()


def gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip()


def gemini_backup_enabled() -> bool:
    """Gemini is OFF by default. Deposit Wapas M0 (8 Nov 2026): the AQ. key authenticated on the
    native endpoint, but generateContent gave 404 on gemini-2.5-flash and timed out on
    gemini-flash-latest. Opt in with GEMINI_BACKUP=1 or LLM_PROVIDER=gemini."""
    return llm_provider() == "gemini" or os.environ.get("GEMINI_BACKUP", "0").strip() in ("1", "true", "yes")


def database_url() -> str | None:
    """Postgres (Supabase/Neon) in production. Unset = local SQLite at backend/data/app.db."""
    return os.environ.get("DATABASE_URL", "").strip() or None


def stt_use_context() -> bool:
    """Send domain topic + keyterms with Prisma v3.0 requests (default ON; STT_CONTEXT=0 turns it off).

    Deposit Wapas M0 A/B: context kept amounts 12/12 and fixed a date that ITN invented. With
    context, Prisma sometimes leaves amounts as number words, so app.lang.amounts is required.
    """
    return os.environ.get("STT_CONTEXT", "1").strip().lower() in ("1", "true", "yes")


def cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def media_dir() -> Path:
    """Local media store (LocalStorage). A cloud store replaces it in production."""
    return Path(os.environ.get("MEDIA_DIR", str(DATA_DIR / "media")))


def tts_cache_dir() -> Path:
    """TTS disk cache, keyed by sha256(model|voice|lang|text), so a text is never synthesised twice."""
    return Path(os.environ.get("TTS_CACHE_DIR", str(DATA_DIR / "tts_cache")))


def public_base_url() -> str:
    """Origin of the web app (used for links in letters and share messages)."""
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").strip().rstrip("/")
