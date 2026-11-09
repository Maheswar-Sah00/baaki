"""Async client for the Gnani (Vachana) speech APIs.

Endpoints, field names and voices come from docs/gnani_api/ (docs.gnani.ai, Nov 2026):
  STT (Prisma)     POST {base}/stt/v3                         multipart, field audio_file
  TTS (Timbre)     POST {base}/api/v1/tts/inference           JSON
  VC embeddings    POST {base}/api/v1/tts/voice-clone/embeddings  multipart, field audio_file
  VC synthesis     POST {base}/api/v1/tts/inference           JSON with speaker_embedding

The account allows ONE active request ("Only 1 active request is allowed at a time", 429
RATE_LIMITED), so every call goes through one process-wide asyncio.Lock, and 429/5xx are
retried with backoff (errors page: retry 429/500/503/504, ~3 attempts; no Retry-After today).

The API key is sent only in the X-API-Key-ID header to the official base URL. It is never
logged, printed or included in exceptions.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from . import config

log = logging.getLogger("gnani")

STT_PATH = "/stt/v3"
TTS_PATH = "/api/v1/tts/inference"
VC_EMBED_PATH = "/api/v1/tts/voice-clone/embeddings"

STT_MODELS = ("prisma-v3.0", "prisma-v2.5")
STT_FORMATS_V3 = ("verbatim", "transcribe", "codemix", "transliterate")
STT_FORMATS_V25 = ("verbatim", "transcribe")
STT_LANGS = ("bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN")
STT_EXTS = ("wav", "mp3", "ogg", "flac", "aac", "m4a")  # REST: detected from the file-name extension
STT_MAX_SECONDS = 30.0

TTS_MODEL_V3 = "timbre-v3.0"
TTS_MODEL_V25 = "timbre-v2.5"
VC_MODEL = "vachana-vc-v1"
TTS_LANGS = ("auto", "hi-IN", "en-IN", "hi-en", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN")
TTS_SAMPLE_RATES = (8000, 16000, 22050, 24000, 44100, 48000)
VC_MAX_SAMPLE_RATE = 44100

# Timbre v3.0: 13 voices, every voice speaks all 10 languages (TTS_available-voices.md).
TIMBRE_V3_VOICES: dict[str, dict[str, str]] = {
    "Avinash": {"gender": "male", "persona": "Professional", "description": "Professional, firm voice with deliberate pacing"},
    "Chetana": {"gender": "female", "persona": "Warm, empathetic", "description": "Gentle, empathetic voice"},
    "Devansh": {"gender": "male", "persona": "Conversational", "description": "Energetic, young conversational voice"},
    "Kalpana": {"gender": "female", "persona": "Warm, empathetic", "description": "Empathetic, composed voice"},
    "Lakshmi": {"gender": "female", "persona": "Expressive, energetic", "description": "Expressive, warm storytelling voice"},
    "Prakash": {"gender": "male", "persona": "Professional", "description": "Steady, deliberate voice"},
    "Riyaa": {"gender": "female", "persona": "Confident, authoritative", "description": "Confident, lively voice"},
    "Shivani": {"gender": "female", "persona": "Warm, empathetic", "description": "Warm, patient, empathy-first voice"},
    "Shubham": {"gender": "male", "persona": "Expressive, energetic", "description": "Energetic, confident voice"},
    "Tarika": {"gender": "female", "persona": "Warm, empathetic", "description": "Warm, reassuring voice"},
    "Vasudha": {"gender": "female", "persona": "Expressive, energetic", "description": "Expressive, composed narration voice"},
    "Yashraj": {"gender": "male", "persona": "Warm, empathetic", "description": "Warm narrative voice"},
    "Harshad": {"gender": "male", "persona": "Professional", "description": "Professional, firm voice"},
}
# Timbre v2.5 preferred voices for our languages (one preferred language each).
TIMBRE_V25_VOICES: dict[str, list[str]] = {
    "te-IN": ["Suhana", "Lehara", "Lavanya", "Yukti", "Varuni"],
    "hi-IN": ["Nalini", "Bhavna", "Yashvi", "Urmila", "Jwala", "Chitra", "Ambuja", "Deepak", "Roopesh", "Vikrant", "Hemraj", "Jalaj", "Omkar"],
    "hi-en": ["Poorvi"],
    "en-IN": ["Kaveri", "Trupti", "Devika", "Pranav", "Shlok", "Girish"],
}
TIMBRE_V3_TAGS = (
    "<coughs>", "<excited>", "<exhales>", "<giggle>", "<laugh>", "<pauses>", "<shouting>",
    "<sigh>", "<slow>", "<sniffles>", "<whispers>", "<yawns>", "<clears throat>",
)

# Default voices the app uses (Timbre v3.0). Baaki speaks both ways: Telugu (te-IN) and
# Hindi / Hinglish (hi-IN, hi-en), to the worker and to the employer.
# The v2.5 Hinglish voice is Poorvi (model timbre-v2.5, language hi-en).
DEFAULT_VOICE = {"te-IN": "Kalpana", "hi-IN": "Shivani", "hi-en": "Shivani", "en-IN": "Tarika"}
DEFAULT_VOICE_V25 = {"te-IN": "Suhana", "hi-IN": "Nalini", "hi-en": "Poorvi", "en-IN": "Kaveri"}

# Only 429 (the 1-active-request limit: nothing was processed) is retried. 5xx and read timeouts may
# have been processed and billed already (backend design audit, 10 Nov 2026).
RETRYABLE = {429}
BREAKER_STATUSES = {401, 402}  # bad key / no credits: fail fast for GNANI_BREAKER_S
LOCK_STATS: dict[str, float] = {"last_wait_s": 0.0, "max_wait_s": 0.0}

CONTENT_TYPES = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav", "raw": "application/octet-stream"}


class GnaniError(Exception):
    """A Gnani API call failed. Carries status, error code and message; never the key."""

    def __init__(self, status: int, code: str, message: str, request_id: str | None = None):
        super().__init__(f"Gnani {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id

    def as_dict(self) -> dict[str, Any]:
        return {"source": "gnani", "status": self.status, "code": self.code, "message": self.message,
                "request_id": self.request_id}


class GnaniConfigError(GnaniError):
    def __init__(self, message: str):
        super().__init__(0, "NOT_CONFIGURED", message)


@dataclass
class CallStats:
    """Counts calls per kind so scripts can stay inside the credit budget."""
    stt: int = 0
    tts: int = 0
    vc_embed: int = 0
    vc_tts: int = 0
    retries: int = 0


STATS = CallStats()

# ---------------------------------------------------------------------------
# One lock for the whole process. asyncio locks bind to an event loop, so keep one per loop
# (uvicorn runs one loop; tests and scripts may create several over the process lifetime).
_locks: dict[int, asyncio.Lock] = {}


def _lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    key = id(loop)
    lk = _locks.get(key)
    if lk is None:
        _locks.clear()  # drop locks of loops that are gone
        lk = _locks[key] = asyncio.Lock()
    return lk


def _parse_error(resp: httpx.Response) -> tuple[str, str]:
    """Return (code, message) from any of Gnani's error shapes."""
    try:
        body = resp.json()
    except Exception:
        return f"HTTP_{resp.status_code}", resp.text[:300]
    if isinstance(body, dict):
        det = body.get("detail")
        if isinstance(det, dict):  # auth / rate-limit shape
            return str(det.get("error_code") or f"HTTP_{resp.status_code}"), str(det.get("message", ""))
        if isinstance(det, list):  # 422 validation
            return "VALIDATION_ERROR", json.dumps(det, ensure_ascii=False)[:500]
        err = body.get("error")
        if isinstance(err, dict):  # STT envelope
            return str(err.get("type") or f"HTTP_{resp.status_code}"), str(err.get("message", ""))
        if "code" in body:  # STT 504 shape
            return str(body.get("code")), str(body.get("message", ""))
        if "message" in body:  # TTS / VC flat shape
            return f"HTTP_{resp.status_code}", str(body.get("message"))
    return f"HTTP_{resp.status_code}", resp.text[:300]


class GnaniClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None,
                 max_attempts: int = 5, backoff_s: float = 0.75, timeout_s: float = 60.0,
                 deadline_s: float | None = None):
        self._key = api_key if api_key is not None else config.gnani_key()
        self.base_url = (base_url or config.gnani_base()).rstrip("/")
        self._transport = transport
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self.deadline_s = deadline_s  # None: config.gnani_deadline_s() (GNANI_DEADLINE_S, default 45 s)
        self.timeout = httpx.Timeout(timeout_s, connect=15.0)
        self.last_response_headers: dict[str, str] = {}
        self._breaker_until = 0.0
        self._breaker_code: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        if not self._key:
            raise GnaniConfigError("GNANI_API_KEY is not set")
        h = {"X-API-Key-ID": self._key}
        if extra:
            h.update(extra)
        return h

    # ------------------------------------------------------------------ circuit breaker
    def breaker_state(self) -> dict[str, Any]:
        left = max(0.0, self._breaker_until - time.monotonic())
        return {"open": left > 0, "seconds_left": round(left, 1), "reason": self._breaker_code if left > 0 else None}

    def _trip(self, status: int, code: str) -> None:
        secs = config.gnani_breaker_s()
        if secs > 0:
            self._breaker_until = time.monotonic() + secs
            self._breaker_code = f"{status} {code}"
            log.warning("gnani breaker open for %.0f s after %d %s", secs, status, code)

    async def _request(self, method: str, path: str, *, kind: str, **kwargs: Any) -> httpx.Response:
        """Send one request under the global lock.

        The single chokepoint for every Gnani call:
          * circuit breaker: after 401/402 every call fails fast with 503 voice_unavailable for
            GNANI_BREAKER_S (routes turn it into text-only; TTS still serves the cache / seed_cache);
          * budget: security.take_gnani_budget(kind) (public mode only) -> 429 "budget";
          * one total deadline (GNANI_DEADLINE_S, default 45 s) that includes waiting for the lock;
          * retries ONLY on 429 and connection errors. A POST that timed out or got a 5xx may already
            have been processed (and billed), so it is not sent again.
        """
        if time.monotonic() < self._breaker_until:
            raise GnaniError(503, "voice_unavailable", "Voice is unavailable right now. Showing text instead.")
        from .security import take_gnani_budget  # lazy: security imports models, not gnani

        take_gnani_budget(kind)
        url = self.base_url + path
        headers = self._headers(kwargs.pop("headers", None))
        delay = self.backoff_s
        last_exc: Exception | None = None
        t0 = time.monotonic()
        deadline = t0 + (self.deadline_s if self.deadline_s is not None else config.gnani_deadline_s())
        lock = _lock()
        try:
            await asyncio.wait_for(lock.acquire(), timeout=max(0.01, deadline - time.monotonic()))
        except (asyncio.TimeoutError, TimeoutError):
            raise GnaniError(503, "BUSY", "Voice is busy right now (another request is still running).")
        waited = time.monotonic() - t0
        LOCK_STATS["last_wait_s"] = round(waited, 3)
        LOCK_STATS["max_wait_s"] = max(LOCK_STATS["max_wait_s"], round(waited, 3))
        if waited > 0.5:
            log.info("gnani %s waited %.2f s for the 1-request lock", kind, waited)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
                for attempt in range(1, self.max_attempts + 1):
                    left = deadline - time.monotonic()
                    if left <= 0.05:
                        break
                    timeout = httpx.Timeout(min(self.timeout_s, left), connect=min(15.0, left))
                    try:
                        resp = await client.request(method, url, headers=headers, timeout=timeout, **kwargs)
                    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                        last_exc = exc  # never reached Gnani: safe to send again
                        log.warning("gnani %s %s: %s (attempt %d)", kind, path, type(exc).__name__, attempt)
                    except httpx.TimeoutException as exc:
                        log.warning("gnani %s %s: %s, not retried", kind, path, type(exc).__name__)
                        raise GnaniError(504, "TIMEOUT", f"{type(exc).__name__}: no answer in time")
                    except httpx.TransportError as exc:
                        log.warning("gnani %s %s: %s, not retried", kind, path, type(exc).__name__)
                        raise GnaniError(0, "NETWORK_ERROR", type(exc).__name__)
                    else:
                        if resp.status_code < 400:
                            # response headers only (never our request headers): used by M0 to look for credit info
                            self.last_response_headers = {
                                k: v for k, v in resp.headers.items()
                                if k.lower() not in ("set-cookie", "x-api-key-id") and self._key not in v}
                            return resp
                        code, msg = _parse_error(resp)
                        if resp.status_code in BREAKER_STATUSES:
                            self._trip(resp.status_code, code)
                        if resp.status_code not in RETRYABLE or attempt == self.max_attempts:
                            raise GnaniError(resp.status_code, code, msg)
                        log.warning("gnani %s %s -> %d %s (attempt %d)", kind, path, resp.status_code, code, attempt)
                        last_exc = GnaniError(resp.status_code, code, msg)
                        ra = resp.headers.get("Retry-After", "")
                        if ra.isdigit():
                            delay = max(delay, float(ra))
                    if attempt < self.max_attempts:
                        if time.monotonic() + delay >= deadline:
                            break
                        STATS.retries += 1
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 8.0)  # multipart bodies from bytes are re-sendable
        finally:
            lock.release()
        if isinstance(last_exc, GnaniError):
            raise last_exc
        if last_exc is None:
            raise GnaniError(504, "TIMEOUT", "Gnani call deadline reached")
        raise GnaniError(0, "NETWORK_ERROR", f"{type(last_exc).__name__} after {self.max_attempts} attempts")

    # ------------------------------------------------------------------ STT
    async def stt(self, audio_bytes: bytes, filename: str, language_code: str = "indic-auto",
                  fmt: str = "transcribe", keyterms: Iterable[str] | None = None, topic: str | None = None,
                  previous_text: str | None = None, model: str = "prisma-v3.0",
                  speaker_names: Iterable[str] | None = None) -> dict[str, Any]:
        """Transcribe one clip (<= 30 s) with Prisma. Returns the API body plus client timing.

        The file-name extension tells the API the format (wav, mp3, ogg, flac, aac, m4a).
        """
        if model not in STT_MODELS:
            raise ValueError(f"model must be one of {STT_MODELS}")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in STT_EXTS:
            raise ValueError(f"unsupported extension .{ext}; convert to one of {STT_EXTS} first")
        if not audio_bytes:
            raise ValueError("empty audio")
        v3 = model == "prisma-v3.0"
        if fmt not in (STT_FORMATS_V3 if v3 else STT_FORMATS_V25):
            raise ValueError(f"format {fmt!r} not supported by {model}")
        langs = [c.strip() for c in language_code.split(",") if c.strip()]
        if v3:
            if langs != ["indic-auto"]:
                if not 1 <= len(langs) <= 4 or any(c not in STT_LANGS for c in langs):
                    raise ValueError(f"language_code must be indic-auto or 1-4 of {STT_LANGS}")
        elif len(langs) != 1 or langs[0] not in STT_LANGS:
            raise ValueError("prisma-v2.5 takes exactly one language code")

        data: dict[str, str] = {"language_code": ",".join(langs), "format": fmt}
        if v3:
            data["model"] = "prisma-v3.0"  # omit for v2.5 (the default model)
            kt = [k.strip() for k in (keyterms or []) if k and k.strip()]
            if kt:
                data["keyterms"] = json.dumps(kt[:200], ensure_ascii=False)
            if topic and topic.strip():
                data["topic"] = topic.strip()[:1600]
            # Docs say "no minimum", but their own sample code guards with >= 12 chars.
            if previous_text and len(previous_text.strip()) >= 12:
                data["previous_text"] = previous_text.strip()[-600:]
            names = [n.strip() for n in (speaker_names or []) if n and n.strip()]
            if names:
                data["speaker_names"] = json.dumps(names[:4], ensure_ascii=False)
        mime = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "flac": "audio/flac",
                "aac": "audio/aac", "m4a": "audio/mp4"}[ext]
        t0 = time.perf_counter()
        resp = await self._request("POST", STT_PATH, kind="stt",
                                   files={"audio_file": (filename, audio_bytes, mime)}, data=data)
        STATS.stt += 1
        body = resp.json()
        if not body.get("success", True):
            err = body.get("error") or {}
            raise GnaniError(resp.status_code, str(err.get("type", "STT_FAILED")), str(err.get("message", "")))
        body.setdefault("transcript", "")
        body["client_latency_s"] = round(time.perf_counter() - t0, 3)
        body.setdefault("model", model)
        return body

    # ------------------------------------------------------------------ TTS
    @staticmethod
    def audio_config(container: str = "ogg", sample_rate: int = 48000, bitrate: str = "64k") -> dict[str, Any]:
        if sample_rate not in TTS_SAMPLE_RATES:
            raise ValueError(f"sample_rate must be one of {TTS_SAMPLE_RATES}")
        cfg: dict[str, Any] = {"sample_rate": sample_rate, "num_channels": 1, "sample_width": 2, "container": container}
        if container == "ogg":
            cfg["encoding"] = "oggopus"  # same as container=ogg per docs
        elif container == "mp3":
            cfg["bitrate"] = bitrate
        elif container in ("wav", "raw"):
            cfg["encoding"] = "linear_pcm"
        else:
            raise ValueError("container must be ogg, mp3, wav or raw")
        return cfg

    async def tts(self, text: str, language: str, voice: str | None = None, container: str = "ogg",
                  model: str = TTS_MODEL_V3, sample_rate: int = 48000, speed: float | None = None,
                  bitrate: str = "64k") -> bytes:
        """Synthesize text with Timbre. Returns raw audio bytes in the requested container."""
        if not text or not text.strip():
            raise ValueError("empty text")
        if language not in TTS_LANGS:
            raise ValueError(f"language must be one of {TTS_LANGS}")
        if model == TTS_MODEL_V3:
            voice = voice or DEFAULT_VOICE.get(language, "Shivani")
            if voice not in TIMBRE_V3_VOICES:
                raise ValueError(f"voice {voice!r} is not a timbre-v3.0 voice")
        elif model == TTS_MODEL_V25:
            voice = voice or DEFAULT_VOICE_V25.get(language)
            if not voice:
                raise ValueError("timbre-v2.5 needs an explicit voice")
        else:
            raise ValueError("model must be timbre-v3.0 or timbre-v2.5")
        payload: dict[str, Any] = {"text": text, "voice": voice, "model": model, "language": language,
                                   "audio_config": self.audio_config(container, sample_rate, bitrate)}
        if speed is not None:
            payload["speed"] = max(0.85, min(1.15, float(speed)))
        resp = await self._request("POST", TTS_PATH, kind="tts", json=payload)
        STATS.tts += 1
        return _audio_or_raise(resp)

    # ------------------------------------------------------------------ Voice clone
    async def vc_embedding(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """Create a speaker embedding from 5-30 s of clean reference audio.

        Returns {"embedding": str, "shape": [1, 768], "dtype": "torch.bfloat16"}; cache it.
        Verified 9 Nov 2026 (docs/research/04_gnani_feasibility.md): a 19.3 s 24 kHz mono WAV gives a
        [1, 768] torch.bfloat16 embedding (4,096-char string) in ~1.2 s, and the embedding speaks
        Hinglish, Hindi, Telugu and English (cross-lingual) through vc_tts().
        """
        if not audio_bytes:
            raise ValueError("empty audio")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "flac": "audio/flac",
                "m4a": "audio/mp4", "aac": "audio/aac"}.get(ext, "application/octet-stream")
        resp = await self._request("POST", VC_EMBED_PATH, kind="vc_embed",
                                   files={"audio_file": (filename, audio_bytes, mime)})
        STATS.vc_embed += 1
        body = resp.json()
        emb = ((body.get("data") or {}).get("voice_clone_embedding")) if isinstance(body, dict) else None
        if not emb or "embedding" not in emb:
            raise GnaniError(resp.status_code, "VC_NO_EMBEDDING", str(body)[:300])
        return {"embedding": emb["embedding"], "shape": emb.get("shape", [1, 768]), "dtype": emb.get("dtype", "torch.bfloat16")}

    async def vc_tts(self, text: str, speaker_embedding: dict[str, Any], container: str = "wav",
                     sample_rate: int = 24000) -> bytes:
        """Synthesize text in a cloned voice (model vachana-vc-v1; no language/voice fields).

        Default WAV/24 kHz is the verified format; convert with audio.whatsappify() for OGG.
        Audio tags are a timbre-v3.0 feature; do not rely on them here. Write amounts as words or
        with Devanagari around them (text normalisation is auto-detected from the script).
        """
        if not text or not text.strip():
            raise ValueError("empty text")
        if not isinstance(speaker_embedding, dict) or not all(
                k in speaker_embedding for k in ("embedding", "shape", "dtype")):
            raise ValueError("speaker_embedding needs embedding, shape and dtype")
        if sample_rate > VC_MAX_SAMPLE_RATE:
            raise ValueError("voice-clone sample_rate max is 44100")
        speaker_embedding = {k: speaker_embedding[k] for k in ("embedding", "shape", "dtype")}
        payload = {"text": text, "model": VC_MODEL, "speaker_embedding": speaker_embedding,
                   "audio_config": self.audio_config(container, sample_rate)}
        resp = await self._request("POST", TTS_PATH, kind="vc_tts", json=payload)
        STATS.vc_tts += 1
        return _audio_or_raise(resp)


