"""Listen-twice guard (G07). Offline: Timbre and Prisma are mocked."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import verify_guard
from app.main import app

from .b_data import make_case, tts_ok
from .conftest import multipart_fields


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _stt(transcript: str, seen: list | None = None):
    def handler(request):
        if seen is not None:
            seen.append(multipart_fields(request))
        return httpx.Response(200, json={"success": True, "transcript": transcript,
                                         "detected_language_code": "hi-IN"})
    return handler


def _make_note(client, mock_gnani, short_ogg, lang: str = "hi-en") -> dict:
    ids = make_case()
    mock_gnani.default["/api/v1/tts/inference"] = tts_ok(short_ogg)
    r = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "lang": lang})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audio_url"], body
    return body


def test_correct_note_is_verified(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg)
    seen: list = []
    heard = " ".join(note["speech"]).replace("Baaki ऐप", "बाकी अपने")   # real Prisma drift (feasibility t1)
    mock_gnani.push("/stt/v3", _stt(heard, seen))
    r = client.post(f"/api/verify/messages/{note['message_id']}")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["verified"] is True and v["amounts_ok"] is True
    assert sorted(v["amounts_expected"]) == [1000, 4000, 13000]
    assert sorted(v["amounts_heard"]) == [1000, 4000, 13000]
    assert v["missing"] == [] and v["extra"] == []
    assert v["total_expected"] == 13000 and v["total_heard"] is True
    assert v["disclosure_heard"] is True and v["ai_word_heard"] is True
    assert v["cached"] is False and v["stt_calls"] == 1
    assert v["language_code"] == "hi-IN,en-IN" and v["stt_mode"] == "codemix"
    assert seen[0]["language_code"] == "hi-IN,en-IN" and seen[0]["format"] == "codemix"
    for k in ("transcript", "ms", "audio_sha256", "checked_at"):
        assert k in v


def test_misheard_amount_warns(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg)
    heard = " ".join(note["speech"]).replace("तेरह हज़ार रुपये", "तीन हज़ार रुपये")
    mock_gnani.push("/stt/v3", _stt(heard))
    v = client.post(f"/api/verify/messages/{note['message_id']}").json()
    assert v["verified"] is False and v["amounts_ok"] is False
    assert v["missing"] == [13000] and v["extra"] == [3000]
    assert v["total_heard"] is False
    assert v["disclosure_heard"] is True


def test_missing_disclosure_warns(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg)
    heard = " ".join(note["speech"][1:])          # the AI label sentence was not heard
    mock_gnani.push("/stt/v3", _stt(heard))
    v = client.post(f"/api/verify/messages/{note['message_id']}").json()
    assert v["amounts_ok"] is True
    assert v["disclosure_heard"] is False and v["verified"] is False


def test_cache_hit_costs_nothing_and_get_returns_it(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg)
    mid = note["message_id"]
    assert client.get(f"/api/verify/messages/{mid}").status_code == 404
    mock_gnani.push("/stt/v3", _stt(" ".join(note["speech"])))
    first = client.post(f"/api/verify/messages/{mid}").json()
    stt_before = sum(1 for q in mock_gnani.requests if q.url.path == "/stt/v3")
    again = client.post(f"/api/verify/messages/{mid}").json()          # nothing mocked: must be cached
    stt_after = sum(1 for q in mock_gnani.requests if q.url.path == "/stt/v3")
    assert stt_after == stt_before == 1
    assert again["cached"] is True and again["verified"] == first["verified"] is True
    got = client.get(f"/api/verify/messages/{mid}")
    assert got.status_code == 200 and got.json()["cached"] is True
    assert list(verify_guard.cache_dir().glob(f"m{mid}_*.json"))


def test_telugu_note_uses_telugu_codemix(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg, lang="te-IN")
    seen: list = []
    mock_gnani.push("/stt/v3", _stt(" ".join(note["speech"]), seen))
    v = client.post(f"/api/verify/messages/{note['message_id']}").json()
    assert seen[0]["language_code"] == "te-IN,en-IN" and seen[0]["format"] == "codemix"
    assert v["verified"] is True, v
    assert 13000 in v["amounts_heard"]


def test_stt_failure_is_a_clear_error_not_a_pass(client, mock_gnani, short_ogg):
    note = _make_note(client, mock_gnani, short_ogg)
    mock_gnani.default["/stt/v3"] = httpx.Response(400, json={"detail": {"error_code": "BAD", "message": "x"}})
    r = client.post(f"/api/verify/messages/{note['message_id']}")
    assert r.status_code == 502
    assert r.json()["detail"]["error"] == "stt_failed"
    assert client.get(f"/api/verify/messages/{note['message_id']}").status_code == 404   # nothing cached


def test_errors(client):
    assert client.post("/api/verify/messages/999").status_code == 404
    ids = make_case()
    r = client.post(f"/api/cases/{ids['case_id']}/messages/polite", json={"use_llm": False, "audio": False})
    mid = r.json()["message_id"]
    r = client.post(f"/api/verify/messages/{mid}")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "no_audio"


@pytest.mark.parametrize("heard,ok", [
    ("यह एक एआई वॉइस सन्देश है। इसे लक्ष्मी की अनुमति से उनकी ओर से बाकी एप ने बनाया है।", True),
    ("ये एक ए आई वाइस संदेश है इसे लक्ष्मी की अनुमति से बाकी अपने बनाया है", True),
    ("नमस्ते शर्मा जी, मेरी salary अभी तक नहीं मिली है", False),
    ("यह एक वॉइस संदेश है। इसे लक्ष्मी की अनुमति से, उनकी ओर से, Baaki ऐप ने बनाया है।", False),  # no "AI"
])
def test_disclosure_fuzzy_match(heard, ok):
    exp = "यह एक AI वॉइस संदेश है। इसे लक्ष्मी की अनुमति से, उनकी ओर से, Baaki ऐप ने बनाया है।"
    assert verify_guard.disclosure_match(exp, heard)["heard"] is ok


def test_compare_amounts_multiset():
    assert verify_guard.compare_amounts([4000, 4000, 13000], [4000, 13000]) == \
        {"ok": False, "missing": [4000], "extra": []}
