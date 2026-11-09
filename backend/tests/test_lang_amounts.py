"""Tests for app.lang.amounts.extract_amounts on Prisma-style transcripts."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.lang.amounts import extract_amounts  # noqa: E402

# (text, lang_hint, [(amount, label_hint), ...])
CASES = [
    # ---- Telugu landlord, format=transcribe (digits) --------------------------------
    ("పెయింటింగ్ కి 55 వేలు, క్లీనింగ్ కి 10 వేలు కట్ చేస్తున్నా", "te",
     [(55000, "painting"), (10000, "cleaning")]),
    ("Painting ki 55 vela, cleaning ki 10 vela cut chestunna", "te", [(55000, "painting"), (10000, "cleaning")]),
    ("15th ki 1,20,000 isthanu", "te", [(120000, None)]),
    ("ఈ నెల 15 కి ₹1,20,000 ఇస్తాను", "te", [(120000, None)]),
    ("లిఫ్ట్ కి ₹2,000 కట్ చేశాను", "te", [(2000, "lift")]),
    ("అడ్వాన్స్ ₹1,50,000 లో ₹65,000 కట్", "te", [(150000, "advance"), (65000, "deduction")]),
    ("కరెంట్ బిల్ ₹3,456 పెండింగ్ ఉంది", "te", [(3456, "electricity")]),
    ("గోడలకి పెయింట్ 30 వేలు", "te", [(30000, "painting")]),
    ("పెయింటింగ్‌కి 25,000", "te", [(25000, "painting")]),
    ("మెయింటెనెన్స్ 4,000 రూపాయలు", "te", [(4000, "maintenance")]),
    # ---- Telugu codemix / verbatim (number words) -------------------------------------
    ("పెయింటింగ్ కి యాభై ఐదు వేలు, క్లీనింగ్ కి పది వేలు కట్ చేస్తున్నా", "te",
     [(55000, "painting"), (10000, "cleaning")]),
    ("పదిహేనో తారీఖు కి లక్ష ఇరవై వేలు ఇస్తాను", "te", [(120000, None)]),
    ("అద్దె నలభై వేలు", "te", [(40000, "rent")]),
    ("డిపాజిట్ లక్షన్నర", "te", [(150000, "deposit")]),
    ("గీజర్ రిపేర్ కి రెండు వేల నాలుగు వందల యాభై రూపాయలు", "te", [(2450, "geyser")]),
    ("ఫ్యాన్ రిపేర్ కి ముప్పై ఐదు వందలు", "te", [(3500, "fan")]),
    ("మొత్తం అర లక్ష", "te", [(50000, "total")]),
    ("తాళం చెవి కి వెయ్యిన్నర", "te", [(1500, "key")]),
    ("మిగతా రెండున్నర లక్షలు వచ్చే నెల 5న", "te", [(250000, "balance")]),
    ("ఒక్క రూపాయి కూడా ఇవ్వను", "te", []),
    ("రెండు మూడు వేలు అవుతుంది", "te", []),
    # ---- romanised Telugu ---------------------------------------------------------
    ("Painting ki yabhai aidu velu, cleaning ki padi velu cut chestunna", "te",
     [(55000, "painting"), (10000, "cleaning")]),
    ("Fifteenth ki laksha iravai velu isthanu", "te", [(120000, None)]),
    ("Geyser repair ki rendu vela naalugu vandala yaabhai ayindi", "te", [(2450, "geyser")]),
    ("Painting ki paavu laksha avuthundi", "te", [(25000, "painting")]),
    ("Lift usage ki rendu velu", "te", [(2000, "lift")]),
    ("Kitchen sink tap maarchaanu, enimidi vandalu. Bathroom geyser ki moodu velu.", "te",
     [(800, "tap"), (3000, "geyser")]),
    ("Current bill pending undi, moodu vela rendu vandalu.", "te", [(3200, "electricity")]),
    ("Three-o-two flat ki rent nalabhai velu", "te", [(40000, "rent")]),
    ("Pakka flat vaallu rendu lakshalu deposit ichhaaru", "te", [(200000, "deposit")]),
    ("Painter fifty five velu adugutunnaadu", "te", [(55000, None)]),
    ("painting ki forty K quote, twenty K cut chestha", "te", [(40000, "painting"), (20000, "deduction")]),
    # ---- Hindi (Devanagari) ---------------------------------------------------------
    ("पेंटिंग के लिए पचपन हज़ार और सफाई के दस हज़ार काट रहा हूँ", "hi", [(55000, "painting"), (10000, "cleaning")]),
    ("पेंटिंग का ₹55,000, सफाई का ₹10,000", "hi", [(55000, "painting"), (10000, "cleaning")]),
    ("डिपॉजिट डेढ़ लाख था", "hi", [(150000, "deposit")]),
    ("सवा लाख रुपये वापस करूँगा", "hi", [(125000, "refund")]),
    ("एक लाख बीस में से सत्तर हज़ार वापस करता", "hi", [(120000, None), (70000, "refund")]),
    ("लिफ्ट के 2,000 रुपये", "hi", [(2000, "lift")]),
    ("किराया 25 हज़ार है", "hi", [(25000, "rent")]),
    # ---- Hinglish ---------------------------------------------------------------------
    ("Owner ne bola painting ke pachpan hazaar aur cleaning ke das hazaar kaatenge", "hinglish",
     [(55000, "painting"), (10000, "cleaning")]),
    ("Lift ke bhi do hazaar bol rahe hain", "hinglish", [(2000, "lift")]),
    ("Rent chalees hazaar hai, aur deposit ek lakh bees hazaar diya tha, teen mahine ka", "hinglish",
     [(40000, "rent"), (120000, "deposit")]),
    ("pandrah tareekh tak poora paisa de denge, ek lakh bees", "hinglish", [(120000, None)]),
    ("Dedh lakh nahi, deposit ek lakh bees tha", "hinglish", [(150000, None), (120000, "deposit")]),
    ("geyser dhai hazaar mein theek karwa denge", "hinglish", [(2500, "geyser")]),
    ("sade teen lakh deposit diya tha", "hinglish", [(350000, "deposit")]),
    ("paune do lakh wapas milenge", "hinglish", [(175000, "refund")]),
    ("deposit 1.5 lakh tha, 82k kaat liye", "hinglish", [(150000, "deposit"), (82000, "deduction")]),
    ("Owner ₹65,000 kaat rahe hain", "hinglish", [(65000, "deduction")]),
    ("do teen hazaar ka kharcha hai", "hinglish", []),
    ("bees pachees hazaar lagenge", "hinglish", []),
    ("2 se 3 lakh", "hinglish", []),
    ("ek rupaya bhi nahi dunga", "hinglish", []),
    # ---- English --------------------------------------------------------------------
    ("Rs 2,000 for lift usage", "en", [(2000, "lift")]),
    ("Rs. 82,000 was deducted from my Rs 1.5 lakh deposit", "en", [(82000, "deduction"), (150000, "deposit")]),
    ("55k for painting, 10k for cleaning", "en", [(55000, "painting"), (10000, "cleaning")]),
    ("55,000 painting, 10,000 cleaning", "en", [(55000, "painting"), (10000, "cleaning")]),
    ("Painting: ₹55,000. Cleaning: ₹10,000.", "en", [(55000, "painting"), (10000, "cleaning")]),
    ("Deposit one lakh twenty thousand, sixty five thousand cut", "en", [(120000, "deposit"), (65000, "deduction")]),
    ("Deep cleaning twelve thousand five hundred, pest control two thousand", "en",
     [(12500, "cleaning"), (2000, "pest_control")]),
    ("I will return two and a half lakh", "en", [(250000, "refund")]),
    ("₹2000/- lift charges", "en", [(2000, "lift")]),
    ("INR 65,000.00 total", "en", [(65000, "total")]),
    ("₹3.50 for the bulb", "en", [(4, "light")]),
    # ---- false-positive traps ----------------------------------------------------------
    ("flat 302 ki painting 5000", "hinglish", [(5000, "painting")]),
    ("Flat No. 302, Block B", "en", []),
    ("H.No. 8-2-293/82, Road No 12, Banjara Hills", "en", []),
    ("Call me at 98765 43210", "en", []),
    ("+91 98765 43210 pe call karo, 5000 bhejo", "hinglish", [(5000, None)]),
    ("98XXX XXX10 is his number", "en", []),
    ("pin 500081", "en", []),
    ("2025 lo flat teesukunna", "te", []),
    ("I moved in December 2025", "en", []),
    ("lift ki 2000", "te", [(2000, "lift")]),
    ("15th ki isthanu", "te", []),
    ("15వ తేదీ కల్లా ఇస్తా", "te", []),
    ("meeting at 10:30, pay by 5 pm", "en", []),
    ("2 rooms, 3 months rent advance", "hinglish", []),
    ("2 BHK flat, rent 25000 per month", "en", [(25000, "rent")]),
    ("1200 sqft flat", "en", []),
    ("200 units current bill 1,600", "en", [(1600, "electricity")]),
    ("Bijli meter ki reading atharah hazaar chaar sau baavan hai", "hinglish", []),
    ("main door ki do chaabiyan mili, bedroom ki do, aur fan ke teen remote", "hinglish", []),
    ("jaali do jagah se phati hui hai", "hinglish", []),
    ("10 days lo isthanu", "te", []),
    ("Tiles rendu pagilaayi", "te", []),
    # ---- Baaki: wage vocabulary (jeetham, salary, tankha, kooli, baaki, advance, cut) ---------------
    ("మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు", "te", [(4000, "wage")]),
    ("mūḍu nelalu, nelaku nālugu vēlu", "te", [(4000, None)]),
    ("teen mahine ki salary chaar hazaar", "hinglish", [(4000, "wage")]),
    ("teen mahine se salary nahi di, chaar hazaar mahina, aur do din bimar thi to ek hazaar kaat liya",
     "hinglish", [(4000, "wage"), (1000, "deduction")]),
    ("मेरी तीन महीने की salary चार हज़ार", "hi", [(4000, "wage")]),
    ("tankha 4000", "hinglish", [(4000, "wage")]),
    ("కూలి 4000", "te", [(4000, "wage")]),
    ("jeetham naalugu velu", "te", [(4000, "wage")]),
    ("పన్నెండు వేల రూపాయలు బాకీ", "te", [(12000, "balance")]),
    ("advance 2000 liya tha", "hinglish", [(2000, "advance")]),
    ("katauti ek hazaar", "hinglish", [(1000, "deduction")]),
    ("నెలకు 4000 కట్టాను", "te", [(4000, None)]),
    ("4 thousand", "en", [(4000, None)]),
    ("₹4,000", None, [(4000, None)]),
    ("teen mahine", "hinglish", []),
    ("3 months 2 days", "en", []),
    ("", None, []),
]


@pytest.mark.parametrize("text, lang, expected", CASES)
def test_extract_amounts(text, lang, expected):
    got = extract_amounts(text, lang)
    assert [(a["amount_inr"], a["label_hint"]) for a in got] == expected


@pytest.mark.parametrize("text, lang, expected", CASES)
def test_spans_index_original_text(text, lang, expected):
    for a in extract_amounts(text, lang):
        assert text[a["start"]:a["end"]] == a["source_text"]
        assert a["source_text"].strip() == a["source_text"]
        assert isinstance(a["amount_inr"], int)


@pytest.mark.parametrize("text, sources", [
    ("₹2000/- lift ke liye", ["₹2000/-"]),
    ("Rs. 2,000 for lift usage", ["Rs. 2,000"]),
    ("పెయింటింగ్ కి 55 వేల రూపాయలు", ["55 వేల రూపాయలు"]),
    ("Painting ki 55 vela, cleaning ki 10 vela", ["55 vela", "10 vela"]),
    ("डिपॉजिट डेढ़ लाख था", ["डेढ़ लाख"]),
    ("ఈ నెల 15 కి ₹1,20,000 ఇస్తాను", ["₹1,20,000"]),
])
def test_source_text(text, sources):
    assert [a["source_text"] for a in extract_amounts(text)] == sources


def test_native_digits():
    # Devanagari and Telugu digits arrive when itn_native_numerals is on (v2.5)
    assert [a["amount_inr"] for a in extract_amounts("₹५,०००")] == [5000]
    assert [a["amount_inr"] for a in extract_amounts("౫౫ వేలు")] == [55000]


def test_lang_hint_optional_and_unknown_is_ignored():
    text = "Painting ki 55 vela"
    assert extract_amounts(text) == extract_amounts(text, "te") == extract_amounts(text, "kn-IN")
