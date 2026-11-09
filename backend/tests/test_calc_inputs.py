"""One calculation input (GAP_AUDIT R2): meter, read-back and case agree; paid money subtracts; months, fractions
and hours are never guessed. Offline, parser only (no LLM)."""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from app import calc_inputs, raise_core, wages
from app.extract import extract_facts
from app.inbox_logic import extract_past_payments, extract_promises
from app.lang import extract_amounts
from app.messages import CaseCtx
from app.meter import meter
from app.models import CaseItem
from app.readback import build_readback
from app.routes.cases import calc_from_facts

TODAY = dt.date(2026, 11, 10)


async def _three(text: str, lang: str = "hinglish"):
    m = meter(text, lang)
    ex = await extract_facts(text, lang, use_llm=False)
    calc = calc_from_facts(ex["facts"], today=TODAY)
    rb = build_readback(ex["facts"], "hi-en", legal_total=calc["total"], today=TODAY)
    return m["total"], calc["total"], rb["said_total"], calc, rb


# --------------------------------------------------------------------------- meter == case == read-back
@pytest.mark.parametrize("text,lang,total", [
    ("salary 5000 har mahina, 4000 rupaye har mahina dete hain, teen mahine se", "hinglish", 3000),
    ("salary 4000 har mahina, 3 mahine nahi mili, 2000 rupaye diye", "hinglish", 10000),
    ("2000 diya hai", "hinglish", 0),
    ("teen mahine ki salary chaar hazaar", "hinglish", 12000),
    ("2000 advance liya tha, chaar hazaar salary, teen mahine", "hinglish", 10000),
    ("dhai mahine se salary nahi mili, 4000 har mahina", "hinglish", 10000),
    ("ఆగస్టు, సెప్టెంబర్, అక్టోబర్ జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు", "te", 12000),
    ("మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు", "te", 12000),
    ("రెడ్డి గారు నెలకు ఐదు వేలు ఇచ్చారు", "te", 0),
    ("Mehta madam do ghante ke kaam ke liye dhai hazaar dete hain", "hinglish", 0),
])
async def test_meter_case_and_readback_agree(text, lang, total):
    m_total, case_total, said, _, _ = await _three(text, lang)
    assert m_total == case_total == said == total


async def test_paid_per_month_is_the_gap_not_the_wage():
    _, total, _, calc, rb = await _three("salary 5000 har mahina, 4000 rupaye har mahina dete hain, teen mahine se")
    assert total == 3000  # was Rs 15,000 (GAP_AUDIT #1)
    gaps = [i for i in calc["items"] if i["kind"] == "unpaid_wage"]
    assert [i["amount"] for i in gaps] == [1000, 1000, 1000] and all(i["label"].startswith("Part unpaid") for i in gaps)
    assert "sirf chaar hazaar rupaye milte hain" in rb["text"]


async def test_paid_lump_is_a_visible_negative_line():
    _, total, _, calc, rb = await _three("salary 4000 har mahina, 3 mahine nahi mili, 2000 rupaye diye")
    received = [i for i in calc["items"] if i["kind"] == "paid_received"]
    assert total == 10000 and received[0]["amount"] == -2000 and received[0]["included_in_total"]
    assert calc["received_from_employer"] == 2000
    assert "Do hazaar rupaye mil chuke hain" in rb["text"]


async def test_sick_cut_meter_says_what_she_said_case_says_the_calculation():
    text = "Sharma ji ne teen mahine se salary nahi di, chaar hazaar mahina, aur do din bimar thi to ek hazaar kaat liya"
    m_total, case_total, said, _, rb = await _three(text)
    assert m_total == said == 13000 and case_total == 12692
    assert "Baaki ka hisaab, Code on Wages section bees: baarah hazaar chhah sau baanve rupaye" in rb["text"]


def test_seeded_sharma_still_12692():
    facts = {"monthly_wage": 4000, "hours_per_day": 2, "unpaid_months": ["2026-08", "2026-09", "2026-10"],
             "paid_months": {"2026-06": 4000, "2026-07": 4000},
             "deductions": [{"amount": 1000, "reason": "sick", "days_absent": 2, "month": "2026-07"}]}
    calc = calc_from_facts(facts, today=dt.date(2026, 11, 9))
    assert calc["total"] == 12692 and calc["said"]["total"] == 13000


# --------------------------------------------------------------------------- withheld money is the ceiling
def test_part_paid_month_with_a_cut_never_claims_more_than_withheld():
    # October: paid Rs 3,000 of Rs 4,000 because Rs 1,000 was cut for 2 sick days. Only Rs 1,000 was withheld.
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, paid_months={"2026-10": 3000},
                        deductions=[{"amount": 1000, "reason": "sick", "days_absent": 2, "month": "2026-10"}],
                        today=TODAY)
    assert r["contractual_due"] == 692 <= 1000
    # the same story without the month on the cut: it is placed in October and says so
    c = calc_from_facts({"monthly_wage": 4000, "hours_per_day": 2, "paid_months": {"2026-10": 3000},
                         "deductions": [{"amount": 1000, "reason": "sick", "days_absent": 2}]}, today=TODAY)
    assert c["total"] == 692 and "cut_month_assumed" in c["flags"]
    assert "Oct 2026" in c["notes"][0]


def test_fifty_percent_cap_for_a_cut_without_a_month():
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, months_unpaid=1, last_month="2026-10",
                        deductions=[{"amount": 3000, "reason": "sick", "days_absent": 20}], today=TODAY)
    d = r["deductions"][0]
    assert "over_50_percent" in r["flags"] and d["reclaimable"] >= 1000
    assert "Month not said" in d["note"] and "one month's wage" in d["note"]


