"""Confirmed facts -> app.wages.calculate inputs. The ONE place this happens.

The case (routes/cases.calc_from_facts), the Baaki Meter (meter.summarise) and the read-back (readback.said_total)
all go through facts_to_calc_inputs(), so the same words always give the same months, the same paid amounts and
the same total. The only difference between "what she said" (said_tally) and "Baaki's calculation" (calculate) is
the legal check of cuts (s.18 to s.20) and the opt-in minimum-wage shortfall; everything else is shared.

Fact keys (every key optional; a case needs monthly_wage):
  monthly_wage          agreed wage per month.
  unpaid_months         ["2026-08", ...]: the months counted as owed (an explicit list wins).
  unpaid_month_numbers  [8, 9, 10]: month names she said, through resolve_month() (the current month is this
                        year's, never last year's).
  months_unpaid         a count; 2.5 ("dhai mahine") is kept: whole months back from last_unpaid_month (default:
                        the dismissal month, else the last complete month) and half of the month before that.
  part_months           {"2026-08": 0.5}: part of a month (what a fractional count resolves to; frozen by Exit Kit).
  paid_per_month        the amount actually paid for EACH counted month when it is less than the wage
                        ("salary 5000, 4000 dete hain, teen mahine se"): each counted month becomes
                        paid_months[month] = paid_per_month, so only the gap (1,000 a month) is owed.
  paid_months           {month: amount actually paid for that month}. A cut named for the same month is part of
                        what was withheld (wages.calculate never claims more than wage - paid for it).
  paid_lumps            [2000]: one-off payments she received -> a visible negative line "Received from employer".
  owed_lumps            [1500]: one-off sums owed -> a positive line.
  deductions            [{amount, reason, days_absent, month}]. A cut with no month is placed in the latest
                        part-paid month that could hold it (and says so); with none, wages checks it against one
                        month's wage for the 50% limit (s.18(3)).
  advance_outstanding   subtracted (s.18(2)(f), s.23).
  final_settlement      {month, amount, days_worked, is_estimate, due_date, basis, source} from the Exit Kit:
                        wages for days worked in the last month, due within two working days (s.17(2)).
  dismissed_on, hours_per_day, days_per_week, work_type, category, include_shortfall.
  hours_known           whether she said her hours. case_hours() is the only reader of hours for a case.
  months_unclear        she gave an unclear count ("do teen mahine"): the read-back asks how many.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from . import wages

PAID_RECEIVED_LABEL = "Received from employer (as she said, subtracted)"
OWED_LUMP_LABEL = "Other amount owed (as she said)"


# --------------------------------------------------------------------------- dates
def today() -> dt.date:
    """IST today (app.clock with BAAKI_TODAY when present). Never the server's local date."""
    return wages.default_today()


def resolve_month(n: int, today_: dt.date) -> str:
    """Month number she said -> "YYYY-MM". The current month and earlier ones are this year; later ones last year.
    ("November" on 10 Nov 2026 is Nov 2026, not Nov 2025.)"""
    n = int(n)
    year = today_.year if n <= today_.month else today_.year - 1
    return f"{year:04d}-{n:02d}"


def not_yet_due(month: str, today_: dt.date, dismissed_on: str | None = None) -> bool:
    """s.17(1)(iv): wages for a month are due by the 7th of the next month (two working days after dismissal)."""
    due = wages.normal_due_date(month)
    if dismissed_on:
        settle = wages.add_working_days(dt.date.fromisoformat(str(dismissed_on)[:10]), 2)
        due = min(due, settle)
    return today_ <= due


def _num(x: Any) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _whole(x: float) -> int | float:
    return int(round(x)) if abs(x - round(x)) < 0.005 else round(x, 2)


