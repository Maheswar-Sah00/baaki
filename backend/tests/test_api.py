"""API plumbing tests: offline, with a mocked Gnani transport. No network, no keys."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import stt_service, tts_cache
from app.main import app

from .conftest import multipart_fields


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_both_paths(client):
    for path in ("/health", "/api/health"):
        r = client.get(path)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["gnani"] is False  # keys are blanked in tests
        assert "llm" in body


def test_voices_lists_telugu_and_hinglish(client):
    body = client.get("/api/voices").json()
    v3 = body["defaults"]["timbre-v3.0"]
    assert v3["te-IN"] and v3["hi-en"]
    assert body["defaults"]["timbre-v2.5"]["hi-en"] == "Poorvi"
    assert body["stt_lang_presets"]["te"] == "te-IN,en-IN"


@pytest.mark.parametrize("given,expected", [
    (None, "te-IN,hi-IN,en-IN"),
    ("te", "te-IN,en-IN"),
    ("hinglish", "hi-IN,en-IN"),
    ("Hinglish", "hi-IN,en-IN"),
    ("indic-auto", "indic-auto"),
    ("te-IN,hi-IN", "te-IN,hi-IN"),
])
def test_lang_presets(given, expected):
    assert stt_service.parse_langs(given) == expected


@pytest.mark.parametrize("bad", ["xx-IN", "te-IN,te-IN", "te-IN,hi-IN,en-IN,ta-IN,kn-IN"])
def test_lang_rejects(bad):
    with pytest.raises(ValueError):
        stt_service.parse_langs(bad)


def test_stt_telugu(client, mock_gnani, short_ogg):
    def reply(request):
        f = multipart_fields(request)
        assert f["language_code"] == "te-IN,en-IN"
        assert f["format"] == "transcribe"
        assert f["model"] == "prisma-v3.0"
        assert f["audio_file.filename"].endswith(".ogg")
        assert request.headers["X-API-Key-ID"] == "test-key"
        return httpx.Response(200, json={"success": True, "transcript": "నాకు 4,500 బాకీ ఉంది",
                                         "detected_language_code": "te-IN"})

    mock_gnani.push("/stt/v3", reply)
    r = client.post("/api/stt", files={"audio": ("note.ogg", short_ogg, "audio/ogg")}, data={"lang": "te"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"] == "నాకు 4,500 బాకీ ఉంది"
    assert body["detected_language_code"] == "te-IN"
    assert body["language_code"] == "te-IN,en-IN"
    assert len(body["chunks"]) == 1


def test_stt_hinglish_webm_is_converted(client, mock_gnani, short_wav):
    from app import audio

    webm = audio._convert(short_wav, "wav", "webm", ["-c:a", "libopus", "-b:a", "24k", "-f", "webm"])

    def reply(request):
        f = multipart_fields(request)
        assert f["language_code"] == "hi-IN,en-IN"
        assert f["audio_file.filename"].endswith(".wav")  # webm is not native to Prisma REST
        return httpx.Response(200, json={"success": True, "transcript": "madam ne 3 mahine ki salary nahi di",
                                         "detected_language_code": "hi-IN"})

    mock_gnani.push("/stt/v3", reply)
    r = client.post("/api/stt", files={"audio": ("recording.webm", webm, "audio/webm;codecs=opus")},
                    data={"lang": "hinglish"})
    assert r.status_code == 200, r.text
    assert "salary" in r.json()["transcript"]


def test_stt_rejects_bad_input(client, mock_gnani, short_ogg):
    assert client.post("/api/stt", files={"audio": ("x.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/stt", files={"audio": ("x.ogg", short_ogg, "audio/ogg")},
                       data={"mode": "nope"}).status_code == 400
    assert client.post("/api/stt", files={"audio": ("x.ogg", short_ogg, "audio/ogg")},
                       data={"lang": "zz"}).status_code == 400


def test_stt_rate_limit_maps_to_503(client, mock_gnani, short_ogg):
    mock_gnani.default["/stt/v3"] = httpx.Response(
        429, json={"detail": {"error_code": "RATE_LIMITED", "message": "Only 1 active request is allowed at a time"}})
    r = client.post("/api/stt", files={"audio": ("x.ogg", short_ogg, "audio/ogg")})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "RATE_LIMITED"
    assert "test-key" not in r.text


def test_tts_is_cached(client, mock_gnani, short_ogg):
    calls = []

    def reply(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = reply
    payload = {"text": "మీ జీతం బాకీ ఉంది", "lang": "te-IN"}
    r1 = client.post("/api/tts", json=payload)
    r2 = client.post("/api/tts", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers["x-tts-cache"] == "miss" and r2.headers["x-tts-cache"] == "hit"
    assert r1.content[:4] == b"OggS"
    assert len(calls) == 1
    assert calls[0]["voice"] == "Kalpana" and calls[0]["language"] == "te-IN" and calls[0]["model"] == "timbre-v3.0"


def test_tts_hinglish_v25_poorvi(client, mock_gnani, short_ogg):
    seen = {}

    def reply(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = reply
    r = client.post("/api/tts", json={"text": "Aapki salary baaki hai", "lang": "hi-en", "model": "timbre-v2.5"})
    assert r.status_code == 200, r.text
    assert seen["voice"] == "Poorvi" and seen["language"] == "hi-en" and seen["model"] == "timbre-v2.5"


def test_tts_cache_key_separates_models():
    a = tts_cache.cache_key("x", "hi-en", "Shivani")
    b = tts_cache.cache_key("x", "hi-en", "Shivani", model="timbre-v2.5")
    assert a != b


def test_tts_validation(client):
    assert client.post("/api/tts", json={"text": "hi", "lang": "fr-FR"}).status_code == 422
    assert client.post("/api/tts", json={"text": "hi", "lang": "te-IN", "voice": "Nobody"}).status_code == 400


@pytest.mark.parametrize("method,path", [
    ("post", "/api/cases"),
    ("get", "/api/cases/1"),
    ("post", "/api/cases/1/extract"),
    ("get", "/api/cases/1/dues"),
    ("post", "/api/cases/1/letters"),
    ("get", "/api/cases/1/letters/1/pdf"),
    ("post", "/api/cases/1/letters/1/voice"),
])
def test_placeholders_are_501(client, method, path):
    r = getattr(client, method)(path)
    assert r.status_code == 501
    assert r.json()["detail"]["error"] == "not_implemented"
