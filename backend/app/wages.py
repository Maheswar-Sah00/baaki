"""Deterministic wage calculator (no LLM). Every figure here can be shown with its source.

Rules (docs/research/02_law_procedure_telangana.md section 8, docs/BUILD_BRIEF.md):
* Minimum wage from 1 Jun 2026: Telangana G.O.Ms.No.6 dated 30.05.2026, Table 1, Zone-I (Hyderabad), basic only
  (VDA not notified after June 2026, so it is left out and we say so; that can only understate her claim).
  Per day = monthly / 26, rounded to the nearest 50 paise (G.O. para 5(1), 5(6)).
* Part-time: monthly / 26 / 8 x hours per day x days worked. Always is_estimate=True (the G.O. lists no part-time rate).
* Before 1 Jun 2026: G.O.Ms.No.60 (2011 schedule for domestic workers), only for months before June 2026.
* Code on Wages s.17: monthly wages due before the 7th of the next month is over; on dismissal, within 2 working days.
* s.18 to s.20: only authorised deductions; absence cuts in proportion to days absent; total <= 50% of the month.
* NEVER a multiplier, penalty, notice pay, bonus, gratuity or interest. NEVER "cash pay is illegal".
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Iterable

# --------------------------------------------------------------------------- notified rates
CATEGORIES = ("unskilled", "semi_skilled", "skilled", "highly_skilled")
GO6_MONTHLY = {"unskilled": 16000.0, "semi_skilled": 17000.0, "skilled": 18500.0, "highly_skilled": 20000.0}
GO6_START = dt.date(2026, 6, 1)
WORK_TYPE_CATEGORY = {
    "housekeeping": "unskilled", "maid": "unskilled", "cleaning": "unskilled", "washing": "unskilled",
    "vessels": "unskilled", "sweeping": "unskilled", "childcare": "unskilled", "ayah": "unskilled",
    "eldercare": "unskilled", "caretaker": "unskilled", "gardener": "unskilled", "watchman": "unskilled",
    "assistant_cook": "semi_skilled", "creche_ayah": "semi_skilled",
    "cooking": "skilled", "cook": "skilled",
    "other": "unskilled",
}
CATEGORY_LABEL = {"unskilled": "Unskilled", "semi_skilled": "Semi-Skilled", "skilled": "Skilled",
                  "highly_skilled": "Highly Skilled"}

# G.O.Ms.No.60 (domestic workers, 2011 schedule), department sheet: total (basic + VDA) per month by hours a day.
GO60_TABLES = [
    (dt.date(2026, 4, 1), dt.date(2026, 9, 30), {0.5: 676.0, 1.0: 1348.0, 1.5: 2023.0, 8.0: 10785.0}),
    (dt.date(2025, 10, 1), dt.date(2026, 3, 31), {0.5: 657.0, 1.0: 1312.0, 1.5: 1968.0, 8.0: 10493.0}),
]

SRC_GO6 = ("Telangana G.O.Ms.No.6, LET&F (Lab-I) Dept, dated 30.05.2026, in force 01.06.2026, Table 1, "
           "Zone-I (Hyderabad), {cat}: ₹{monthly} per month basic; per day = monthly / 26 (para 5(1)). "
           "VDA not yet notified, so basic only. Subject to pending court cases.")
SRC_GO60 = ("Telangana G.O.Ms.No.60, LET&F (Lab.II) Dept, dated 01.11.2011 (domestic workers), rates for "
            "{period}: ₹{amount} per month for {hours} a day (basic + VDA). Used only for months before June 2026.")
SRC_ESTIMATE = ("Part-time figure is Baaki's estimate (monthly / 26 / 8 x hours per day x days worked); "
                "the order does not list part-time rates.")
SRC_S17_1 = "Code on Wages, 2019, s.17(1)(iv): monthly wages are due before the expiry of the 7th day of the next month."
SRC_S17_2 = "Code on Wages, 2019, s.17(2): on removal or dismissal, wages are due within two working days."
SRC_S18 = ("Code on Wages, 2019, s.18(1): no deductions except those the Code authorises; s.18(3): total deductions "
           "in a wage period cannot exceed 50% of the wages.")
SRC_S20 = "Code on Wages, 2019, s.20(2): an absence deduction must be in proportion to the days absent."
SRC_S21 = ("Code on Wages, 2019, s.18(2)(c) and s.21: a damage cut is lawful only for goods entrusted to her, lost by "
           "her own neglect, at actual value, after she is heard.")
SRC_S19 = "Code on Wages, 2019, s.19: fines need prior Government approval and a displayed notice; a household fine is almost never lawful."
SRC_S23 = "Code on Wages, 2019, s.18(2)(f) and s.23: recovery of an advance is an authorised deduction."
NOTE_NO_EXTRAS = ("No compensation multiple, penalty, notice pay, bonus, gratuity or interest is added. "
                  "The claims authority may award compensation at its discretion (s.45(2)); Baaki never adds it.")
DISCLAIMER = ("Baaki is an information tool, not a lawyer and not a government office. It does not give legal advice. "
              "Check with the Telangana Labour Department or free legal aid (DLSA, NALSA 15100) before acting.")


# --------------------------------------------------------------------------- helpers
def round50(x: float) -> float:
    """Nearest 50 paise (G.O.Ms.No.6 para 5(6)); halves round up."""
    return math.floor(x * 2 + 0.5) / 2


def ceil50(x: float) -> float:
    return math.ceil(round(x * 2, 6)) / 2


def money(x: float) -> float:
    return round(float(x) + 0.0, 2)


def parse_month(m: str | dt.date) -> dt.date:
    if isinstance(m, dt.date):
        return m.replace(day=1)
    y, mo = str(m)[:7].split("-")
    return dt.date(int(y), int(mo), 1)


def month_key(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def month_label(m: str) -> str:
    return parse_month(m).strftime("%b %Y")


def previous_months(last: str | dt.date, count: int) -> list[str]:
    """`count` months ending at `last` (inclusive), oldest first."""
    end = parse_month(last)
    return [month_key(add_months(end, -i)) for i in range(count - 1, -1, -1)]


def last_complete_month(today: dt.date) -> str:
    return month_key(add_months(today.replace(day=1), -1))


def add_working_days(d: dt.date, n: int) -> dt.date:
    """Skip Sundays only (public holidays are not modelled; this can only make the date earlier-or-equal)."""
    out = d
    while n > 0:
        out += dt.timedelta(days=1)
        if out.weekday() != 6:
            n -= 1
    return out


def normal_due_date(month: str) -> dt.date:
    """s.17(1)(iv): before the expiry of the 7th day of the next month -> by the 7th."""
    return add_months(parse_month(month), 1).replace(day=7)


def category_for(work_type: str | None, category: str | None = None) -> str:
    if category in CATEGORIES:
        return category  # type: ignore[return-value]
    return WORK_TYPE_CATEGORY.get((work_type or "").lower(), "unskilled")


def days_per_month(days_per_week: float) -> float:
    """26 working days for a 6-day week (G.O. para 5(1)); pro-rated for fewer days, capped at 26."""
    return min(26.0, 26.0 * max(0.0, float(days_per_week)) / 6.0)


def fmt_inr(x: float) -> str:
    """The one rupee formatter for item labels and sources: ₹13,000, ₹615.50, -₹2,000 (Indian grouping)."""
    a = round(float(x), 2)
    sign, a = ("-", -a) if a < 0 else ("", a)
    whole = int(a)
    paise = int(round((a - whole) * 100))
    if paise == 100:
        whole, paise = whole + 1, 0
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{sign}₹{s}" + (f".{paise:02d}" if paise else "")


def default_today() -> dt.date:
    """Today in IST (app.clock when it exists, which honours BAAKI_TODAY), never the server's local date."""
    try:
        from . import clock  # type: ignore[attr-defined]
        return clock.today()
    except (ImportError, AttributeError):
        from .lang.dates import today_ist
        return today_ist()


