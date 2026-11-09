"""PDF shaping plumbing and the LLM provider chain (mocked; no network)."""
from __future__ import annotations

import json

import httpx

from app import config, llm, pdf


def test_pdf_renders_telugu_hindi_latin():
    data = pdf.render_pdf([
        pdf.Block("Baaki (synthetic test)", size=16),
        "జీతం 12,000 రూపాయలు, ఇంకా 4,500 బాకీ ఉంది.",
        "पगार 12,000 रुपये, अभी 4,500 बाकी है।",
    ], title="test")
    assert data[:5] == b"%PDF-"
    assert len(data) > 5000
    # all three fonts are embedded
    for name in (b"NotoSans", b"NotoSansTelugu", b"NotoSansDevanagari"):
        assert name in data


def test_script_detection():
    assert pdf._script("జీతం") == "te"
    assert pdf._script("पगार") == "hi"
    assert pdf._script("salary 100") == "latin"


SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}


def test_llm_disabled_without_keys():
    assert llm.configured() is False


async def test_llm_groq_strict_then_fallback(monkeypatch):
    monkeypatch.setattr(config, "groq_key", lambda: "gk")
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((body["model"], body["response_format"]["type"]))
        assert request.headers["Authorization"] == "Bearer gk"
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": "schema"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"x": 7}'}}]})

    out = await llm.json_call("sys", "user", SCHEMA, transport=httpx.MockTransport(handler))
    assert out == {"x": 7}
    assert seen == [("openai/gpt-oss-20b", "json_schema"), ("openai/gpt-oss-120b", "json_object")]
    assert llm.LAST_PROVIDER["provider"].startswith("groq:openai/gpt-oss-120b")


async def test_llm_gemini_first_when_selected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "gemini_key", lambda: "gem")

    def handler(request):
        assert "generativelanguage.googleapis.com" in str(request.url)
        body = json.loads(request.content)
        assert "additionalProperties" not in json.dumps(body["generationConfig"]["responseSchema"])
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"x": 3}'}]}}]})

    out = await llm.json_call("sys", "user", SCHEMA, transport=httpx.MockTransport(handler))
    assert out == {"x": 3}


async def test_llm_none_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setattr(config, "groq_key", lambda: "gk")
    assert await llm.json_call("s", "u", SCHEMA) is None
