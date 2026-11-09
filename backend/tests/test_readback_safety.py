"""Read-back text (tags, amounts as words) and the safety switch."""
from __future__ import annotations

import pytest

from app import safety
from app.readback import build_readback, said_total

SHARMA = {"employer_name": "Sharma ji", "monthly_wage": 4000, "months_unpaid": 3, "hours_per_day": 2,
          "deductions": [{"amount": 1000, "reason": "sick", "days_absent": 2}]}


def test_hinglish_readback_words_and_tags():
    rb = build_readback(SHARMA, "hi-en")
    assert rb["text"].startswith("<slow> ")
    assert rb["text"].count("<pauses>") >= 4
    assert "teen mahine" in rb["text"] and "chaar hazaar rupaye har mahina" in rb["text"]
    assert "Kul terah hazaar rupaye" in rb["text"]
    assert rb["text"].endswith("Sahi hai?")
    assert not any(ch.isdigit() for ch in rb["text"])  # amounts are words, never digits
    assert "<" not in rb["plain"]


def test_telugu_readback():
    rb = build_readback(SHARMA, "te-IN")
    assert "మూడు నెలల జీతం" in rb["text"] and "నెలకు నాలుగు వేల రూపాయలు" in rb["text"]
    assert "మొత్తం పదమూడు వేల రూపాయలు" in rb["text"] and rb["text"].endswith("సరేనా?")


def test_legal_total_said_when_different():
    rb = build_readback(SHARMA, "hi-en", legal_total=12692)
    assert "Kanoon ke hisaab se maang sakte hain baarah hazaar chhah sau baanave rupaye" in rb["text"] or \
           "Kanoon ke hisaab se" in rb["text"]
    assert build_readback(SHARMA, "hi-en", legal_total=13000)["text"].count("Kanoon") == 0


def test_said_total():
    assert said_total(SHARMA) == 13000
    assert said_total({"stated_total": 5000}) == 5000
    assert said_total({"monthly_wage": 4000, "months_unpaid": 3, "advance_outstanding": 2000}) == 10000


@pytest.mark.parametrize("lang", ["hi-IN", "en-IN", "xx"])
def test_other_langs(lang):
    rb = build_readback(SHARMA, lang)
    assert rb["text"].startswith("<slow>")


# ---------------------------------------------------------------- safety
@pytest.mark.parametrize("text,cat", [
    ("Madam ne mujhe ghar mein band kar diya, bahar nahi jaane dete", "locked_in"),
    ("వాళ్ళు నన్ను లోపల పెట్టి తాళం వేసి వెళ్ళారు", "locked_in"),
    ("Sir ne mujhe maara aur salary bhi nahi di", "violence"),
    ("అమ్మగారు నన్ను కొట్టారు", "violence"),
    ("उन्होंने मुझे पीटा", "violence"),
    ("Mera aadhaar card madam ne rakh liya", "id_taken"),
    ("నా ఆధార్ కార్డు వాళ్ళు తీసుకున్నారు", "id_taken"),
    ("meri beti 12 saal ki ladki hai, woh bhi wahan kaam karti hai", "minor"),
    ("She is 13 years old and works there", "minor"),
    ("agent ne mujhe yahan bech diya", "trafficking"),
])
def test_safety_keywords(text, cat):
    r = safety.check_sync(text)
    assert r["flagged"] and r["stop_wage_flow"] and r["quick_exit"]
    assert cat in [c["key"] for c in r["categories"]]
    numbers = [h["number"] for h in r["helplines"]]
    assert "112" in numbers


@pytest.mark.parametrize("text", [
    "Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina",
    "మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు",
    "12 saal se kaam kar rahi hoon",  # working for 12 years is not a minor
    "Mehta madam do ghante ke liye dhai hazaar dete hain",
    "phone pe paise bhej do",
])
def test_no_false_alarm_on_wage_talk(text):
    assert safety.check_sync(text)["flagged"] is False


def test_helplines_listed():
    r = safety.check_sync("")
    nums = {h["number"] for h in r["helplines"]}
    assert {"181", "112", "1098", "1800 833 9020"} <= nums
    assert any(h["name"].startswith("NDWM") for h in r["helplines"])


async def test_llm_adds_but_never_clears(monkeypatch):
    from app import llm

    async def fake(system, user, schema, **kw):
        return kw["validate"]({k: (k == "minor") for k in safety.PATTERNS})

    monkeypatch.setattr(llm, "configured", lambda: True)
    monkeypatch.setattr(llm, "json_call", fake)
    r = await safety.check("Sir ne mujhe maara, and the girl working with me is young")
    keys = {c["key"]: c["via"] for c in r["categories"]}
    assert keys["violence"] == "keyword" and keys["minor"] == "llm"


async def test_llm_failure_keeps_keywords(monkeypatch):
    from app import llm

    async def boom(*a, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "configured", lambda: True)
    monkeypatch.setattr(llm, "json_call", boom)
    r = await safety.check("అమ్మగారు నన్ను కొట్టారు, జీతం కూడా ఇవ్వలేదు")
    assert r["flagged"]
