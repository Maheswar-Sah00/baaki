"""Tests for app.lang.dates.extract_dates. today = Sunday 8 Nov 2026 unless stated."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.lang.dates import extract_dates, today_ist  # noqa: E402

SUN = date(2026, 11, 8)  # Sunday
TUE = date(2026, 11, 10)  # Tuesday (the eval set's "today")

CASES = [
    # ---- bare day of month ---------------------------------------------------------
    ("15th ki 1,20,000 isthanu", SUN, ["2026-11-15"]),
    ("5th ki istha", SUN, ["2026-12-05"]),  # passed this month -> next month
    ("8th ko", SUN, ["2026-11-08"]),  # today
    ("31st tak", SUN, ["2026-11-30"]),  # clamped
    ("15 tareekh ko de dunga", SUN, ["2026-11-15"]),
    ("15 tarikh tak", SUN, ["2026-11-15"]),
    ("pandrah tarikh tak", SUN, ["2026-11-15"]),
    ("पंद्रह तारीख़ को डालता", SUN, ["2026-11-15"]),
    ("15 तारीख तक", SUN, ["2026-11-15"]),
    ("15వ తేదీ కల్లా", SUN, ["2026-11-15"]),
    ("15న ఇస్తాను", SUN, ["2026-11-15"]),
    ("పదిహేనో తారీఖు", SUN, ["2026-11-15"]),
    ("పదిహేనవ తేదీ", SUN, ["2026-11-15"]),
    ("ఇరవై ఐదో తేదీ", SUN, ["2026-11-25"]),
    ("ఒకటో తారీఖు కి", SUN, ["2026-12-01"]),
    ("Okato taareekhu ki kotha tenant", SUN, ["2026-12-01"]),
    ("Padiheno tedee lopu isthaanani", SUN, ["2026-11-15"]),
    ("Fifteenth ki laksha iravai velu", SUN, ["2026-11-15"]),
    ("fifth ki pakka istha", SUN, ["2026-12-05"]),
    ("twentieth lopala", SUN, ["2026-11-20"]),
    ("the first", SUN, ["2026-12-01"]),
    ("pehli tarikh ko", SUN, ["2026-12-01"]),
    # ---- this / next month + day -------------------------------------------------------
    ("ఈ నెల 15 కి ఇస్తాను", SUN, ["2026-11-15"]),
    ("ee nela 5 ki", SUN, ["2026-11-05"]),  # explicit "this month" even if passed
    ("is mahine ki 20 tarikh", SUN, ["2026-11-20"]),
    ("next month 5th", SUN, ["2026-12-05"]),
    ("5th next month", SUN, ["2026-12-05"]),
    ("15th of next month", SUN, ["2026-12-15"]),
    ("agle mahine ki 5 tarikh", SUN, ["2026-12-05"]),
    ("अगले महीने की 5 तारीख तक", SUN, ["2026-12-05"]),
    ("వచ్చే నెల 5న మిగతా 50 వేలు", SUN, ["2026-12-05"]),
    ("vachche nela 10 ki", SUN, ["2026-12-10"]),
    # ---- month names -----------------------------------------------------------------
    ("15 December", SUN, ["2026-12-15"]),
    ("December 15th, 2026", SUN, ["2026-12-15"]),
    ("15th of December", SUN, ["2026-12-15"]),
    ("December fifth ki muppai velu, December twentieth ki migatha", SUN, ["2026-12-05", "2026-12-20"]),
    ("15 డిసెంబర్", SUN, ["2026-12-15"]),
    ("15 दिसंबर तक", SUN, ["2026-12-15"]),
    ("5 January", SUN, ["2027-01-05"]),  # past this year -> next year
    ("10 November", SUN, ["2026-11-10"]),
    ("1 November", SUN, ["2027-11-01"]),
    ("15/12/2026", SUN, ["2026-12-15"]),
    ("15-12-2026", SUN, ["2026-12-15"]),
    ("31/02/2026", SUN, []),  # invalid date
    # ---- relative days ---------------------------------------------------------------
    ("aaj bhej dunga", SUN, ["2026-11-08"]),
    ("ఇవాళ పంపిస్తా", SUN, ["2026-11-08"]),
    ("Ippude NEFT chesaanu", SUN, ["2026-11-08"]),
    ("kal de dunga", SUN, ["2026-11-09"]),
    ("कल तक", SUN, ["2026-11-09"]),
    ("రేపు ఇస్తాను", SUN, ["2026-11-09"]),
    ("repu saayantram", SUN, ["2026-11-09"]),
    ("parson", SUN, ["2026-11-10"]),
    ("ఎల్లుండి bank ki velli", SUN, ["2026-11-10"]),
    ("day after tomorrow", SUN, ["2026-11-10"]),
    ("kal parson tak", SUN, ["2026-11-10"]),
    ("tomorrow", SUN, ["2026-11-09"]),
    # ---- weekdays -------------------------------------------------------------------
    ("Monday tak", SUN, ["2026-11-09"]),
    ("సోమవారం ఇస్తాను", SUN, ["2026-11-09"]),
    ("సోమవారానికి", SUN, ["2026-11-09"]),
    ("सोमवार को", SUN, ["2026-11-09"]),
    ("Sunday", SUN, ["2026-11-15"]),  # same weekday -> a week later
    ("vacche Monday vestha", TUE, ["2026-11-16"]),
    ("ee Friday", TUE, ["2026-11-13"]),
    ("Saturday return chestha", TUE, ["2026-11-14"]),
    ("shukravar ko", TUE, ["2026-11-13"]),
    # ---- durations --------------------------------------------------------------------
    ("1 week lo isthanu", SUN, ["2026-11-15"]),
    ("in a week", SUN, ["2026-11-15"]),
    ("ek hafte mein", SUN, ["2026-11-15"]),
    ("ఒక వారంలో", SUN, ["2026-11-15"]),
    ("10 days lo", SUN, ["2026-11-18"]),
    ("10 din mein", SUN, ["2026-11-18"]),
    ("10 दिन में", SUN, ["2026-11-18"]),
    ("10 రోజుల్లో", SUN, ["2026-11-18"]),
    ("Padi rojullo poora paisa", TUE, ["2026-11-20"]),
    ("Rendu rojullo pampistha", TUE, ["2026-11-12"]),
    ("Rendu vaaraallo settle chestha", TUE, ["2026-11-24"]),
    ("రెండు వారాల్లో", TUE, ["2026-11-24"]),
    ("after 10 days", SUN, ["2026-11-18"]),
    ("10 din ke baad", SUN, ["2026-11-18"]),
    ("2 months lo", SUN, ["2027-01-08"]),
    # ---- month end / whole months -----------------------------------------------------
    ("month end tak", SUN, ["2026-11-30"]),
    ("end of the month", SUN, ["2026-11-30"]),
    ("నెలాఖరు కల్లా", SUN, ["2026-11-30"]),
    ("nelaakharuki istha", SUN, ["2026-11-30"]),
    ("is mahine ke end tak", SUN, ["2026-11-30"]),
    ("agle mahine ke end tak", SUN, ["2026-12-31"]),
    ("agle mahine", SUN, ["2026-12-31"]),
    ("వచ్చే నెల", SUN, ["2026-12-31"]),
    ("ee nelalo istha", SUN, ["2026-11-30"]),
    ("in December", SUN, ["2026-12-31"]),
    # ---- Hindi past tense -------------------------------------------------------------
    ("Kal flat khaali kiya, aaj chaabi watchman ko de di.", TUE, ["2026-11-09", "2026-11-10"]),
    ("kal tak pachaas hazaar bhej denge", TUE, ["2026-11-11"]),
    ("Aakhri baar teen tareekh ko baat hui thi", TUE, ["2026-11-03"]),
    ("20 tarikh ko paisa aaya tha", TUE, ["2026-10-20"]),
    ("Owner ne kaha 15 tarikh ko denge", TUE, ["2026-11-15"]),
    # ---- not dates ------------------------------------------------------------------
    ("3rd floor", SUN, []),
    ("2nd cross road", SUN, []),
    ("first I will pay painting", SUN, []),
    ("second installment", SUN, []),
    ("do teen din mein", SUN, []),
    ("aaj kal bahut busy hoon", SUN, []),
    ("3 months rent", SUN, []),
    ("5 vela", SUN, []),
    ("Ee nela konchem kashtam andi", SUN, []),
    ("ఈ నెల కొంచెం కష్టం", SUN, []),
    ("Salary padagaane pampistha", SUN, []),
    ("1,20,000", SUN, []),
    ("flat 302", SUN, []),
    ("agle mahine 2 lakh denge", SUN, ["2026-12-31"]),  # "2 lakh" is money, not the 2nd
    ("padihenu rojule ichhaaru", SUN, []),  # a 15-day notice, not a deadline
    ("", SUN, []),
]


@pytest.mark.parametrize("text, today, expected", CASES)
def test_extract_dates(text, today, expected):
    assert [d["iso"] for d in extract_dates(text, today=today)] == expected


@pytest.mark.parametrize("text, today, expected", CASES)
def test_spans_index_original_text(text, today, expected):
    for d in extract_dates(text, today=today):
        assert text[d["start"]:d["end"]] == d["source_text"]
        assert d["precision"] in ("day", "week", "month")


@pytest.mark.parametrize("text, today, iso, rng", [
    ("ee vaaramlo vestha", TUE, "2026-11-15", ("2026-11-10", "2026-11-15")),
    ("ఈ వారంలో", TUE, "2026-11-15", ("2026-11-10", "2026-11-15")),
    ("Vacche vaaram pampistha", TUE, "2026-11-22", ("2026-11-16", "2026-11-22")),
    ("agle hafte", TUE, "2026-11-22", ("2026-11-16", "2026-11-22")),
    ("अगले हफ़्ते डालता", TUE, "2026-11-22", ("2026-11-16", "2026-11-22")),
    ("next week", SUN, "2026-11-15", ("2026-11-09", "2026-11-15")),
    ("agle mahine", SUN, "2026-12-31", ("2026-12-01", "2026-12-31")),
    ("is mahine mein", SUN, "2026-11-30", ("2026-11-08", "2026-11-30")),
])
def test_windows(text, today, iso, rng):
    (d,) = extract_dates(text, today=today)
    assert d["iso"] == iso
    assert (d["range_start"], d["range_end"]) == rng


def test_point_dates_have_no_range():
    (d,) = extract_dates("15th ki", today=SUN)
    assert d["range_start"] is None and d["range_end"] is None and d["precision"] == "day"


def test_year_rollover():
    dec = date(2026, 12, 20)
    assert [d["iso"] for d in extract_dates("15th ki", today=dec)] == ["2027-01-15"]
    assert [d["iso"] for d in extract_dates("agle mahine", today=dec)] == ["2027-01-31"]
    assert [d["iso"] for d in extract_dates("next week", today=dec)] == ["2026-12-27"]


def test_source_text_examples():
    ds = extract_dates("next month 5th ki 50 vela, agle hafte baaki", today=SUN)
    assert [d["source_text"] for d in ds] == ["next month 5th", "agle hafte"]


def test_default_today_is_ist():
    assert extract_dates("aaj")[0]["iso"] == today_ist().isoformat()