# --------------------------------------------------------------------------- minimum wage
@dataclass
class MinWage:
    month: str
    amount: float | None
    is_estimate: bool
    source: str
    basis: str
    notification: str  # "G.O.Ms.No.6" | "G.O.Ms.No.60" | ""

    def as_dict(self) -> dict[str, Any]:
        return {"month": self.month, "amount": self.amount, "is_estimate": self.is_estimate,
                "source": self.source, "basis": self.basis, "notification": self.notification}


def per_day_rate(category: str) -> float:
    return round50(GO6_MONTHLY[category] / 26)


def minimum_wage(month: str, category: str = "unskilled", hours_per_day: float = 8,
                 days_per_week: float = 6) -> MinWage:
    """Minimum wage for one month of work at these hours. Hours above 8 are capped at 8 (overtime not computed)."""
    m = parse_month(month)
    category = category if category in CATEGORIES else "unskilled"
    hours = max(0.0, min(8.0, float(hours_per_day)))
    dpm = days_per_month(days_per_week)
    full_time = hours >= 8 and dpm >= 26
    if m >= GO6_START:
        monthly = GO6_MONTHLY[category]
        src = SRC_GO6.format(cat=CATEGORY_LABEL[category], monthly=f"{int(monthly):,}")
        if full_time:
            return MinWage(month_key(m), monthly, False, src, f"{CATEGORY_LABEL[category]} full-time monthly rate",
                           "G.O.Ms.No.6")
        amount = round50(monthly / 26 / 8 * hours * dpm)
        basis = (f"{fmt_inr(monthly)} / 26 / 8 x {hours:g} h x {dpm:g} days")
        return MinWage(month_key(m), amount, True, src + " " + SRC_ESTIMATE, basis, "G.O.Ms.No.6")
    for start, end, table in GO60_TABLES:
        if start <= m <= end:
            period = f"{start.strftime('%d.%m.%Y')} to {end.strftime('%d.%m.%Y')}"
            if hours in table:
                amount, est, hrs = table[hours], False, hours
                basis = f"G.O.Ms.No.60 row for {hours:g} h a day"
            else:
                amount, est, hrs = min(table[1.0] * hours, table[8.0]), True, 1.0
                basis = f"G.O.Ms.No.60 1-hour rate {fmt_inr(table[1.0])} x {hours:g} h (estimate)"
            if dpm < 26:
                amount, est = amount * dpm / 26, True
                basis += f" x {dpm:g}/26 days"
            src = SRC_GO60.format(period=period, amount=f"{int(table[hrs]):,}",
                                  hours=f"{hrs:g} hour" + ("" if hrs == 1 else "s"))
            if est:
                src += " Pro-rated figure is Baaki's estimate."
            return MinWage(month_key(m), round50(amount), est, src, basis, "G.O.Ms.No.60")
    return MinWage(month_key(m), None, True, "No verified minimum-wage figure for this month in Baaki's tables.",
                   "not computed", "")


