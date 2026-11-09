"""app.wages: the deterministic calculator. Legal numbers from G.O.Ms.No.6 / G.O.Ms.No.60 and the Code on Wages."""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app import wages

TODAY = dt.date(2026, 11, 9)


# ---------------------------------------------------------------- rates
@pytest.mark.parametrize("cat,monthly,daily", [
    ("unskilled", 16000, 615.50), ("semi_skilled", 17000, 654.00), ("skilled", 18500, 711.50),
    ("highly_skilled", 20000, 769.00),
])
def test_go6_rates_and_per_day(cat, monthly, daily):
    assert wages.GO6_MONTHLY[cat] == monthly
    assert wages.per_day_rate(cat) == daily  # monthly / 26, nearest 50 paise


def test_full_time_is_the_notified_rate_not_an_estimate():
    mw = wages.minimum_wage("2026-07", "unskilled", 8, 6)
    assert mw.amount == 16000 and mw.is_estimate is False
    assert "G.O.Ms.No.6" in mw.source and "30.05.2026" in mw.source and "VDA" in mw.source


@pytest.mark.parametrize("cat,hours,expected", [
    ("unskilled", 1, 2000.0), ("unskilled", 2, 4000.0), ("skilled", 3, 6937.5), ("skilled", 1, 2312.5),
    ("semi_skilled", 1, 2125.0),
])
def test_part_time_estimate(cat, hours, expected):
    mw = wages.minimum_wage("2026-08", cat, hours, 6)
    assert mw.amount == expected
    assert mw.is_estimate is True
    assert "estimate" in mw.source


def test_fewer_days_a_week_pro_rated():
    mw = wages.minimum_wage("2026-08", "unskilled", 2, 3)  # 13 days a month
    assert mw.amount == 2000.0 and mw.is_estimate


def test_hours_above_8_capped_no_overtime_added():
    assert wages.minimum_wage("2026-08", "unskilled", 10, 6).amount == 16000


def test_before_june_uses_go60():
    mw = wages.minimum_wage("2026-05", "unskilled", 1)
    assert mw.amount == 1348 and mw.notification == "G.O.Ms.No.60" and not mw.is_estimate
    assert wages.minimum_wage("2026-04", "unskilled", 8).amount == 10785
    assert wages.minimum_wage("2026-02", "unskilled", 8).amount == 10493  # Oct 2025 - Mar 2026 sheet
    est = wages.minimum_wage("2026-05", "unskilled", 2)
    assert est.amount == 2696 and est.is_estimate
    # June 2026 onwards never uses G.O.60
    assert wages.minimum_wage("2026-06", "unskilled", 1).notification == "G.O.Ms.No.6"


def test_unknown_period_not_guessed():
    mw = wages.minimum_wage("2024-01", "unskilled", 8)
    assert mw.amount is None


# ---------------------------------------------------------------- the law agent's case (Rs 44,000)
def test_law_agent_case_44000():
    """Full-time maid, paid Rs 9,000 Jun-Sep 2026, dismissed 31 Oct without October pay -> Rs 44,000."""
    r = wages.calculate(monthly_wage=9000, category="unskilled", hours_per_day=8, days_per_week=6,
                        paid_months={"2026-06": 9000, "2026-07": 9000, "2026-08": 9000, "2026-09": 9000},
                        unpaid_months=["2026-10"], dismissed_on="2026-10-31", include_shortfall=True, today=TODAY)
    assert r["unpaid_wages"] == 9000
    assert r["contractual_due"] == 9000
    jun_sep = sum(i["amount"] for i in r["items"] if i["kind"] == "min_wage_shortfall" and i["month"] < "2026-10")
    assert jun_sep == 28000  # (16,000 - 9,000) x 4
    assert r["min_wage_shortfall"] == 35000  # + October's 7,000
    assert r["total"] == r["total_with_shortfall"] == 44000
    # October: 9,000 agreed + 7,000 shortfall = 16,000, due within 2 working days of dismissal (s.17(2))
    oct_items = [i for i in r["items"] if i["month"] == "2026-10"]
    assert sum(i["amount"] for i in oct_items) == 16000
    assert r["due"]["settlement_due"] == "2026-11-03"  # Sat 31 Oct -> (Sun skipped) Mon 2, Tue 3 Nov
    assert all(i["due_date"] == "2026-11-03" for i in oct_items)
    assert any("s.17(2)" in s for s in r["sources"])
    # full-time rate is the notified figure, not an estimate
    assert r["shortfall_is_estimate"] is False


