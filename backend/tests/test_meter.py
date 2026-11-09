"""Baaki Meter: live tally on partial Telugu / Hindi / Hinglish / English text. No LLM, < 50 ms."""
from __future__ import annotations

import time

import pytest

from app.meter import meter, summarise


@pytest.mark.parametrize("text,lang,total,steps", [
    ("మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు", "te", 12000, [4000, 8000, 12000]),
    ("mūḍu nelalu, nelaku nālugu vēlu", None, 12000, [4000, 8000, 12000]),
    ("moodu nelalu, nelaku naalugu velu", "te", 12000, [4000, 8000, 12000]),
    ("teen mahine ki salary chaar hazaar", "hinglish", 12000, [4000, 8000, 12000]),
    ("मेरी तीन महीने की salary चार हज़ार", "hi", 12000, [4000, 8000, 12000]),
    ("3 months salary 4000 per month", "en", 12000, [4000, 8000, 12000]),
    ("₹4,000", None, 4000, [4000]),
    ("4 thousand", None, 4000, [4000]),
])
def test_required_phrases(text, lang, total, steps):
    r = meter(text, lang)
    assert r["total"] == total
    assert r["steps"] == steps
    for c in r["chips"]:
        assert text[c["span"][0]:c["span"][1]] == c["text"]


def test_sharma_sentence_ticks_up_to_13000():
    text = "Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina, aur do din bimar thi to ek hazaar kaat liya"
    r = meter(text, "hinglish")
    assert r["steps"] == [4000, 8000, 12000, 13000]
    assert r["total"] == 13000
    cut = [c for c in r["chips"] if c["kind"] == "cut"][0]
    assert cut["value"] == 1000 and cut["reason"] == "sick"
    assert r["cuts"] == [{"amount": 1000, "reason": "sick", "days_absent": 2}]
    assert r["months_unpaid"] == 3 and r["monthly_wage"] == 4000


def test_telugu_sick_cut():
    r = meter("మూడు నెలల జీతం, నెలకు 4000, రెండు రోజులు జ్వరం వచ్చిందని వెయ్యి రూపాయలు కట్ చేశారు", "te")
    assert r["total"] == 13000 and r["cuts"][0]["reason"] == "sick"


def test_partial_text_grows():
    words = "teen mahine ki salary chaar hazaar mahina".split()
    totals = [meter(" ".join(words[:i]), "hinglish")["total"] for i in range(1, len(words) + 1)]
    assert totals[-1] == 12000
    assert totals[:4] == [0, 0, 0, 0]  # "teen mahine ki salary": no rupee figure yet
    assert meter("teen mahine ki salary chaar ha", "hinglish")["total"] == 0  # a half word is not a number


def test_paid_and_negation():
    assert meter("రెడ్డి గారు నెలకు ఐదు వేలు ఇచ్చారు", "te")["total"] == 0
    r = meter("Rao garu ne do mahine ki tankha nahi di, saat hazaar mahina", "hinglish")
    assert r["total"] == 14000


def test_advance_subtracted_and_stated_total():
    assert meter("2000 advance liya tha, chaar hazaar salary, teen mahine", "hinglish")["total"] == 10000
    r = meter("teen mahine ka kul baara hazaar baaki hai", "hinglish")
    assert r["total"] == 12000 and r["stated_total"] == 12000


def test_hours_chip():
    r = meter("Mehta madam do ghante ke kaam ke liye dhai hazaar dete hain", "hinglish")
    assert r["hours_per_day"] == 2
    assert any(c["kind"] == "paid" and c["value"] == 2500 for c in r["chips"])


def test_empty():
    r = meter("", None)
    assert r["total"] == 0 and r["chips"] == []


def test_edited_chips_retotal():
    r = meter("teen mahine ki salary chaar hazaar, aur ek hazaar kaat liya", "hinglish")
    assert r["total"] == 13000
    chips = [c for c in r["chips"] if c["kind"] != "cut"]  # she taps the cut chip away
    assert summarise(chips)["total"] == 12000
    for c in chips:
        if c["kind"] == "months":
            c["value"] = 2  # she fixes "3 months" to 2
    assert summarise(chips)["total"] == 8000


def test_fast_enough_for_live_updates():
    text = ("Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina, aur do din bimar thi to ek hazaar "
            "kaat liya. Mehta madam do ghante ke liye dhai hazaar dete hain. మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు")
    meter(text, "hinglish")  # warm caches
    t0 = time.perf_counter()
    for _ in range(20):
        meter(text, "hinglish")
    assert (time.perf_counter() - t0) / 20 < 0.05
