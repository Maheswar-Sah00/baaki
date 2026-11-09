"""LLM client for structured JSON (fact extraction will call this). Adapted from Deposit Wapas extract.py.

Provider chain (LLM_PROVIDER in .env):
  groq (default):  Groq openai/gpt-oss-20b strict json_schema -> gpt-oss-120b json_object -> Gemini (only if
                   GEMINI_BACKUP=1)
  gemini:          Gemini native REST first, then Groq
  none:            disabled; json_call returns None
Keys go only in request headers to the official endpoints, never in logs or exceptions.

Rule for every caller: the LLM may label or structure what the user said, but every number it returns
must be checked against the deterministic parsers in app.lang before it is used.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

import httpx

from . import config

log = logging.getLogger("llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

LAST_PROVIDER: dict[str, str] = {}


def _strip_additional(schema: Any) -> Any:
    """Gemini responseSchema is an OpenAPI subset: drop additionalProperties."""
    if isinstance(schema, dict):
        return {k: _strip_additional(v) for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_strip_additional(v) for v in schema]
    return schema


async def _groq(client: httpx.AsyncClient, model: str, mode: str, system: str, user: str,
                schema: dict, name: str, max_tokens: int) -> Any:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_completion_tokens": max_tokens,
    }
    if mode == "json_schema":
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
    else:
        payload["response_format"] = {"type": "json_object"}
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
        payload["include_reasoning"] = False
    r = await client.post(GROQ_URL, headers={"Authorization": f"Bearer {config.groq_key()}"}, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"groq {model} {mode} -> HTTP {r.status_code}")
    return json.loads(r.json()["choices"][0]["message"]["content"])


async def _gemini(client: httpx.AsyncClient, system: str, user: str, schema: dict) -> Any:
    """Native endpoint + x-goog-api-key (AQ. keys fail on the OpenAI-compatible route)."""
    url = f"{GEMINI_BASE}/models/{config.gemini_model()}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                             "responseSchema": _strip_additional(schema)},
    }
    r = await client.post(url, headers={"x-goog-api-key": config.gemini_key()}, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"gemini -> HTTP {r.status_code}")
    parts = r.json()["candidates"][0]["content"]["parts"]
    return json.loads("".join(p.get("text", "") for p in parts))


def configured() -> bool:
    p = config.llm_provider()
    if p in ("none", "off", ""):
        return False
    return bool(config.groq_key() or (config.gemini_key() and config.gemini_backup_enabled()))


async def json_call(system: str, user: str, schema: dict, *, name: str = "result",
                    validate: Callable[[Any], Any] | None = None, max_tokens: int = 800,
                    transport: httpx.AsyncBaseTransport | None = None, timeout_s: float = 20.0) -> Any | None:
    """Return the first provider's parsed JSON (after `validate`, which may raise or return a cleaned
    value; a falsy result tries the next provider). Returns None if every provider fails."""
    LAST_PROVIDER.clear()
    provider = config.llm_provider()
    if provider in ("none", "off", ""):
        return None
    steps: list[tuple[str, Callable[[httpx.AsyncClient], Awaitable[Any]]]] = []
    if config.groq_key():
        m1, m2 = config.groq_model(), config.groq_fallback_model()
        steps += [(f"groq:{m1}:json_schema", lambda c: _groq(c, m1, "json_schema", system, user, schema, name, max_tokens)),
                  (f"groq:{m2}:json_object", lambda c: _groq(c, m2, "json_object", system, user, schema, name, max_tokens))]
    if config.gemini_key() and config.gemini_backup_enabled():
        gem = (f"gemini:{config.gemini_model()}", lambda c: _gemini(c, system, user, schema))
        steps = [gem] + steps if provider == "gemini" else steps + [gem]
    async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as client:
        for pname, call in steps:
            try:
                out = await call(client)
                if validate is not None:
                    out = validate(out)
            except Exception as exc:  # network, HTTP, JSON, validation
                log.warning("llm provider %s failed: %s", pname, str(exc)[:120])
                continue
            if out:
                LAST_PROVIDER["provider"] = pname
                return out
    return None