# --------------------------------------------------------------------------- deductions
ABSENCE_REASONS = {"absence", "sick", "leave", "absent", "illness"}
EMPLOYER_AWAY_REASONS = {"employer_away", "holiday", "family_away", "employer_holiday"}
BREAKAGE_REASONS = {"breakage", "damage", "loss"}
FINE_REASONS = {"fine", "late", "penalty"}
ADVANCE_REASONS = {"advance", "advance_recovery", "loan"}


def check_deduction(d: dict[str, Any], monthly_wage: float, days_per_week: float = 6) -> dict[str, Any]:
    """One cut -> lawful part, reclaimable part, flag and source. Amounts never grow beyond what was cut."""
    amount = money(d.get("amount") or 0)
    reason = (d.get("reason") or "other").lower()
    days = d.get("days_absent")
    out: dict[str, Any] = {"amount": amount, "reason": reason, "month": d.get("month"),
                           "days_absent": days, "lawful_max": 0.0, "reclaimable": amount}
    if reason in ABSENCE_REASONS:
        working_days = days_per_month(days_per_week) or 26.0
        if days:
            # conservative: the lawful part is rounded UP to 50 paise, so her claim is never overstated
            lawful = min(amount, ceil50(monthly_wage * float(days) / working_days))
            out.update(lawful_max=lawful, reclaimable=money(amount - lawful),
                       flag="excess_absence_cut" if amount > lawful else "proportional_ok", source=SRC_S20,
                       note=(f"For {days:g} day(s) absent the cut can be at most {fmt_inr(lawful)} "
                             f"({fmt_inr(monthly_wage)} x {days:g} / {working_days:g})."))
        else:
            out.update(lawful_max=None, reclaimable=0.0, flag="absence_days_unknown", source=SRC_S20,
                       note="Tell Baaki how many days were missed to check this cut.")
    elif reason in EMPLOYER_AWAY_REASONS:
        out.update(flag="not_her_absence", source=SRC_S18 + " " + SRC_S20,
                   note="Days the family was away are not her absence from duty; the cut has no authorised basis.")
    elif reason in BREAKAGE_REASONS:
        out.update(flag="breakage_needs_proof", source=SRC_S21,
                   note="Claimed back in full; it would be lawful only for her proven neglect, at actual value, after she is heard.")
    elif reason in FINE_REASONS:
        out.update(flag="household_fine", source=SRC_S19)
    elif reason in ADVANCE_REASONS:
        out.update(lawful_max=amount, reclaimable=0.0, flag="advance_recovery_ok", source=SRC_S23)
    else:
        out.update(flag="no_authorised_basis", source=SRC_S18)
    return out