def test_44000_without_shortfall_opt_in_is_only_contractual():
    r = wages.calculate(monthly_wage=9000, paid_months={"2026-06": 9000, "2026-07": 9000, "2026-08": 9000,
                                                        "2026-09": 9000},
                        unpaid_months=["2026-10"], dismissed_on="2026-10-31", today=TODAY)
    assert r["total"] == 9000 and r["total_with_shortfall"] == 44000
    assert all(not i["included_in_total"] for i in r["items"] if i["kind"] == "min_wage_shortfall")


# ---------------------------------------------------------------- never extras
def test_no_multiplier_penalty_or_extras_anywhere():
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, months_unpaid=3, last_month="2026-10",
                        deductions=[{"amount": 1000, "reason": "fine", "month": "2026-07"}],
                        dismissed_on="2026-10-31", include_shortfall=True, today=TODAY)
    blob = json.dumps(r).lower()
    for bad in ("multiplier", "notice pay", "gratuity", "interest", "10x", "ten times", "cash payment is illegal"):
        if bad in ("notice pay", "gratuity", "interest"):
            assert all(bad not in i["label"].lower() for i in r["items"])
        else:
            assert bad not in blob
    assert {i["kind"] for i in r["items"]} <= {"unpaid_wage", "illegal_deduction", "min_wage_shortfall"}
    included = sum(i["amount"] for i in r["items"] if i["included_in_total"])
    assert r["total"] == pytest.approx(included)
    assert any("may award" in s for s in r["sources"])


# ---------------------------------------------------------------- deductions
def test_sick_cut_only_excess_over_proportional_is_reclaimable():
    d = wages.check_deduction({"amount": 1000, "reason": "sick", "days_absent": 2}, 4000)
    assert d["lawful_max"] == 308.0  # 4000 x 2 / 26 = 307.69 -> rounded UP to 50 paise (never overstate her claim)
    assert d["reclaimable"] == 692.0
    assert d["flag"] == "excess_absence_cut"


def test_proportional_sick_cut_is_lawful():
    d = wages.check_deduction({"amount": 300, "reason": "sick", "days_absent": 2}, 4000)
    assert d["reclaimable"] == 0 and d["flag"] == "proportional_ok"


def test_family_away_cut_fully_reclaimable():
    d = wages.check_deduction({"amount": 1000, "reason": "employer_away", "days_absent": 2}, 4000)
    assert d["reclaimable"] == 1000 and d["flag"] == "not_her_absence"


@pytest.mark.parametrize("reason,flag", [("fine", "household_fine"), ("other", "no_authorised_basis"),
                                         ("breakage", "breakage_needs_proof")])
def test_unauthorised_cuts(reason, flag):
    d = wages.check_deduction({"amount": 500, "reason": reason}, 4000)
    assert d["reclaimable"] == 500 and d["flag"] == flag


def test_absence_without_days_is_not_claimed():
    d = wages.check_deduction({"amount": 500, "reason": "sick"}, 4000)
    assert d["reclaimable"] == 0 and d["flag"] == "absence_days_unknown"


def test_fifty_percent_cap():
    # 20 days "absent" would allow 20/26 of the wage, but s.18(3) caps all cuts at 50% of the month
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, paid_months={"2026-08": 1000},
                        deductions=[{"amount": 3000, "reason": "sick", "days_absent": 20, "month": "2026-08"}],
                        today=TODAY)
    d = r["deductions"][0]
    assert d["reclaimable"] >= 1000  # whatever is above 2,000 (50%) comes back
    assert "over_50_percent" in r["flags"]


