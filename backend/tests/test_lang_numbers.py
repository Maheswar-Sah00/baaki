"""Tests for app.lang.numbers: formatting, read-back words, parsing, round trips."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.lang import numbers as N  # noqa: E402
from app.lang.numbers import (  # noqa: E402
    MAX_INR,
    en_words_to_number,
    format_inr,
    hi_words_to_number,
    hinglish_words_to_number,
    inr_to_words,
    number_to_words,
    te_roman_words_to_number,
    te_words_to_number,
    words_to_number,
)

LANGS = ["te", "hi", "hinglish", "en"]


# --------------------------------------------------------------------------- format_inr
@pytest.mark.parametrize("amount, expected", [
    (0, "₹0"), (5, "₹5"), (99, "₹99"), (100, "₹100"), (999, "₹999"), (1000, "₹1,000"),
    (2000, "₹2,000"), (9999, "₹9,999"), (10000, "₹10,000"), (55000, "₹55,000"), (99999, "₹99,999"),
    (100000, "₹1,00,000"), (120000, "₹1,20,000"), (1234567, "₹12,34,567"), (10000000, "₹1,00,00,000"),
    (999999999, "₹99,99,99,999"), (-65000, "-₹65,000"),
])
def test_format_inr(amount, expected):
    assert format_inr(amount) == expected


def test_format_inr_rejects_non_int():
    with pytest.raises(TypeError):
        format_inr(12.5)
    with pytest.raises(TypeError):
        format_inr(True)


# --------------------------------------------------------------------------- inr_to_words
@pytest.mark.parametrize("amount, lang, expected", [
    # Telugu: attributive వేల / లక్షల before రూపాయలు
    (65000, "te", "అరవై ఐదు వేల రూపాయలు"),
    (120000, "te", "ఒక లక్ష ఇరవై వేల రూపాయలు"),
    (55000, "te", "యాభై ఐదు వేల రూపాయలు"),
    (10000, "te", "పది వేల రూపాయలు"),
    (2000, "te", "రెండు వేల రూపాయలు"),
    (1000, "te", "వెయ్యి రూపాయలు"),
    (1500, "te", "వెయ్యి ఐదు వందల రూపాయలు"),
    (100, "te", "వంద రూపాయలు"),
    (150, "te", "నూట యాభై రూపాయలు"),
    (250, "te", "రెండు వందల యాభై రూపాయలు"),
    (101, "te", "నూట ఒక్క రూపాయలు"),
    (21000, "te", "ఇరవై ఒక్క వేల రూపాయలు"),
    (1, "te", "ఒక రూపాయి"),
    (0, "te", "సున్నా రూపాయలు"),
    (100000, "te", "ఒక లక్ష రూపాయలు"),
    (250000, "te", "రెండు లక్షల యాభై వేల రూపాయలు"),
    (1000000, "te", "పది లక్షల రూపాయలు"),
    (10000000, "te", "ఒక కోటి రూపాయలు"),
    (2450, "te", "రెండు వేల నాలుగు వందల యాభై రూపాయలు"),
    (100020, "te", "ఒక లక్ష మరియు ఇరవై రూపాయలు"),
    # Hindi
    (120000, "hi", "एक लाख बीस हज़ार रुपये"),
    (65000, "hi", "पैंसठ हज़ार रुपये"),
    (1, "hi", "एक रुपया"),
    (0, "hi", "शून्य रुपये"),
    (150, "hi", "एक सौ पचास रुपये"),
    (99, "hi", "निन्यानवे रुपये"),
    (2500, "hi", "दो हज़ार पाँच सौ रुपये"),
    (10000000, "hi", "एक करोड़ रुपये"),
    (100020, "hi", "एक लाख और बीस रुपये"),
    # Hinglish
    (120000, "hinglish", "ek lakh bees hazaar rupaye"),
    (65000, "hinglish", "painsath hazaar rupaye"),
    (1, "hinglish", "ek rupaya"),
    (2500, "hinglish", "do hazaar paanch sau rupaye"),
    (55000, "hinglish", "pachpan hazaar rupaye"),
    # English
    (120000, "en", "one lakh twenty thousand rupees"),
    (1, "en", "one rupee"),
    (0, "en", "zero rupees"),
    (250, "en", "two hundred fifty rupees"),
    (10000000, "en", "one crore rupees"),
    (999999999, "en", "ninety nine crore ninety nine lakh ninety nine thousand nine hundred ninety nine rupees"),
])
def test_inr_to_words(amount, lang, expected):
    assert inr_to_words(amount, lang) == expected


@pytest.mark.parametrize("n, lang, expected", [
    (55000, "te", "యాభై ఐదు వేలు"),
    (200, "te", "రెండు వందలు"),
    (21, "te", "ఇరవై ఒకటి"),
    (120000, "hi", "एक लाख बीस हज़ार"),
    (120000, "en", "one lakh twenty thousand"),
])
def test_number_to_words(n, lang, expected):
    assert number_to_words(n, lang) == expected


def test_inr_to_words_accepts_locale_codes():
    assert inr_to_words(65000, "te-IN") == inr_to_words(65000, "te")
    assert inr_to_words(65000, "hi-IN") == inr_to_words(65000, "hi")


@pytest.mark.parametrize("bad", [-1, MAX_INR + 1])
def test_inr_to_words_range(bad):
    with pytest.raises(ValueError):
        inr_to_words(bad, "te")


def test_inr_to_words_bad_input():
    with pytest.raises(TypeError):
        inr_to_words(12.5, "en")
    with pytest.raises(ValueError):
        inr_to_words(100, "kn")


# --------------------------------------------------------------------------- Hindi 1-99 table
@pytest.mark.parametrize("n", range(100))
def test_hindi_table_devanagari(n):
    assert hi_words_to_number(N.HI_1_99[n]) == n


@pytest.mark.parametrize("n", range(100))
def test_hindi_table_hinglish(n):
    assert hinglish_words_to_number(N.HINGLISH_1_99[n]) == n


@pytest.mark.parametrize("n", range(100))
def test_telugu_table(n):
    assert te_words_to_number(number_to_words(n, "te")) == n


# --------------------------------------------------------------------------- words -> number
@pytest.mark.parametrize("text, expected", [
    # Telugu script (codemix / verbatim style)
    ("యాభై ఐదు వేలు", 55000),
    ("పది వేలు", 10000),
    ("లక్ష ఇరవై వేలు", 120000),
    ("లక్షా ఇరవై వేల", 120000),
    ("ఒక లక్ష ఇరవై వేల రూపాయలు", 120000),
    ("లక్షా ఇరవై", 120000),  # lakh-short
    ("రెండు లక్షలు", 200000),
    ("రెండున్నర లక్షలు", 250000),
    ("లక్షన్నర", 150000),
    ("ఒకటిన్నర లక్ష", 150000),
    ("అర లక్ష", 50000),
    ("పావు లక్ష", 25000),
    ("ముప్పావు లక్ష", 75000),
    ("వెయ్యిన్నర", 1500),
    ("తొమ్మిదిన్నర వేలు", 9500),
    ("ఐదొందలు", 500),
    ("రెండొందల యాభై", 250),
    ("నూట యాభై", 150),
    ("పదిహేను వందలు", 1500),
    ("ముప్పై ఐదు వందలు", 3500),
    ("ఇరవయ్యైదు వేలు", 25000),
    ("పదివేలు", 10000),
    ("55 వేలు", 55000),
    ("55 వేలకి", 55000),
    ("రెండు వేల నాలుగు వందల యాభై", 2450),
    ("ఒక కోటి", 10000000),
    ("పెయింటింగ్ కి 55 వేలు", 55000),
])
def test_te_words(text, expected):
    assert te_words_to_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("yabhai aidu velu", 55000),
    ("yaabhai velu", 50000),
    ("55 vela", 55000),
    ("padi vela", 10000),
    ("rendu lakshalu", 200000),
    ("oka laksha iravai vela", 120000),
    ("laksha iravai", 120000),
    ("laksha aidu velu", 105000),
    ("lakshannara", 150000),
    ("rendunnara lakshalu", 250000),
    ("tommidinnara velu", 9500),
    ("veyyinnara", 1500),
    ("paavu laksha", 25000),
    ("muppaavu laksha", 75000),
    ("ara laksha", 50000),
    ("muppai aidu vandalu", 3500),
    ("rendu vela naalugu vandala yaabhai", 2450),
    ("aaru vela moodu vandalu", 6300),
    ("enimidi vandalu", 800),
    ("laksha roopaayalu", 100000),
])
def test_te_roman_words(text, expected):
    assert te_roman_words_to_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("डेढ़ लाख", 150000),
    ("ढाई लाख", 250000),
    ("सवा लाख", 125000),
    ("साढ़े तीन लाख", 350000),
    ("पौने दो लाख", 175000),
    ("पचपन हज़ार", 55000),
    ("पचपन हजार", 55000),
    ("एक लाख बीस हज़ार", 120000),
    ("एक लाख बीस", 120000),
    ("दो सौ पचास", 250),
    ("पाँच करोड़", 50000000),
    ("दस हज़ार रुपये", 10000),
])
def test_hi_words(text, expected):
    assert hi_words_to_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("ek lakh bees hazaar", 120000),
    ("ek lakh bees", 120000),
    ("ek lakh aur bees", 100020),
    ("sava lakh", 125000),
    ("sava do lakh", 225000),
    ("dedh lakh", 150000),
    ("dhai lakh", 250000),
    ("dhai hazaar", 2500),
    ("sade teen lakh", 350000),
    ("paune do lakh", 175000),
    ("pachpan hazaar", 55000),
    ("pachpan hajar", 55000),
    ("do sau pachaas", 250),
    ("pandra hazaar", 15000),
    ("chalees hazaar", 40000),
    ("sattar hazaar", 70000),
    ("do hazaar", 2000),
    ("das hazaar", 10000),
])
def test_hinglish_words(text, expected):
    assert hinglish_words_to_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("one lakh twenty thousand", 120000),
    ("two and a half lakh", 250000),
    ("one and a half lakh", 150000),
    ("half lakh", 50000),
    ("half a lakh", 50000),
    ("a lakh", 100000),
    ("twenty-five thousand", 25000),
    ("two hundred and fifty", 250),
    ("twelve thousand five hundred", 12500),
    ("fifty five thousand", 55000),
    ("fifty five velu", 55000),
    ("forty K", 40000),
    ("1 lakh 20 thousand", 120000),
    ("2.5 lakh", 250000),
    ("1.2L", 120000),
    ("55k", 55000),
    ("55 K", 55000),
    ("1.2 cr", 12000000),
    ("₹1,20,000", 120000),
    ("Rs. 2,000", 2000),
    ("₹2000/-", 2000),
    ("1 million", 1000000),
])
def test_en_words(text, expected):
    assert en_words_to_number(text) == expected


@pytest.mark.parametrize("text", [
    "do teen hazaar",  # a few thousand
    "bees pachees hazaar",  # 20-25 thousand
    "2-3 lakh",
    "రెండు మూడు వేలు",
    "dedh",  # 1.5, not whole rupees
    "hello",
    "",
    "vela",  # plural multiplier alone = "thousands", vague
    "lakhs",
])
def test_words_to_number_rejects(text):
    assert words_to_number(text) is None


# --------------------------------------------------------------------------- round trips
EDGES = [0, 1, 2, 9, 10, 11, 19, 20, 21, 99, 100, 101, 110, 150, 999, 1000, 1001, 1500, 9999, 10000, 21000,
         99999, 100000, 100001, 100020, 101000, 110000, 120000, 999999, 1000000, 1000020, 10000000, 10000020,
         10100000, 99999999, 999999999]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("n", EDGES)
def test_round_trip_edges(n, lang):
    assert words_to_number(inr_to_words(n, lang), lang) == n


@pytest.mark.parametrize("lang", LANGS)
def test_round_trip_sampled(lang):
    rng = random.Random(20261108)
    sample = rng.sample(range(0, 1_000_001), 2000) + [rng.randrange(MAX_INR + 1) for _ in range(300)]
    bad = [n for n in sample if words_to_number(inr_to_words(n, lang), lang) != n]
    assert bad == []


@pytest.mark.parametrize("lang", LANGS)
def test_round_trip_without_currency(lang):
    rng = random.Random(7)
    for n in [1] + rng.sample(range(2, 1_000_001), 500):
        assert words_to_number(number_to_words(n, lang), lang) == n, (n, number_to_words(n, lang))


# --------------------------------------------------------------------------- lexicon sanity
def test_latin_lexicons_agree():
    """A spelling shared by two Latin lexicons must mean the same number."""
    names = list(N.LATIN_LEXICONS)
    conflicts = []
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            la, lb = N.LATIN_LEXICONS[names[a]], N.LATIN_LEXICONS[names[b]]
            for k in set(la) & set(lb):
                va = [(x.kind, x.value) for x in la[k]]
                vb = [(x.kind, x.value) for x in lb[k]]
                if va != vb:
                    conflicts.append((k, names[a], va, names[b], vb))
    assert conflicts == []


def test_telugu_words_list_is_stable():
    """The words a native speaker reviews (see module constants)."""
    assert N.TE_UNITS[15] == "పదిహేను"
    assert N.TE_TENS[50] == "యాభై"
    assert (N.TE_THOUSANDS, N.TE_THOUSANDS_OBL) == ("వేలు", "వేల")