# --------------------------------------------------------------------------- the calculator
def calculate(*, monthly_wage: float, category: str = "unskilled", work_type: str | None = None,
              hours_per_day: float | None = 8, days_per_week: float = 6,
              unpaid_months: Iterable[str] | None = None, months_unpaid: float | None = None,
              last_month: str | None = None, paid_months: dict[str, float] | None = None,
              part_months: dict[str, dict[str, float]] | None = None,
              deductions: Iterable[dict[str, Any]] = (), advance_outstanding: float = 0,
              dismissed_on: str | dt.date | None = None, include_shortfall: bool = False,
              today: dt.date | None = None) -> dict[str, Any]:
    """Dues for one worker and one employer.

    unpaid_months: months with no pay at all ("2026-08"), or months_unpaid + last_month (default: the last
    complete month before today, or the dismissal month; a fraction such as 2.5 adds half of the month before).
    paid_months: month -> amount actually paid for that month (in full or in part; a part payment leaves the rest
    as unpaid wages). A cut named for the same month is part of what was withheld, so the month never claims more
    than wage - paid (if paid + cuts exceed the wage, the paid figure is read as the amount before the cut).
    part_months: month -> {"fraction": 0.5, "paid_per_month": 0} for part of a month she said ("dhai mahine").
    Returns contractual dues (unpaid agreed wages + reclaimable cuts - outstanding advance), the minimum-wage
    shortfall (each line carries is_estimate), due dates, flags and source strings.
    """
    today = today or default_today()
    wage = money(monthly_wage)
    category = category_for(work_type, category)
    dismissed = None
    if dismissed_on:
        dismissed = dismissed_on if isinstance(dismissed_on, dt.date) else dt.date.fromisoformat(str(dismissed_on)[:10])
    settlement_due = add_working_days(dismissed, 2) if dismissed else None

    parts = {month_key(parse_month(k)): {"fraction": float(v.get("fraction") or 0),
                                         "paid_per_month": float(v.get("paid_per_month") or 0)}
             for k, v in (part_months or {}).items() if float(v.get("fraction") or 0) > 0}
    unpaid = [month_key(parse_month(m)) for m in (unpaid_months or [])]
    if not unpaid and not parts and months_unpaid:
        end = last_month or (month_key(dismissed) if dismissed else last_complete_month(today))
        whole = int(months_unpaid)
        unpaid = previous_months(end, whole) if whole > 0 else []
        frac = round(float(months_unpaid) - whole, 4)
        if frac > 0:  # "dhai mahine": part of the month before the whole months (never dropped, never Rs 0)
            parts[month_key(add_months(parse_month(end), -whole))] = {"fraction": frac, "paid_per_month": 0.0}
    paid = {month_key(parse_month(k)): money(v) for k, v in (paid_months or {}).items()}
    unpaid = sorted(set(unpaid) - set(paid) - set(parts))
    parts = {m: v for m, v in parts.items() if m not in paid}

    items: list[dict[str, Any]] = []
    flags: list[str] = []
    sources: set[str] = set()

    def due_for(month: str) -> dt.date:
        due = normal_due_date(month)
        if settlement_due and due > settlement_due:
            due = settlement_due
        return due

    def due_fields(month: str) -> dict[str, Any]:
        due = due_for(month)
        return {"due_date": due.isoformat(), "overdue": today > due,
                "days_overdue": max(0, (today - due).days), "not_yet_due": today <= due,
                "due_source": SRC_S17_2 if settlement_due and due == settlement_due else SRC_S17_1}

    def wage_item(label: str, m: str, amount: float) -> dict[str, Any]:
        item = {"kind": "unpaid_wage", "label": label, "month": m, "amount": money(amount), "is_estimate": False,
                "included_in_total": True, **due_fields(m)}
        item["source"] = item["due_source"]
        if item["not_yet_due"]:
            item["label"] += f" (not yet due: due by {due_for(m).strftime('%d %b %Y').lstrip('0')})"
        return item

    # cuts first: a cut in a part-paid month is part of what was withheld that month
    checked = [check_deduction(d, wage, days_per_week) for d in deductions]
    for c in checked:
        if c.get("month"):
            c["month"] = month_key(parse_month(c["month"]))
    per_month_cut: dict[str, float] = {}
    for c in checked:
        if c.get("month"):
            per_month_cut[c["month"]] = per_month_cut.get(c["month"], 0.0) + c["amount"]

    # 1. unpaid agreed wages (whole months, part months she said, and the unpaid part of part-paid months)
    unpaid_total = 0.0
    for m in unpaid:
        items.append(wage_item(f"Unpaid wages: {month_label(m)}", m, wage))
        unpaid_total += wage
    for m, p in sorted(parts.items()):
        gap = money(max(0.0, wage - p["paid_per_month"]) * p["fraction"])
        if gap > 0:
            items.append(wage_item(f"Unpaid wages: {month_label(m)} ({p['fraction']:g} of a month, as she said)", m, gap))
            items[-1]["fraction"] = p["fraction"]
            unpaid_total += gap
    for m, amt in sorted(paid.items()):
        gap = money(wage - amt - per_month_cut.get(m, 0.0))
        if gap > 0:
            items.append(wage_item(f"Part unpaid: {month_label(m)} ({fmt_inr(amt)} of {fmt_inr(wage)} paid)", m, gap))
            unpaid_total += gap
    if any(i["kind"] == "unpaid_wage" for i in items):
        sources.add(SRC_S17_1)
        if settlement_due:
            sources.add(SRC_S17_2)
    if any(i.get("not_yet_due") for i in items):
        flags.append("not_yet_due")

    # 2. deductions. s.18(3): all cuts in one wage period <= 50% of it. Cuts without a month are checked
    # together against one month's wage, and the note says so.
    period_cut = dict(per_month_cut)
    if any(not c.get("month") for c in checked):
        period_cut[""] = sum(c["amount"] for c in checked if not c.get("month"))
    over_50 = {m: t for m, t in period_cut.items() if t > 0.5 * wage}
    reclaim_total = 0.0
    for c in checked:
        key = c.get("month") or ""
        if not c.get("month"):
            c["note"] = ((c.get("note") or "") + " Month not said: the 50% limit is checked against one month's "
                         f"wage ({fmt_inr(wage)}).").strip()
            c.setdefault("extra_flags", []).append("cut_month_not_said")
        if key in over_50 and c["reclaimable"] < c["amount"]:
            # whatever pushes the month above 50% is never lawful (s.18(3)); top up proportionally
            excess = over_50[key] - 0.5 * wage
            share = c["amount"] / over_50[key]
            c["reclaimable"] = money(min(c["amount"], max(c["reclaimable"], excess * share)))
            c.setdefault("extra_flags", []).append("over_50_percent")
        sources.add(c.get("source", SRC_S18))
        flags.append(c["flag"])
        if c["reclaimable"] > 0:
            reason = c["reason"].replace("_", " ")
            label = f"Cut taken back ({reason}" + (f", {c['days_absent']:g} days" if c.get("days_absent") else "") + ")"
            if c.get("month"):
                label += f": {month_label(c['month'])}"
            items.append({"kind": "illegal_deduction", "label": label, "month": c.get("month"),
                          "amount": c["reclaimable"], "is_estimate": False, "included_in_total": True,
                          "due_date": due_for(c["month"]).isoformat() if c.get("month") else None,
                          "source": c.get("source", SRC_S18), "flag": c["flag"], "note": c.get("note")})
            reclaim_total += c["reclaimable"]
    if over_50:
        flags.append("over_50_percent")
        sources.add(SRC_S18)

    advance = money(advance_outstanding or 0)
    if advance > 0:
        items.append({"kind": "advance_recovery", "label": "Advance still to be recovered (subtracted)", "month": None,
                      "amount": -advance, "is_estimate": False, "included_in_total": True, "due_date": None,
                      "source": SRC_S23})
        sources.add(SRC_S23)

    contractual = money(max(0.0, unpaid_total + reclaim_total - advance))

    # 3. minimum-wage shortfall (Haq Check) over every month we know about
    months_known = sorted(set(unpaid) | set(paid))
    shortfall_rows = []
    shortfall_total = 0.0
    any_estimate = False
    for m in (months_known if hours_per_day else []):  # no hours -> no Haq Check (never guess full-time)
        mw = minimum_wage(m, category, hours_per_day, days_per_week)
        row = {**mw.as_dict(), "agreed": wage, "gap": 0.0}
        if mw.amount is not None and mw.amount > wage:
            gap = money(mw.amount - wage)
            row["gap"] = gap
            shortfall_total += gap
            any_estimate = any_estimate or mw.is_estimate
            items.append({"kind": "min_wage_shortfall",
                          "label": f"Below minimum wage: {month_label(m)} ({fmt_inr(mw.amount)} minimum - {fmt_inr(wage)} agreed)",
                          "month": m, "amount": gap, "is_estimate": mw.is_estimate,
                          "included_in_total": include_shortfall, **due_fields(m), "source": mw.source})
            sources.add(mw.source)
        shortfall_rows.append(row)
    shortfall_total = money(shortfall_total)
    if shortfall_total > 0:
        flags.append("below_minimum_wage")

    # current monthly minimum for her hours (for the Haq Check card)
    ref_month = months_known[-1] if months_known else month_key(today)
    if hours_per_day:
        ref = minimum_wage(max(ref_month, month_key(GO6_START)), category, hours_per_day, days_per_week)
        haq = {"minimum_for_hours": ref.amount, "agreed": wage, "monthly_gap": money(max(0.0, (ref.amount or 0) - wage)),
               "is_estimate": ref.is_estimate, "basis": ref.basis, "source": ref.source, "needs_hours": False}
        sources.add(ref.source)
    else:
        haq = {"minimum_for_hours": None, "agreed": wage, "monthly_gap": None, "is_estimate": True,
               "basis": "Tell Baaki how many hours a day you work here to check the minimum wage.",
               "source": SRC_GO6.format(cat=CATEGORY_LABEL[category], monthly=f"{int(GO6_MONTHLY[category]):,}"),
               "needs_hours": True}
    haq.update(per_day_full_time=per_day_rate(category), full_time_monthly=GO6_MONTHLY[category],
               vda_note="VDA not notified after June 2026: basic pay only.")

    total = money(contractual + (shortfall_total if include_shortfall else 0.0))
    sources.add(NOTE_NO_EXTRAS)
    return {
        "inputs": {"monthly_wage": wage, "category": category, "work_type": work_type, "hours_per_day": hours_per_day,
                   "days_per_week": days_per_week, "unpaid_months": unpaid, "paid_months": paid,
                   "part_months": parts, "dismissed_on": dismissed.isoformat() if dismissed else None,
                   "include_shortfall": include_shortfall, "advance_outstanding": advance},
        "unpaid_wages": money(unpaid_total),
        "reclaimable_deductions": money(reclaim_total),
        "advance_outstanding": advance,
        "contractual_due": contractual,
        "min_wage_shortfall": shortfall_total,
        "shortfall_is_estimate": any_estimate,
        "total_with_shortfall": money(contractual + shortfall_total),
        "total": total,
        "haq_check": haq,
        "shortfall_by_month": shortfall_rows,
        "deductions": checked,
        "items": items,
        "due": {"settlement_due": settlement_due.isoformat() if settlement_due else None,
                "dismissed_on": dismissed.isoformat() if dismissed else None,
                "earliest_overdue": min((i["due_date"] for i in items if i.get("due_date") and i.get("overdue")),
                                        default=None)},
        "flags": sorted(set(flags)),
        "sources": sorted(sources),
        "disclaimer": DISCLAIMER,
    }


__all__ = ["calculate", "minimum_wage", "check_deduction", "round50", "per_day_rate", "GO6_MONTHLY",
           "category_for", "normal_due_date", "add_working_days", "fmt_inr", "previous_months"]
