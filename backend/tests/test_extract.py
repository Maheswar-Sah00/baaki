"""app.extract: the LLM only structures; rupees come from the parsers. LLM is mocked (no network)."""
from __future__ import annotations

import json

import httpx
import pytest

from app import config, extract, llm

SHARMA = ("Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina, aur do din bimar thi to ek hazaar "
          "kaat liya. Roz do ghante jhadu pocha karti hoon.")


async def test_parser_only_when_llm_off(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    r = await extract.extract_facts(SHARMA, "hinglish")
    f = r["facts"]
    assert r["source"] == "parser"
    assert f["employer_name"] == "Sharma ji"
    assert f["monthly_wage"] == 4000 and f["months_unpaid"] == 3 and f["hours_per_day"] == 2
    assert f["deductions"] == [{"amount": 1000, "reason": "sick", "days_absent": 2}]
    assert f["work_type"] == "housekeeping"


async def test_parser_only_without_key():
    assert not llm.configured()  # conftest blanks the keys
    r = await extract.extract_facts(SHARMA, "hinglish")
    assert r["source"] == "parser" and r["facts"]["monthly_wage"] == 4000


async def test_telugu_month_names_and_negated_name(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    t = "రెడ్డి గారు కాదు, శర్మ గారు. ఆగస్టు, సెప్టెంబర్, అక్టోబర్ జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు. ముందు రెండు వేలు అడ్వాన్స్ తీసుకున్నా."
    f = (await extract.extract_facts(t, "te"))["facts"]
    assert f["employer_name"] == "శర్మ గారు"
    assert f["unpaid_month_numbers"] == [8, 9, 10] and f["months_unpaid"] == 3
    assert f["monthly_wage"] == 4000 and f["advance_outstanding"] == 2000


def _groq(monkeypatch, payload_or_fn):
    monkeypatch.setattr(config, "groq_key", lambda: "gk")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        content = payload_or_fn(body) if callable(payload_or_fn) else payload_or_fn
        if isinstance(content, httpx.Response):
            return content
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    real = llm.json_call

    async def patched(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return await real(*a, **kw)

    monkeypatch.setattr(llm, "json_call", patched)
    return calls


def _llm_out(**over):
    base = {"employer_name": "Sharma ji", "work_type": "housekeeping", "hours_per_day": 2, "days_per_week": None,
            "months_unpaid": 3, "unpaid_month_names": [], "dismissed": False,
            "amount_roles": [{"id": "c2", "role": "monthly_wage", "reason": "none", "days_absent": None},
                             {"id": "c4", "role": "deduction", "reason": "sick", "days_absent": 2}],
            "reasons": ["salary not paid for three months"]}
    base.update(over)
    return base


async def test_llm_roles_parser_values(monkeypatch):
    calls = _groq(monkeypatch, _llm_out())
    r = await extract.extract_facts(SHARMA, "hinglish")
    assert r["source"] == "llm+parser"
    f = r["facts"]
    assert f["monthly_wage"] == 4000 and f["deductions"][0]["amount"] == 1000
    assert f["reasons"] == ["salary not paid for three months"]
    # the prompt carries the parser's amounts with ids; strict schema is sent
    prompt = calls[0]["messages"][1]["content"]
    assert "c2" in prompt and "4000" in prompt
    assert calls[0]["response_format"]["type"] == "json_schema"


async def test_llm_cannot_invent_ids_or_override_counts(monkeypatch):
    out = _llm_out(months_unpaid=5, amount_roles=[
        {"id": "c99", "role": "monthly_wage", "reason": "none", "days_absent": None},  # invented id -> dropped
        {"id": "c2", "role": "monthly_wage", "reason": "none", "days_absent": None}])
    _groq(monkeypatch, out)
    r = await extract.extract_facts(SHARMA, "hinglish")
    assert r["facts"]["monthly_wage"] == 4000
    assert r["facts"]["months_unpaid"] == 3  # the words say 3; the parser wins
    assert any("months unpaid" in w for w in r["warnings"])


async def test_llm_bad_json_falls_back_to_parser(monkeypatch):
    _groq(monkeypatch, {"nonsense": True})
    r = await extract.extract_facts(SHARMA, "hinglish")
    assert r["source"] == "parser" and r["facts"]["monthly_wage"] == 4000
    assert any("parser only" in w for w in r["warnings"])


async def test_llm_http_error_falls_back(monkeypatch):
    _groq(monkeypatch, httpx.Response(500, json={"error": "down"}))
    r = await extract.extract_facts(SHARMA, "hinglish")
    assert r["source"] == "parser" and r["facts"]["months_unpaid"] == 3


async def test_llm_month_names_must_appear_in_text(monkeypatch):
    t = "August aur September ki salary nahi mili, chaar hazaar mahina"
    _groq(monkeypatch, _llm_out(months_unpaid=3, unpaid_month_names=["August", "September", "October"],
                                amount_roles=[{"id": "c1", "role": "monthly_wage", "reason": "none",
                                               "days_absent": None}]))
    r = await extract.extract_facts(t, "hinglish")
    assert r["facts"]["unpaid_month_numbers"] == [8, 9]  # October was not said
    assert r["facts"]["months_unpaid"] == 2


def test_validate_rejects_non_object():
    with pytest.raises(ValueError):
        extract.validate_llm([1, 2], {"c1"})
    with pytest.raises(ValueError):
        extract.validate_llm({"employer_name": "x"}, {"c1"})
    clean = extract.validate_llm(_llm_out(hours_per_day=99, work_type="pilot"), {"c2", "c4"})
    assert clean["hours_per_day"] is None and clean["work_type"] == "unknown"


def test_schema_is_strict_compatible():
    def walk(s):
        if isinstance(s, dict) and s.get("type") == "object":
            assert s.get("additionalProperties") is False
            assert set(s["required"]) == set(s["properties"])
            for v in s["properties"].values():
                walk(v)
        if isinstance(s, dict) and s.get("type") == "array":
            walk(s["items"])
    walk(extract.SCHEMA)


@pytest.mark.parametrize("text,name", [
    ("Sharma ji ne paise nahi diye", "Sharma ji"), ("reddy garu ichharu", "Reddy garu"),
    ("మెహతా మేడమ్ ఇంట్లో పని", "మెహతా మేడమ్"), ("शर्मा जी ने पैसे नहीं दिए", "शर्मा जी"), ("no name here", None),
])
def test_employer_name(text, name):
    assert extract.find_employer_name(text) == name
