"""V08 Fair or Not?: card content, wording rules, numbers tied to wages.py, and the API. Offline; nothing stored."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import quiz_data as qd
from app import wages
from app.check_core import SOURCE_URL as GO6_URL
from app.main import app
from app.routes import quiz as quiz_route

FORBIDDEN = re.compile(r"\b(fine|fined|fines|penalty|penalties|jail|guarantee|guaranteed|"
                       r"compensation|10x|10 times|3x|police|fir)\b", re.I)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- content
def test_five_cards_with_section_source_disclaimer():
    assert len(qd.CARDS) == 5
    assert len(set(qd.CARD_IDS)) == 5
    for c in qd.CARDS:
        assert c["answer"] in qd.CHOICES
        assert c["section"].strip() and c["source"].strip()
        assert c["source_url"].startswith("https://")
        assert set(c["text"]) == set(qd.LANGS)
        for lang in qd.LANGS:
            r = qd.reveal(c["id"], "fair", lang)
            assert r["section"] and r["source"] and r["source_url"]
            assert r["disclaimer"] == qd.DISCLAIMER[lang]
            assert r["disclaimer_en"] == qd.DISCLAIMER_EN
            assert r["myth"] and r["rule"] and r["detail"]
            assert "{" not in r["myth"] + r["rule"] + r["detail"], "unfilled placeholder"


def test_disclaimer_wording():
    assert qd.DISCLAIMER_EN == ("General information from the Code on Wages, 2019 and G.O.Ms.No.6 (Telangana), "
                                "not legal advice.")


def test_required_rules_are_covered():
    sections = " ".join(c["section"] for c in qd.CARDS)
    for s in ("s.17", "s.20(2)", "s.18(3)", "s.60", "G.O.Ms.No.6"):
        assert s in sections, s


def test_no_forbidden_words_anywhere():
    for s in qd.all_strings():
        m = FORBIDDEN.search(s)
        assert m is None, f"forbidden word {m.group(0)!r} in: {s[:120]}"


def test_code_says_framing_and_no_multipliers():
    en_rules = [qd.card_text(cid, "en")["rule"] for cid in ("late", "payday", "agreed")]
    assert all(r.startswith("The Code says") for r in en_rules)
    for s in qd.all_strings():
        assert "×" not in s and "times the" not in s.lower()


def test_answers_mix_fair_and_not_fair():
    answers = {c["answer"] for c in qd.CARDS}
    assert answers == {"fair", "not_fair"}


# --------------------------------------------------------------------------- numbers tied to wages.py
def test_numbers_match_wages():
    assert qd.MONTHLY == wages.GO6_MONTHLY["unskilled"] == 16000
    assert qd.PER_DAY == wages.per_day_rate("unskilled") == 615.5
    assert qd.HALF_MONTH == 8000
    assert qd.PART_TIME_2H == wages.minimum_wage("2026-11", "unskilled", 2, 6).amount == 4000
    assert qd.LATE_CUT == pytest.approx(19.23, abs=0.01)
    assert qd.HALF_DAY == pytest.approx(307.75)


def test_rupee_figures_in_text():
    t = qd.card_text("minimum", "en")
    assert "₹16,000" in t["rule"] and "₹615.50" in t["detail"] and "₹4,000" in t["detail"]
    assert "estimate" in t["detail"]
    assert "₹8,000" in qd.card_text("advance", "en")["detail"]
    late = qd.card_text("late", "en")["detail"]
    assert "₹19.23" in late and "₹307.75" in late
    for lang in qd.LANGS:
        assert "₹16,000" in qd.card_text("minimum", lang)["rule"]
        assert "₹16,000" in qd.card_text("agreed", lang)["detail"]


def test_sources_match_wages_strings():
    by = {c["id"]: c for c in qd.CARDS}
    assert by["payday"]["source"].startswith(wages.SRC_S17_1)
    assert wages.SRC_S17_2 in by["payday"]["source"]
    assert by["late"]["source"] == wages.SRC_S20
    assert by["advance"]["source"].startswith(wages.SRC_S18)
    assert "G.O.Ms.No.6" in by["minimum"]["source"] and by["minimum"]["source_url"] == GO6_URL
    assert by["minimum"]["is_estimate"] is True
    assert "null and void" in by["agreed"]["source"]


def test_score_logic():
    right = {c["id"]: c["answer"] for c in qd.CARDS}
    s = qd.score(right, "en")
    assert (s["score"], s["total"], s["headline"]) == (5, 5, "5/5")
    one_wrong = dict(right, late="fair")
    s = qd.score(one_wrong, "hi-en")
    assert s["score"] == 4 and s["headline"] == "4/5" and "4/5" in s["share_text"]
    assert qd.score({}, "te")["score"] == 0


def test_lang_normalisation():
    assert qd.norm_lang("hinglish") == "hi-en"
    assert qd.norm_lang("te-IN") == "te"
    assert qd.norm_lang("xx") == "en"


# --------------------------------------------------------------------------- API
def test_get_deck_hides_answers(client):
    r = client.get("/api/quiz", params={"lang": "hi-en"})
    assert r.status_code == 200
    d = r.json()
    assert d["lang"] == "hi-en" and d["total"] == 5 and len(d["cards"]) == 5
    assert [c["id"] for c in d["choices"]] == ["fair", "not_fair"]
    for c in d["cards"]:
        assert "answer" not in c and "rule" not in c
        assert c["section"] and c["disclaimer"]


def test_answer_endpoint(client):
    r = client.post("/api/quiz/answer", json={"card_id": "late", "choice": "not_fair", "lang": "en"})
    assert r.status_code == 200
    d = r.json()
    assert d["correct"] is True and d["answer"] == "not_fair" and d["answer_label"] == "Not fair"
    assert d["section"] == "Code on Wages, 2019, s.20(2)"
    assert d["disclaimer"] == qd.DISCLAIMER_EN
    assert "audio_url" in d
    r = client.post("/api/quiz/answer", json={"card_id": "payday", "choice": "not_fair", "lang": "te"})
    assert r.json()["correct"] is False
    assert client.post("/api/quiz/answer", json={"card_id": "nope", "choice": "fair"}).status_code == 404
    assert client.post("/api/quiz/answer", json={"card_id": "late", "choice": "maybe"}).status_code == 422


def test_score_endpoint(client):
    answers = {c["id"]: c["answer"] for c in qd.CARDS}
    answers["minimum"] = "fair"
    r = client.post("/api/quiz/score", json={"answers": answers, "lang": "en"})
    assert r.status_code == 200
    d = r.json()
    assert d["score"] == 4 and d["headline"] == "4/5" and d["check_url"] == "/check"
    assert len(d["results"]) == 5 and all(x["source"] for x in d["results"])
    assert client.post("/api/quiz/score", json={"answers": {"x": "fair"}}).status_code == 422


def test_audio_is_cache_only(client, monkeypatch, tmp_path):
    monkeypatch.setattr(quiz_route.tts_cache, "lookup", lambda key, fmt="ogg": None)
    assert quiz_route.narration_url("late") is None
    assert client.get("/api/quiz/audio/" + "a" * 64 + ".ogg").status_code == 404
    clip = tmp_path / "x.ogg"
    clip.write_bytes(b"OggS-fake")
    monkeypatch.setattr(quiz_route.tts_cache, "lookup", lambda key, fmt="ogg": clip)
    url = quiz_route.narration_url("late")
    assert url and url.startswith("/api/quiz/audio/") and url.endswith(".ogg")
    r = client.get(url)
    assert r.status_code == 200 and r.content == b"OggS-fake"


def test_nothing_stored(client, monkeypatch):
    called = []
    monkeypatch.setattr(quiz_route.tts_cache, "synth", lambda *a, **k: called.append(a))
    client.get("/api/quiz")
    client.post("/api/quiz/score", json={"answers": {"late": "fair"}})
    assert called == []


def test_narration_text_speaks_rupees_not_sign():
    for cid in qd.CARD_IDS:
        t = qd.narration_text(cid, "hi-en")
        assert "₹" not in t and FORBIDDEN.search(t) is None
        assert t.split(".")[0] in ("Fair", "Not fair")
    assert "16,000 रुपये" in qd.narration_text("minimum", "hi-en")