def test_advance_recovery_lawful_and_subtracted():
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, months_unpaid=3, last_month="2026-10",
                        advance_outstanding=2000, today=TODAY)
    assert r["contractual_due"] == 10000


# ---------------------------------------------------------------- due dates
def test_due_by_7th_of_next_month():
    assert wages.normal_due_date("2026-08") == dt.date(2026, 9, 7)
    assert wages.normal_due_date("2026-12") == dt.date(2027, 1, 7)
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, unpaid_months=["2026-10"], today=TODAY)
    item = r["items"][0]
    assert item["due_date"] == "2026-11-07" and item["overdue"] and item["days_overdue"] == 2
    assert "s.17(1)(iv)" in item["source"]


def test_working_days_skip_sunday():
    assert wages.add_working_days(dt.date(2026, 10, 31), 2) == dt.date(2026, 11, 3)  # Saturday
    assert wages.add_working_days(dt.date(2026, 11, 4), 2) == dt.date(2026, 11, 6)  # Wednesday


def test_months_unpaid_counts_back_from_last_complete_month():
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, months_unpaid=3, today=TODAY)
    assert r["inputs"]["unpaid_months"] == ["2026-08", "2026-09", "2026-10"]


# ---------------------------------------------------------------- demo stories
def test_sharma_story():
    r = wages.calculate(monthly_wage=4000, hours_per_day=2, unpaid_months=["2026-08", "2026-09", "2026-10"],
                        paid_months={"2026-06": 4000, "2026-07": 4000},
                        deductions=[{"amount": 1000, "reason": "sick", "days_absent": 2, "month": "2026-07"}],
                        today=TODAY)
    assert r["unpaid_wages"] == 12000
    assert r["reclaimable_deductions"] == 692
    assert r["contractual_due"] == 12692
    assert r["min_wage_shortfall"] == 0  # Rs 4,000 for 2 hours is exactly the estimated minimum
    r2 = wages.calculate(monthly_wage=4000, hours_per_day=2, unpaid_months=["2026-08", "2026-09", "2026-10"],
                         deductions=[{"amount": 1000, "reason": "employer_away", "days_absent": 2, "month": "2026-07"}],
                         today=TODAY)
    assert r2["contractual_due"] == 13000


def test_mehta_hidden_baaki():
    r = wages.calculate(monthly_wage=2500, hours_per_day=2, paid_months={f"2026-{m:02d}": 2500 for m in range(6, 11)},
                        today=TODAY)
    assert r["contractual_due"] == 0
    assert r["haq_check"]["minimum_for_hours"] == 4000 and r["haq_check"]["monthly_gap"] == 1500
    assert r["haq_check"]["is_estimate"] is True
    assert r["min_wage_shortfall"] == 7500 and r["shortfall_is_estimate"] is True
    assert all(i["is_estimate"] for i in r["items"] if i["kind"] == "min_wage_shortfall")


def test_no_hours_no_haq_check():
    r = wages.calculate(monthly_wage=2500, hours_per_day=None, months_unpaid=2, today=TODAY)
    assert r["haq_check"]["needs_hours"] is True and r["min_wage_shortfall"] == 0


def test_cook_category():
    assert wages.category_for("cooking") == "skilled"
    r = wages.calculate(monthly_wage=7000, work_type="cooking", category=None, hours_per_day=3,
                        unpaid_months=["2026-09", "2026-10"], today=TODAY)
    assert r["contractual_due"] == 14000 and r["min_wage_shortfall"] == 0
    assert r["haq_check"]["minimum_for_hours"] == 6937.5


def test_round50():
    assert wages.round50(615.38) == 615.5
    assert wages.round50(711.54) == 711.5
    assert wages.round50(653.85) == 654.0
    assert wages.round50(0.25) == 0.5
