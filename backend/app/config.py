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
    """SQLite URL override (e.g. sqlite:////data/app.db on a deploy volume). Unset = backend/data/app.db.
    Only SQLite is supported (see .env.example)."""
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
    """Origin of the web app (used for links in letters and share messages). Behind a trusted proxy
    (TRUSTED_PROXY=1) it is derived per request from X-Forwarded-Host/Host; PUBLIC_BASE_URL is the fallback."""
    per_request = REQUEST_BASE_URL.get()
    if per_request:
        return per_request
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").strip().rstrip("/")


# --------------------------------------------------------------------------- public deploy (app/security.py)
def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def baaki_public() -> bool:
    """BAAKI_PUBLIC=1: a public deploy anyone can open. Turns on worker keys, the admin token on demo
    routes, the Gnani budget, cache-only TTS and no cloning. Unset (localhost filming): behaviour as before."""
    return _flag("BAAKI_PUBLIC")


def demo_open() -> bool:
    """BAAKI_DEMO_OPEN (default on in public mode): the seeded synthetic workers (no key) are viewable."""
    return _flag("BAAKI_DEMO_OPEN", "1")


def admin_token() -> str:
    return os.environ.get("BAAKI_ADMIN_TOKEN", "").strip()


def trusted_proxy() -> str:
    """How far to trust client-IP headers: "1" = behind a trusted proxy (cf-connecting-ip, else the
    X-Forwarded-For hop the proxy added); "0" = the socket peer only. Unset: "legacy" (the old behaviour,
    first X-Forwarded-For hop) on localhost, "0" in public mode."""
    raw = os.environ.get("TRUSTED_PROXY", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return "1"
    if raw in ("0", "false", "no"):
        return "0"
    return "0" if baaki_public() else "legacy"


def trusted_proxy_hops() -> int:
    """X-Forwarded-For hops appended by trusted proxies (1 = the last entry is the client the proxy saw)."""
    try:
        return max(1, int(os.environ.get("TRUSTED_PROXY_HOPS", "1")))
    except ValueError:
        return 1


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(default)).strip()))
    except ValueError:
        return default


def gnani_budget(kind: str) -> int | None:
    """Daily Gnani calls allowed per kind (stt | tts | vc) in public mode; None = unlimited (localhost)."""
    if not baaki_public():
        return None
    name, default = {"stt": ("GNANI_BUDGET_STT", 400), "tts": ("GNANI_BUDGET_TTS", 150),
                     "vc": ("GNANI_BUDGET_VC", 0)}[kind]
    return _int_env(name, default)


def gnani_budget_per_ip() -> int | None:
    """Daily Gnani calls (all kinds) one client IP may cause in public mode; None = unlimited."""
    return _int_env("GNANI_BUDGET_PER_IP", 40) if baaki_public() else None


def gnani_deadline_s() -> float:
    """Total time one Gnani call may take, waiting for the 1-request lock included."""
    try:
        return max(5.0, float(os.environ.get("GNANI_DEADLINE_S", "45")))
    except ValueError:
        return 45.0


def gnani_breaker_s() -> float:
    """After 401/402 from Gnani, fail fast (voice_unavailable) for this many seconds."""
    try:
        return max(0.0, float(os.environ.get("GNANI_BREAKER_S", "300")))
    except ValueError:
        return 300.0


def stt_max_seconds() -> float:
    """Hard cap on one upload sent to STT (also on localhost: a 60-minute upload is never legitimate)."""
    try:
        return max(5.0, float(os.environ.get("STT_MAX_SECONDS", "90")))
    except ValueError:
        return 90.0


def tts_live_routes() -> list[str]:
    """Public mode: route templates that may synthesise NEW Timbre audio (everything else is cache-only).
    "*" allows every route."""
    raw = os.environ.get("TTS_LIVE_ROUTES", "")
    if raw.strip():
        return [r.strip() for r in raw.split(",") if r.strip()]
    return ["/api/e/{token}/reply", "/api/cases/{case_id}/readback", "/api/cases/{case_id}/messages/{step}",
            "/api/inbox/{case_id}"]


def onboard_per_ip_day() -> int | None:
    return _int_env("ONBOARD_PER_IP_DAY", 5) if baaki_public() else None


def seed_on_boot() -> bool:
    """BAAKI_SEED_ON_BOOT: seed the synthetic demo story at startup when the database is empty. Default on in
    public mode, off on localhost unless set. SEED_ON_BOOT is accepted as a legacy alias."""
    raw = os.environ.get("BAAKI_SEED_ON_BOOT", "").strip() or os.environ.get("SEED_ON_BOOT", "").strip()
    if not raw:
        return baaki_public()
    return raw.lower() in ("1", "true", "yes", "on")


# Per-request public origin (set by security.RequestContextMiddleware when TRUSTED_PROXY=1).
from contextvars import ContextVar  # noqa: E402

REQUEST_BASE_URL: ContextVar[str | None] = ContextVar("baaki_request_base_url", default=None)