def _audio_or_raise(resp: httpx.Response) -> bytes:
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        code, msg = _parse_error(resp)
        raise GnaniError(resp.status_code, code, msg or "JSON body where audio was expected")
    if not resp.content:
        raise GnaniError(resp.status_code, "EMPTY_AUDIO", "empty audio body")
    return resp.content


_default: GnaniClient | None = None


def get_client() -> GnaniClient:
    global _default
    if _default is None:
        _default = GnaniClient()
    return _default


# Convenience module-level functions (signatures from the build brief).
async def stt(audio_bytes: bytes, filename: str, language_code: str = "indic-auto", fmt: str = "transcribe",
              keyterms: Iterable[str] | None = None, topic: str | None = None, previous_text: str | None = None,
              model: str = "prisma-v3.0") -> dict[str, Any]:
    return await get_client().stt(audio_bytes, filename, language_code, fmt, keyterms, topic, previous_text, model)


async def tts(text: str, language: str, voice: str | None = None, container: str = "ogg",
              model: str = TTS_MODEL_V3, sample_rate: int = 48000, speed: float | None = None) -> bytes:
    return await get_client().tts(text, language, voice, container, model, sample_rate, speed)


async def vc_embedding(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    return await get_client().vc_embedding(audio_bytes, filename)


async def voice_clone_embedding(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    """Alias of vc_embedding(): 5-30 s reference clip -> {"embedding", "shape", "dtype"}."""
    return await get_client().vc_embedding(audio_bytes, filename)


async def vc_tts(text: str, speaker_embedding: dict[str, Any], container: str = "wav", sample_rate: int = 24000) -> bytes:
    return await get_client().vc_tts(text, speaker_embedding, container, sample_rate)