# --------------------------------------------------------------------------- months
def resolve_months(facts: dict[str, Any], today_: dt.date | None = None) -> dict[str, Any]:
    """Which months are counted as owed: {whole: [...], part: {month: fraction}, end, how, not_yet_due: [...]}."""
    today_ = today_ or today()
    part = {wages.month_key(wages.parse_month(k)): float(v) for k, v in (facts.get("part_months") or {}).items()
            if _num(v) > 0}
    how = None
    whole: list[str] = []
    end = None
    if facts.get("unpaid_months"):
        whole = sorted({wages.month_key(wages.parse_month(m)) for m in facts["unpaid_months"]})
        how = "list"
    elif facts.get("unpaid_month_numbers"):
        whole = sorted({resolve_month(n, today_) for n in facts["unpaid_month_numbers"]})
        how = "names"
    elif _num(facts.get("months_unpaid")) > 0 and not part:
        count = _num(facts["months_unpaid"])
        dismissed = facts.get("dismissed_on")
        end = facts.get("last_unpaid_month") or (str(dismissed)[:7] if dismissed else wages.last_complete_month(today_))
        n = int(count)
        whole = wages.previous_months(end, n) if n > 0 else []
        frac = round(count - n, 4)
        if frac > 0:  # never dropped, never Rs 0: part of the month before the whole months
            part[wages.month_key(wages.add_months(wages.parse_month(end), -n))] = frac
        how = "count"
    if part and how is None:
        how = "part"
    counted = sorted(set(whole) | set(part))
    return {"whole": whole, "part": part, "counted": counted, "end": end or (counted[-1] if counted else None),
            "how": how, "count": len(whole) + sum(part.values()),
            "not_yet_due": [m for m in counted if not_yet_due(m, today_, facts.get("dismissed_on"))]}


# --------------------------------------------------------------------------- the one conversion
def facts_to_calc_inputs(facts: dict[str, Any], today_: dt.date | None = None) -> dict[str, Any]:
    """Facts -> {kwargs (for wages.calculate), extras (lines wages does not make), months, notes, flags}."""
    today_ = today_ or today()
    facts = facts or {}
    wage = wages.money(_num(facts.get("monthly_wage")))
    months = resolve_months(facts, today_)
    notes: list[str] = []
    flags: list[str] = []

    paid = {wages.month_key(wages.parse_month(k)): wages.money(_num(v))
            for k, v in (facts.get("paid_months") or {}).items()}
    unpaid = list(months["whole"])
    part = {m: {"fraction": f, "paid_per_month": 0.0} for m, f in months["part"].items()}
    ppm = _num(facts.get("paid_per_month"))
    if ppm > 0 and months["counted"]:
        # she is paid ppm for each counted month: only the gap is owed
        for m in unpaid:
            paid.setdefault(m, wages.money(ppm))
        unpaid = [m for m in unpaid if m not in paid]
        for m in part:
            part[m]["paid_per_month"] = wages.money(ppm)
        flags.append("paid_per_month_applied")
    elif ppm > 0 and wage and ppm < wage:
        notes.append("She is paid less than agreed each month, but no months were counted: tell Baaki for how many "
                     "months.")
        flags.append("paid_per_month_without_months")

    # cuts: a cut without a month goes to the latest part-paid month that could hold it
    deductions = []
    for d in facts.get("deductions") or []:
        dd = {"amount": _num(d.get("amount")), "reason": d.get("reason") or "other",
              "days_absent": d.get("days_absent"), "month": d.get("month")}
        deductions.append(dd)
    cut_in = {}
    for dd in deductions:
        if dd["month"]:
            mk = wages.month_key(wages.parse_month(dd["month"]))
            cut_in[mk] = cut_in.get(mk, 0.0) + dd["amount"]
    for dd in deductions:
        if dd["month"] or not wage:
            continue
        room = [m for m, amt in paid.items() if wage - amt - cut_in.get(m, 0.0) >= dd["amount"] > 0]
        if room:
            m = max(room)
            dd["month"] = m
            cut_in[m] = cut_in.get(m, 0.0) + dd["amount"]
            notes.append(f"A cut of {wages.fmt_inr(dd['amount'])} had no month: Baaki took it as part of what was "
                         f"held back in {wages.month_label(m)}, so it is not counted twice.")
            flags.append("cut_month_assumed")
        else:
            flags.append("cut_month_not_said")

    kwargs = {
        "monthly_wage": wage,
        "category": facts.get("category") or wages.category_for(facts.get("work_type")),
        "work_type": facts.get("work_type"),
        "hours_per_day": _num(facts.get("hours_per_day")) or None,
        "days_per_week": _num(facts.get("days_per_week")) or 6.0,
        "unpaid_months": unpaid,
        "months_unpaid": None,
        "paid_months": paid or None,
        "part_months": part or None,
        "deductions": deductions,
        "advance_outstanding": _num(facts.get("advance_outstanding")),
        "dismissed_on": facts.get("dismissed_on"),
        "include_shortfall": bool(facts.get("include_shortfall")),
        "today": today_,
    }

    extras: list[dict[str, Any]] = []
    for v in facts.get("owed_lumps") or []:
        if _num(v) > 0:
            extras.append({"kind": "unpaid_wage", "label": OWED_LUMP_LABEL, "month": None, "amount": wages.money(_num(v)),
                           "is_estimate": False, "included_in_total": True, "due_date": None,
                           "source": wages.SRC_S17_1})
    fs = facts.get("final_settlement")
    if isinstance(fs, dict) and _num(fs.get("amount")) > 0:
        due = fs.get("due_date")
        src = " ".join(x for x in (wages.SRC_S17_2, fs.get("source") or "") if x)
        extras.append({"kind": "final_settlement", "month": fs.get("month"), "amount": wages.money(_num(fs["amount"])),
                       "label": fs.get("label") or (f"Wages for {_num(fs.get('days_worked')):g} days worked in "
                                                    f"{wages.month_label(fs['month'])}" if fs.get("month")
                                                    else "Final settlement (wages up to the last day)"),
                       "is_estimate": bool(fs.get("is_estimate")), "included_in_total": True, "due_date": due,
                       "overdue": bool(due and today_.isoformat() > str(due)[:10]),
                       "source": src, "note": fs.get("basis") or None, "days_worked": fs.get("days_worked")})
    for v in facts.get("paid_lumps") or []:
        if _num(v) > 0:
            extras.append({"kind": "paid_received", "label": PAID_RECEIVED_LABEL, "month": None,
                           "amount": -wages.money(_num(v)), "is_estimate": False, "included_in_total": True,
                           "due_date": None, "source": ""})

    if facts.get("months_unclear"):
        flags.append("months_unclear")
    if months["part"]:
        flags.append("part_month")
    if not facts.get("hours_per_day"):
        flags.append("hours_unknown")
    return {"kwargs": kwargs, "extras": extras, "months": months, "notes": notes, "flags": flags,
            "stated_total": facts.get("stated_total")}