# --------------------------------------------------------------------------- months
def test_month_resolver_current_month_is_this_year():
    assert calc_inputs.resolve_month(11, TODAY) == "2026-11"
    assert calc_inputs.resolve_month(10, TODAY) == "2026-10"
    assert calc_inputs.resolve_month(12, TODAY) == "2025-12"


async def test_current_month_is_not_yet_due_and_named():
    _, total, _, calc, rb = await _three("November ki salary nahi mili, 4000 har mahina")
    item = [i for i in calc["items"] if i["kind"] == "unpaid_wage"][0]
    assert item["month"] == "2026-11" and item["not_yet_due"] and "not yet due" in item["label"]
    assert "not_yet_due" in calc["flags"] and total == 4000
    assert rb["text"].count("November") >= 1 and "saat December tak deni hai" in rb["text"]


def test_readback_names_the_months():
    rb = build_readback({"monthly_wage": 4000, "months_unpaid": 3}, "hi-en", today=TODAY)
    assert "August, September aur October, teen mahine ki salary nahi mili" in rb["text"]
    te = build_readback({"monthly_wage": 4000, "unpaid_month_numbers": [9, 10]}, "te-IN", today=TODAY)["text"]
    assert "సెప్టెంబర్, అక్టోబర్" in te


@pytest.mark.parametrize("months,total", [(2.5, 10000), (0.5, 2000), (1.5, 6000)])
def test_fractional_months_kept(months, total):
    c = calc_from_facts({"monthly_wage": 4000, "months_unpaid": months}, today=TODAY)
    assert c["total"] == total > 0
    assert any(i.get("fraction") for i in c["items"])


def test_unclear_month_count_is_asked_not_guessed():
    m = meter("do teen mahine se salary nahi mili, 4000 har mahina", "hinglish")
    assert m["months_unclear"] and m["total"] == 0
    rb = build_readback({"monthly_wage": 4000, "months_unclear": True}, "hi-en", today=TODAY)
    assert "Kitne mahine" in rb["text"] and rb["asks"] == ["months"]


# --------------------------------------------------------------------------- hours
def _case(facts, hours_col=8.0):
    return SimpleNamespace(facts=lambda: facts, hours_per_day=hours_col, work_type="housekeeping",
                           days_per_week=6.0, monthly_wage=2500.0)


def test_case_hours_reads_facts_not_the_db_default():
    assert calc_inputs.case_hours(_case({})) is None
    assert calc_inputs.case_hours(_case({"hours_per_day": None, "hours_known": False})) is None
    assert calc_inputs.case_hours(_case({"hours_per_day": 2}, hours_col=2)) == 2


def test_raise_estimate_needs_hours_instead_of_8():
    est = raise_core.estimate_for_case(_case({}), TODAY)
    assert est["needs_hours"] and est["legal_estimate"] is None and est["gap_monthly"] == 0
    assert "hours not said" in est["how"].lower()
    est2 = raise_core.estimate_for_case(_case({"hours_per_day": 2}, 2), TODAY)
    assert not est2["needs_hours"] and est2["legal_estimate"] == 4000


def test_letter_hours_text():
    from app.letter import _hours_text
    assert _hours_text(_case({})) == calc_inputs.HOURS_NOT_SAID
    assert _hours_text(_case({"hours_per_day": 2}, 2)) == "2 hours a day"


async def test_extract_records_whether_hours_were_said():
    f = (await extract_facts("teen mahine ki salary chaar hazaar", "hinglish", use_llm=False))["facts"]
    assert f["hours_known"] is False and f["hours_per_day"] is None
    f = (await extract_facts("teen mahine ki salary chaar hazaar, roz do ghante", "hinglish", use_llm=False))["facts"]
    assert f["hours_known"] is True and f["hours_per_day"] == 2


# --------------------------------------------------------------------------- small ones (GAP_AUDIT #29)
def test_paise_kept():
    assert extract_amounts("₹615.50 baaki hai", "en")[0]["amount_inr"] == 615.5
    assert wages.fmt_inr(615.5) == "₹615.50" and wages.fmt_inr(12692) == "₹12,692" and wages.fmt_inr(-2000) == "-₹2,000"


def test_item_labels_use_rupee_sign():
    c = calc_from_facts({"monthly_wage": 5000, "paid_months": {"2026-10": 4000}}, today=TODAY)
    assert all("Rs " not in i["label"] for i in c["items"])
    assert "₹4,000 of ₹5,000 paid" in c["items"][0]["label"]


def test_past_tense_payment_is_not_a_promise():
    said_on = dt.date(2026, 11, 10)
    assert extract_promises("5 November ko diya tha 2000", "hi-en", said_on) == []
    past = extract_past_payments("5 November ko diya tha 2000", "hi-en", said_on)
    assert past == [{"amount": 2000.0, "paid_on": "2026-11-05", "quote": "5 November ko diya tha 2000",
                     "kind": "past_payment"}]
    # a real promise still is one
    assert extract_promises("15 November ko 2000 de dungi", "hi-en", said_on)[0]["due_date"] == "2026-11-15"


def _item(kind, month, label, amount):
    return CaseItem(case_id=1, kind=kind, month=month, label=label, amount=amount, included_in_total=True)


def test_part_paid_month_is_said_as_part_unpaid():
    case = SimpleNamespace(total_due=5000, amount_paid=0, monthly_wage=4000)
    ctx = CaseCtx(case, None, None, [  # type: ignore[arg-type]
        _item("unpaid_wage", "2026-09", "Unpaid wages: Sep 2026", 4000),
        _item("unpaid_wage", "2026-10", "Part unpaid: Oct 2026 (₹3,000 of ₹4,000 paid)", 1000)])
    assert ctx.unpaid_months() == ["2026-09"] and ctx.part_unpaid_months() == ["2026-10"]
