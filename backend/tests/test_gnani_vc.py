"""Offline tests for the voice-clone client (mocked HTTP; no network, no real key)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app import gnani

from .conftest import multipart_fields

EMB = {"embedding": "QUJD" * 1024, "shape": [1, 768], "dtype": "torch.bfloat16"}


def _run(coro):
    return asyncio.run(coro)


def test_voice_clone_embedding_request_and_parse(mock_gnani, short_wav):
    mock_gnani.push(gnani.VC_EMBED_PATH, httpx.Response(200, json={
        "success": True, "message": "Voice embeddings generated successfully",
        "data": {"voice_clone_embedding": EMB}}))
    emb = _run(gnani.voice_clone_embedding(short_wav, "ref.wav"))
    assert emb == EMB
    req = mock_gnani.requests[-1]
    assert req.method == "POST" and req.url.path == "/api/v1/tts/voice-clone/embeddings"
    assert req.headers["X-API-Key-ID"] == "test-key"
    fields = multipart_fields(req)
    assert fields["audio_file.filename"] == "ref.wav"
    assert b"Content-Type: audio/wav" in req.content


def test_voice_clone_embedding_missing_data_raises(mock_gnani, short_wav):
    mock_gnani.push(gnani.VC_EMBED_PATH, httpx.Response(200, json={"success": True, "data": {}}))
    with pytest.raises(gnani.GnaniError) as ei:
        _run(gnani.vc_embedding(short_wav, "ref.wav"))
    assert ei.value.code == "VC_NO_EMBEDDING"
    assert "test-key" not in str(ei.value)


def test_voice_clone_embedding_rejects_empty():
    with pytest.raises(ValueError):
        _run(gnani.GnaniClient(api_key="k").vc_embedding(b"", "ref.wav"))


def test_vc_tts_payload(mock_gnani):
    mock_gnani.push(gnani.TTS_PATH, httpx.Response(200, content=b"RIFFfakewav", headers={"content-type": "audio/wav"}))
    extra = {**EMB, "unused": 1}
    out = _run(gnani.vc_tts("Madam, baarah hazaar rupaye baaki hain.", extra))
    assert out == b"RIFFfakewav"
    req = mock_gnani.requests[-1]
    assert req.url.path == "/api/v1/tts/inference"
    body = json.loads(req.content)
    assert body["model"] == "vachana-vc-v1"
    assert body["speaker_embedding"] == EMB  # only the three documented fields are sent
    assert body["audio_config"] == {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                                    "container": "wav", "encoding": "linear_pcm"}
    assert "voice" not in body and "language" not in body


def test_vc_tts_validation():
    c = gnani.GnaniClient(api_key="k")
    with pytest.raises(ValueError):
        _run(c.vc_tts("  ", EMB))
    with pytest.raises(ValueError):
        _run(c.vc_tts("hello", {"embedding": "x"}))
    with pytest.raises(ValueError):
        _run(c.vc_tts("hello", EMB, sample_rate=48000))


def test_vc_tts_json_error_and_500_retry(mock_gnani):
    mock_gnani.push(gnani.TTS_PATH, httpx.Response(429, json={"detail": {
        "error_code": "RATE_LIMITED", "message": "Only 1 active request is allowed at a time.", "status_code": 429}}))
    mock_gnani.push(gnani.TTS_PATH, httpx.Response(400, json={
        "success": False, "message": "Invalid request: Field required at body -> text", "status_code": 400}))
    with pytest.raises(gnani.GnaniError) as ei:
        _run(gnani.vc_tts("hello", EMB))
    assert ei.value.status == 400 and "Field required" in ei.value.message
    assert len(mock_gnani.requests) == 2  # 429 retried once, 400 not retried