# --------------------------------------------------------------------------- what she said
def said_tally(facts: dict[str, Any], today_: dt.date | None = None,
               inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """What her words add up to (no legal check): owed months (the gap for part-paid ones) + cuts in full +
    lumps owed + final settlement - lumps received - advance. Steps tick up as the Meter shows them."""
    inp = inputs or facts_to_calc_inputs(facts, today_)
    kw = inp["kwargs"]
    wage = kw["monthly_wage"]
    steps: list[float] = []
    formula: list[str] = []
    total = 0.0

    def add(x: float) -> None:
        nonlocal total
        total = max(0.0, total + x)
        steps.append(_whole(total))

    def fmt(x: float) -> str:
        w = _whole(x)
        return f"{w:,}" if isinstance(w, int) else f"{w:,.2f}"

    cut_in: dict[str, float] = {}
    for d in kw["deductions"]:
        if d.get("month"):
            mk = wages.month_key(wages.parse_month(d["month"]))
            cut_in[mk] = cut_in.get(mk, 0.0) + d["amount"]
    month_gaps: list[float] = []
    for _m in kw["unpaid_months"]:
        month_gaps.append(wage)
    for m, p in sorted((kw["paid_months"] or {}).items()):
        month_gaps.append(max(0.0, wage - p - cut_in.get(m, 0.0)))
    part_gaps = [max(0.0, wage - p["paid_per_month"]) * p["fraction"] for _m, p in sorted((kw["part_months"] or {}).items())]
    gaps = [g for g in month_gaps if g > 0]
    for g in gaps:
        add(g)
    if gaps:
        same = len(set(gaps)) == 1
        formula.append(f"{len(gaps)} x {fmt(gaps[0])}" if same else " + ".join(fmt(g) for g in gaps))
    for g in part_gaps:
        if g > 0:
            add(g)
            formula.append(f"+ {fmt(g)}")
    for e in inp["extras"]:
        if e["kind"] in ("unpaid_wage", "final_settlement"):
            add(e["amount"])
            formula.append(f"+ {fmt(e['amount'])}")
    for d in kw["deductions"]:
        if d["amount"] > 0:
            add(d["amount"])
            formula.append(f"+ {fmt(d['amount'])} cut")
    for e in inp["extras"]:
        if e["kind"] == "paid_received":
            add(e["amount"])
            formula.append(f"- {fmt(-e['amount'])} paid")
    if kw["advance_outstanding"] > 0:
        add(-kw["advance_outstanding"])
        formula.append(f"- {fmt(kw['advance_outstanding'])} advance")
    stated = inp.get("stated_total")
    if not total and stated:
        total = float(stated)
        steps.append(_whole(total))
        formula.append(f"{fmt(total)} (said)")
    text = " ".join(formula)
    return {"total": _whole(total), "steps": steps, "formula": text[2:] if text.startswith("+ ") else text}


# --------------------------------------------------------------------------- Baaki's calculation
def calculate(facts: dict[str, Any], today_: dt.date | None = None, include_shortfall: bool = False) -> dict[str, Any]:
    """Facts -> the full calculation (wages.calculate + lumps, money received and the Exit Kit settlement)."""
    today_ = today_ or today()
    inp = facts_to_calc_inputs(facts, today_)
    kw = dict(inp["kwargs"])
    kw["include_shortfall"] = include_shortfall or kw["include_shortfall"]
    calc = wages.calculate(**kw)
    extras = inp["extras"]
    if extras:
        calc["items"].extend(extras)
        calc["sources"] = sorted(set(calc["sources"]) | {e["source"] for e in extras if e.get("source")})
    raw = sum(i["amount"] for i in calc["items"] if i.get("included_in_total") and i["kind"] != "min_wage_shortfall")
    contractual = wages.money(max(0.0, raw))
    shortfall = calc["min_wage_shortfall"]
    calc["contractual_due"] = contractual
    calc["total_with_shortfall"] = wages.money(contractual + shortfall)
    calc["total"] = wages.money(contractual + (shortfall if kw["include_shortfall"] else 0.0))
    calc["received_from_employer"] = wages.money(-sum(e["amount"] for e in extras if e["kind"] == "paid_received"))
    calc["owed_lumps"] = wages.money(sum(e["amount"] for e in extras if e["kind"] == "unpaid_wage"))
    calc["final_settlement"] = wages.money(sum(e["amount"] for e in extras if e["kind"] == "final_settlement"))
    if raw < 0:
        inp["flags"].append("received_more_than_owed")
    overdue = [i["due_date"] for i in calc["items"] if i.get("due_date") and i.get("overdue")]
    calc["due"]["earliest_overdue"] = min(overdue) if overdue else None
    calc["flags"] = sorted(set(calc["flags"]) | set(inp["flags"]))
    calc["notes"] = inp["notes"]
    calc["months"] = {**inp["months"], "names": inp["months"]["counted"]}
    calc["inputs"]["paid_per_month"] = _num(facts.get("paid_per_month")) or None
    calc["said"] = said_tally(facts, today_, inputs=inp)
    return calc


# --------------------------------------------------------------------------- hours
def hours_known(facts: dict[str, Any]) -> bool:
    return bool(_num((facts or {}).get("hours_per_day")))


def case_hours(case: Any) -> float | None:
    """Hours a day she actually said for this case, or None. Case.hours_per_day defaults to 8 in the database,
    so it is never read directly: unknown hours stay unknown ("hours not said: estimate needs hours")."""
    facts = case.facts() if callable(getattr(case, "facts", None)) else (getattr(case, "facts", None) or {})
    h = _num(facts.get("hours_per_day"))
    return h if h > 0 else None


HOURS_NOT_SAID = "hours not said: estimate needs hours"

__all__ = ["facts_to_calc_inputs", "calculate", "said_tally", "resolve_month", "resolve_months", "not_yet_due",
           "case_hours", "hours_known", "today", "HOURS_NOT_SAID"]
