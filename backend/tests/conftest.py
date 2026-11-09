"""Offline test helpers: synthetic audio and a mocked Gnani transport. No network, no keys."""
from __future__ import annotations

import math
import struct

import pytest

from app import audio, config, gnani

SR = 16000


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch):
    """Tests are offline: blank every real key from .env so nothing can reach a real API.
    Tests that need a key patch it back with a fake value and a MockTransport."""
    for name in ("gnani_key", "groq_key", "gemini_key"):
        monkeypatch.setattr(config, name, lambda: "")
    monkeypatch.setattr(gnani, "_default", None)
    monkeypatch.delenv("STT_CONTEXT", raising=False)


def _tone_pcm(seconds: float, freq: float = 440.0, amp: float = 0.4) -> bytes:
    period = int(SR / freq) or 1
    one = b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * i / period))) for i in range(period))
    n = int(seconds * SR)
    reps = n // period + 1
    return (one * reps)[: n * 2]


def _silence_pcm(seconds: float) -> bytes:
    return b"\x00\x00" * int(seconds * SR)


def make_wav(pattern: list[tuple[str, float]]) -> bytes:
    """pattern like [("tone", 2.0), ("sil", 1.0), ...] -> 16 kHz mono WAV bytes."""
    pcm = b"".join(_tone_pcm(s) if kind == "tone" else _silence_pcm(s) for kind, s in pattern)
    return audio.wav_from_pcm(pcm, SR)


@pytest.fixture(scope="session")
def short_wav() -> bytes:
    return make_wav([("sil", 0.3), ("tone", 2.0), ("sil", 0.4), ("tone", 0.6)])


@pytest.fixture(scope="session")
def long_wav() -> bytes:
    # 66.4 s with clear pauses at ~20.5 s and ~46 s; speech-like runs in between
    pat: list[tuple[str, float]] = []
    for _ in range(4):
        pat += [("tone", 4.5), ("sil", 0.2)]
    pat += [("tone", 1.2), ("sil", 1.0)]          # pause centred ~21.0 s
    for _ in range(5):
        pat += [("tone", 4.6), ("sil", 0.15)]
    pat += [("sil", 1.0)]                         # pause ~45.0-46.0 s
    for _ in range(4):
        pat += [("tone", 4.8), ("sil", 0.1)]
    return make_wav(pat)


@pytest.fixture(scope="session")
def short_ogg(short_wav) -> bytes:
    return audio.to_ogg_opus(short_wav, "wav")


class MockGnani:
    """Records requests; replies via a per-path handler list (FIFO) or a default."""

    def __init__(self):
        self.requests: list = []
        self.queue: dict[str, list] = {}
        self.default: dict = {}

    def push(self, path: str, response):
        self.queue.setdefault(path, []).append(response)

    def __call__(self, request):
        import httpx

        self.requests.append(request)
        path = request.url.path
        q = self.queue.get(path)
        resp = q.pop(0) if q else self.default.get(path)
        if resp is None:
            return httpx.Response(404, json={"detail": {"error_code": "NOT_MOCKED", "message": path}})
        return resp(request) if callable(resp) else resp


@pytest.fixture
def mock_gnani(monkeypatch):
    import httpx

    m = MockGnani()
    client = gnani.GnaniClient(api_key="test-key", base_url="https://mock.gnani.local",
                               transport=httpx.MockTransport(m), backoff_s=0.0)
    monkeypatch.setattr(gnani, "_default", client)
    return m


def multipart_fields(request) -> dict[str, str]:
    """Parse simple text fields (and file names) from a multipart request body."""
    import re

    body = request.content
    ctype = request.headers["content-type"]
    boundary = ctype.split("boundary=")[1].encode()
    out: dict[str, str] = {}
    for part in body.split(b"--" + boundary):
        if b"Content-Disposition" not in part:
            continue
        head, _, value = part.partition(b"\r\n\r\n")
        name = re.search(rb'name="([^"]+)"', head).group(1).decode()
        fn = re.search(rb'filename="([^"]+)"', head)
        if fn:
            out[name + ".filename"] = fn.group(1).decode()
            continue
        out[name] = value.rstrip(b"\r\n").decode("utf-8")
    return out


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Every test gets its own in-memory database, media folder, TTS cache and data dir, so nothing
    a test writes (e.g. a mocked TTS reply) can land in backend/data or backend/seed_cache."""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import create_engine

    from app import db, storage

    db.set_engine(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "tts_cache"))
    monkeypatch.setattr(config, "SEED_CACHE_DIR", tmp_path / "seed_cache")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    storage.set_storage(None)
    yield
    db.set_engine(None)
    storage.set_storage(None)