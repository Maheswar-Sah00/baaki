"""Case engine API: demo seed, dashboard, create, read-back, confirm, listen, diary. Gnani and LLM mocked."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import multipart_fields


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo(client):
    r = client.post("/api/demo/reset")
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_seed_story(client, demo):
    assert demo["totals"] == {"sharma": 12692.0, "reddy": 0.0, "mehta_shortfall": 7500.0, "rao": 14000.0}
    again = client.post("/api/demo/reset").json()
    assert again["totals"] == demo["totals"] and again["cases"] == demo["cases"]  # reproducible


def test_dashboard_cards(client, demo):
    d = client.get(f"/api/workers/{demo['workers']['lakshmi']}/dashboard").json()
    cards = {c["employer"]["name"]: c for c in d["cards"]}
    assert set(cards) == {"Sharma ji", "Reddy garu", "Mehta madam"}
    assert cards["Sharma ji"]["balance"] == 12692
    assert cards["Reddy garu"]["state"] == "paid" and cards["Reddy garu"]["fair_employer"] is True
    assert cards["Mehta madam"]["state"] == "below_minimum"
    assert cards["Mehta madam"]["haq_check"]["monthly_gap"] == 1500
    assert d["totals"] == {"homes": 3, "baaki": 12692.0, "recovered": 0.0, "hidden_baaki_estimate": 7500.0}
    assert client.get("/api/workers/999/dashboard").status_code == 404


def test_get_case_items_and_sources(client, demo):
    c = client.get(f"/api/cases/{demo['cases']['sharma']}").json()
    kinds = [(i["kind"], i["month"], i["amount"]) for i in c["items"]]
    assert ("unpaid_wage", "2026-10", 4000.0) in kinds
    assert ("illegal_deduction", "2026-07", 692.0) in kinds
    assert c["total_due"] == sum(i["amount"] for i in c["items"] if i["included_in_total"])
    assert any("G.O.Ms.No.6" in s for s in c["calc"]["sources"])
    assert c["employer_path"].startswith("/e/")
    assert c["readback"]["text"].startswith("<slow>")
    assert client.get("/api/cases/9999").status_code == 404


def test_mehta_shortfall_opt_in(client, demo):
    cid = demo["cases"]["mehta"]
    c = client.post(f"/api/cases/{cid}/confirm", json={"include_shortfall": True}).json()
    assert c["total_due"] == 7500 and c["status"] == "confirmed"
    assert all(i["is_estimate"] for i in c["items"] if i["kind"] == "min_wage_shortfall")


def test_meter_route(client):
    r = client.post("/api/cases/meter", json={"text": "teen mahine ki salary chaar hazaar", "lang": "hi-en"}).json()
    assert r["total"] == 12000 and r["safety"]["flagged"] is False
    edited = [c for c in r["chips"]]
    edited[0]["value"] = 2
    r2 = client.post("/api/cases/meter", json={"chips": edited}).json()
    assert r2["total"] == 8000


def test_extract_route(client):
    r = client.post("/api/cases/extract", json={
        "text": "Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina, roz do ghante",
        "lang": "hi-en", "worker_lang": "te-IN"}).json()
    assert r["facts"]["monthly_wage"] == 4000 and r["calc"]["contractual_due"] == 12000
    assert r["source"] == "parser"
    assert "నెలకు" in r["readback"]["text"]


def test_create_readback_confirm(client, demo, mock_gnani, short_ogg):
    body = {"worker_id": demo["workers"]["rafiq"], "lang": "hi-en",
            "transcript": "Gupta ji ne do mahine ki tankha nahi di, saat hazaar mahina, roz teen ghante khana banata hoon",
            "employer": {"name": "Gupta ji", "language": "te-IN"}}
    r = client.post("/api/cases", json=body)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["total_due"] == 14000 and c["work_type"] == "cooking" and c["category"] == "skilled"
    assert c["status"] == "draft" and c["employer"]["language"] == "te-IN"

    sent = []

    def tts(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, content=short_ogg, headers={"content-type": "audio/ogg"})

    mock_gnani.default["/api/v1/tts/inference"] = tts
    rb = client.post(f"/api/cases/{c['id']}/readback", json={}).json()
    assert rb["lang"] == "hi-en" and rb["audio_url"].startswith("/api/media/")
    assert sent[0]["language"] == "hi-en" and "<pauses>" in sent[0]["text"]
    audio = client.post(f"/api/cases/{c['id']}/readback?format=ogg", json={})
    assert audio.status_code == 200 and audio.content[:4] == b"OggS"
    assert len(sent) == 1  # second call came from the TTS cache

    c2 = client.post(f"/api/cases/{c['id']}/confirm", json={"facts": {"months_unpaid": 1}}).json()
    assert c2["readback_confirmed"] and c2["status"] == "confirmed" and c2["total_due"] == 7000


def test_readback_survives_tts_failure(client, demo, mock_gnani):
    mock_gnani.default["/api/v1/tts/inference"] = httpx.Response(500, json={"detail": "boom"})
    rb = client.post(f"/api/cases/{demo['cases']['sharma']}/readback", json={}).json()
    assert rb["text"] and rb["audio_url"] is None and rb["tts_error"]


def test_readback_text_only_no_gnani(client, demo):
    rb = client.post(f"/api/cases/{demo['cases']['sharma']}/readback", json={"audio": False}).json()
    assert "నెలకు నాలుగు వేల రూపాయలు" in rb["text"] and rb["audio_url"] is None


def test_readback_names_the_chosen_home(client, demo):
    """She says "Ammagaru" but picks Sharma ji: the read-back must name Sharma ji."""
    body = {"worker_id": demo["workers"]["lakshmi"], "lang": "te", "use_llm": False,
            "employer_id": demo["employers"]["sharma"],
            "transcript": "అమ్మగారు మూడు నెలలుగా నెలకు నాలుగు వేలు జీతం ఇవ్వలేదు."}
    c = client.post("/api/cases", json=body).json()
    rb = client.post(f"/api/cases/{c['id']}/readback", json={"audio": False}).json()
    assert "శర్మ గారు" in rb["text"] and "అమ్మ గారు" not in rb["text"]
    assert c["facts"]["employer_name"] == "Sharma ji"


def test_create_needs_wage(client, demo):
    r = client.post("/api/cases", json={"worker_id": demo["workers"]["lakshmi"], "transcript": "hello"})
    assert r.status_code == 422


def test_listen_uses_codemix_and_meters(client, mock_gnani, short_ogg):
    def stt(request):
        f = multipart_fields(request)
        assert f["language_code"] == "hi-IN,en-IN" and f["format"] == "codemix"
        return httpx.Response(200, json={"success": True, "detected_language_code": "hi-IN",
                                         "transcript": "Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina"})

    mock_gnani.push("/stt/v3", stt)
    r = client.post("/api/cases/listen", files={"audio": ("a.ogg", short_ogg, "audio/ogg")}, data={"lang": "hinglish"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 12000 and body["mode"] == "codemix"
    assert body["safety"]["flagged"] is False


def test_listen_flags_safety(client, mock_gnani, short_ogg):
    mock_gnani.push("/stt/v3", httpx.Response(200, json={"success": True, "transcript": "అమ్మగారు నన్ను కొట్టారు"}))
    body = client.post("/api/cases/listen", files={"audio": ("a.ogg", short_ogg, "audio/ogg")},
                       data={"lang": "te"}).json()
    assert body["safety"]["stop_wage_flow"] is True


def test_diary_chain_and_tamper(client, demo, short_ogg, mock_gnani):
    lid = demo["workers"]["lakshmi"]
    r = client.post("/api/diary", data={"worker_id": lid, "text": "Aaj Mehta madam ke ghar do ghante",
                                        "employer_id": demo["employers"]["mehta"]})
    assert r.status_code == 200 and r.json()["hours"] == 2
    mock_gnani.push("/stt/v3", httpx.Response(200, json={"success": True, "transcript": "ఈరోజు రెండు గంటలు"}))
    r2 = client.post("/api/diary", data={"worker_id": lid}, files={"audio": ("a.ogg", short_ogg, "audio/ogg")})
    e2 = r2.json()["entry"]
    assert e2["audio_sha256"] and e2["prev_hash"] == r.json()["entry"]["hash"] and e2["text"] == "ఈరోజు రెండు గంటలు"
    chain = client.get("/api/diary", params={"worker_id": lid}).json()
    assert chain["chain"]["valid"] and chain["chain"]["count"] == 8

    from app import db
    from app.models import DiaryEntry
    with db.session() as s:
        first = s.get(DiaryEntry, 1)
        first.text = "edited later"
        s.add(first)
        s.commit()
    assert client.get("/api/diary", params={"worker_id": lid}).json()["chain"] == {
        "valid": False, "broken_at": 1, "head": None, "count": 8}
    assert client.post("/api/diary", data={"worker_id": lid}).status_code == 400
