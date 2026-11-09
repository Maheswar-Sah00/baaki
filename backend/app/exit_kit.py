"""Exit Kit (W03, lite): "Madam said don't come from tomorrow."

Pure, deterministic logic (no LLM, no network) plus the one table this feature needs.

* Due date: Code on Wages s.17(2), "within two working days" of removal or dismissal, from
  `wages.add_working_days` (Sundays skipped; public holidays are NOT skipped, so the date we show can only be
  the same as or earlier than the real one). We show a DATE, never an hours-and-minutes countdown.
* Part-month: monthly wage / working days a month (26 for a 6-day week, G.O. para 5(1) convention, via
  `wages.days_per_month`) x days worked, rounded DOWN to the rupee so it is never overstated.
* Earlier dues come from the existing case (recomputed from its confirmed facts by the case engine).
* Minimum-wage shortfall for the part-month is an estimate, labelled, and never added to the total.
* NEVER notice pay, gratuity, bonus, compensation or interest (law file section 8 B4).
"""
from __future__ import annotations

import datetime as dt
import json
import math
from typing import Any, Iterable, Optional

from sqlmodel import Field, SQLModel

from . import wages
from .db import now_iso

# --------------------------------------------------------------------------- table
class ExitKit(SQLModel, table=True):
    """One Exit Kit calculation (inputs + result), so GET /api/exit/{id} can show it again."""
    __tablename__ = "exit_kit"
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    employer_id: Optional[int] = Field(default=None, foreign_key="employer.id", index=True)
    case_id: Optional[int] = Field(default=None, foreign_key="case.id", index=True)
    last_day: str
    due_by: str
    total: float = 0
    result_json: str = "{}"
    created_at: str = Field(default_factory=now_iso)

    def result(self) -> dict[str, Any]:
        return json.loads(self.result_json or "{}")


# --------------------------------------------------------------------------- sources and wording
SRC_PART_MONTH = ("Part-month wages: agreed monthly wage / {div:g} working days a month x days worked "
                  "(the 26-day month of G.O.Ms.No.6 para 5(1) for a 6-day week), rounded down to the rupee.")
SRC_OUR_READING = "Applying s.17(2) to work in a household is Baaki's reading of the Code; no court has ruled on it."
DUE_NOTE = ("Two working days after the last working day. Sundays are skipped. Public holidays are not skipped, "
            "so the real date can be a day or two later, never earlier.")
NOT_CLAIMED = ("Baaki adds only wages for days worked and money already owed. It does not add notice pay, gratuity, "
               "bonus, compensation or interest.")
NEVER_CLAIM_WORDS = ("notice pay", "gratuity", "bonus", "compensation", "interest", "penalty")
ALLOWED_KINDS = {"final_settlement", "unpaid_wage", "illegal_deduction", "advance_recovery", "paid_back",
                 "min_wage_shortfall", "paid_received"}

# --------------------------------------------------------------------------- the gate checklist
# Calm and practical, never confrontational. Display text per language; speech adds <slow> and spells UPI.
CHECKLIST_IDS = ("amount", "last_day", "ledger_photo", "contact")
CHECKLIST: dict[str, list[str]] = {
    "te-IN": [
        "యజమానిని మీ చివరి లెక్క ఎంతో అడగండి. వారు చెప్పిన మొత్తాన్ని ఫోన్‌లో రికార్డ్ చేయండి, లేదా రాసి పెట్టుకోండి.",
        "మీ చివరి పని రోజు తేదీని రాసి పెట్టుకోండి.",
        "అడ్వాన్స్ లేదా లెక్కల పుస్తకం ఉంటే, సురక్షితం అనిపిస్తేనే, దాని ఫోటో తీసుకోండి.",
        "యజమాని ఫోన్ నంబర్, UPI ఐడీ సేవ్ చేసుకోండి. తర్వాత మాట్లాడడానికి అవి పనికొస్తాయి.",
    ],
    "hi-en": [
        "मालिक से अपना आख़िरी हिसाब पूछिए। जो रकम वो बताएँ, उसे phone में record कर लीजिए, या लिख लीजिए।",
        "अपने आख़िरी काम के दिन की तारीख़ लिख लीजिए।",
        "Advance या हिसाब की कॉपी हो, तो उसकी photo ले लीजिए, पर सिर्फ़ तभी जब सुरक्षित लगे।",
        "मालिक का phone number और UPI ID save कर लीजिए, बाद में बात करने के काम आएगा।",
    ],
    "en-IN": [
        "Ask the employer for your full and final amount. Record what they say on your phone, or write it down.",
        "Write down the date of your last working day.",
        "If there is an advance book or a ledger, take a photo of it, only if it feels safe.",
        "Save the employer's phone number and UPI ID, so you can follow up later.",
    ],
}
SPEECH_FIX = {"te-IN": (("UPI", "యూపీఐ"),), "hi-en": (), "en-IN": ()}
LANG_ALIASES = {"te": "te-IN", "te-IN": "te-IN", "hi-en": "hi-en", "hinglish": "hi-en", "hi-IN": "hi-en",
                "hi": "hi-en", "en": "en-IN", "en-IN": "en-IN"}


def norm_lang(lang: str | None) -> str:
    return LANG_ALIASES.get(lang or "", "te-IN")


def speech_text(text: str, lang: str) -> str:
    """What Timbre is asked to say (fixed strings, so the cache key never changes)."""
    for a, b in SPEECH_FIX.get(lang, ()):
        text = text.replace(a, b)
    return "<slow> " + text


def checklist_texts(lang: str) -> list[dict[str, str]]:
    lang = norm_lang(lang)
    return [{"id": i, "text": t, "speech": speech_text(t, lang), "lang": lang}
            for i, t in zip(CHECKLIST_IDS, CHECKLIST[lang])]


# --------------------------------------------------------------------------- dates and days
def due_by(last_day: dt.date) -> dt.date:
    """s.17(2): within two working days of removal (Sundays skipped, holidays not modelled)."""
    return wages.add_working_days(last_day, 2)


def month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def calendar_working_days(start: dt.date, end: dt.date, days_per_week: float = 6) -> int:
    """Working days from start to end inclusive: Sundays skipped; fewer than 6 days a week is pro-rated down."""
    if end < start:
        return 0
    n = sum(1 for k in range((end - start).days + 1) if (start + dt.timedelta(days=k)).weekday() != 6)
    dpw = max(0.0, min(6.0, float(days_per_week or 6)))
    return n if dpw >= 6 else int(math.floor(n * dpw / 6))


def days_worked_this_month(last_day: dt.date, *, given: float | None = None,
                           checkin_dates: Iterable[str] = (), start_date: str | None = None,
                           days_per_week: float = 6) -> tuple[float, str, bool]:
    """(days, how, is_estimate). Her own number wins; then her diary check-ins; then a calendar count."""
    if given is not None:
        return float(given), "you said", False
    first = month_start(last_day)
    in_month = {d[:10] for d in checkin_dates if d and first.isoformat() <= d[:10] <= last_day.isoformat()}
    if in_month:
        return float(len(in_month)), "diary check-ins", False
    start = first
    if start_date:
        try:
            sd = dt.date.fromisoformat(start_date[:10])
            if first <= sd <= last_day:
                start = sd
        except ValueError:
            pass
    return float(calendar_working_days(start, last_day, days_per_week)), "calendar count", True


def part_month_pay(monthly_wage: float, days: float, days_per_week: float = 6) -> tuple[float, float, str]:
    """(amount, divisor, basis). Capped at one month's wage; rounded down to the rupee."""
    div = wages.days_per_month(days_per_week) or 26.0
    days = max(0.0, min(float(days), div))
    amount = float(math.floor(monthly_wage / div * days + 1e-9))
    basis = f"{wages.fmt_inr(monthly_wage)} / {div:g} x {days:g} days = {wages.fmt_inr(amount)}"
    return amount, div, basis


def part_month_shortfall(month: str, days: float, part_pay: float, *, category: str, hours_per_day: float | None,
                         days_per_week: float) -> dict[str, Any] | None:
    """Minimum-wage gap for the days worked this month (always an estimate; never in the total)."""
    if not hours_per_day:
        return None
    mw = wages.minimum_wage(month, category, hours_per_day, days_per_week)
    if mw.amount is None:
        return None
    div = wages.days_per_month(days_per_week) or 26.0
    days = max(0.0, min(float(days), div))
    minimum_part = float(math.floor(mw.amount / div * days + 1e-9))
    gap = minimum_part - part_pay
    if gap <= 0:
        return None
    return {"kind": "min_wage_shortfall", "month": month, "amount": wages.money(gap), "is_estimate": True,
            "included_in_total": False,
            "label": (f"Below minimum wage this month (estimate): {wages.fmt_inr(minimum_part)} minimum for "
                      f"{days:g} days - {wages.fmt_inr(part_pay)}"),
            "basis": f"{wages.fmt_inr(mw.amount)} / {div:g} x {days:g} days ({mw.basis})",
            "source": mw.source}


# --------------------------------------------------------------------------- facts bookkeeping
def clean_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Case facts as they were before any earlier Exit Kit was applied to them (so a re-run never double counts)."""
    facts = json.loads(json.dumps(facts or {}))
    ek = facts.pop("exit_kit", None)
    if isinstance(ek, dict):
        facts.pop("final_settlement", None)  # the typed part-month fact this kit wrote
        if ek.get("frozen_parts"):
            facts.pop("part_months", None)
        lump = None if ek.get("typed") else ek.get("lump")  # older kits wrote the amount as an owed lump
        lumps = list(facts.get("owed_lumps") or [])
        if lump:
            for i, v in enumerate(lumps):
                if abs(float(v) - float(lump)) < 0.005:
                    lumps.pop(i)
                    break
        if lumps:
            facts["owed_lumps"] = lumps
        else:
            facts.pop("owed_lumps", None)
        restored = ek.get("removed_paid_month")
        if isinstance(restored, dict) and restored.get("month"):
            pm = dict(facts.get("paid_months") or {})
            pm[restored["month"]] = restored["amount"]
            facts["paid_months"] = pm
        if "prev_dismissed_on" in ek:
            prev = ek.get("prev_dismissed_on")
            if prev:
                facts["dismissed_on"] = prev
            else:
                facts.pop("dismissed_on", None)
    return facts


def build(*, last_day: dt.date, monthly_wage: float, days_per_week: float = 6, hours_per_day: float | None = None,
          category: str = "unskilled", days_given: float | None = None, checkin_dates: Iterable[str] = (),
          start_date: str | None = None, earlier: dict[str, Any] | None = None, amount_paid: float = 0,
          case_facts: dict[str, Any] | None = None, frozen_unpaid: list[str] | None = None,
          frozen_parts: dict[str, float] | None = None) -> dict[str, Any]:
    """The Exit Kit result (without checklist audio). `earlier` is the case engine's calculation for the case
    (its facts minus any earlier Exit Kit, with dismissed_on = last_day and its unpaid months frozen as
    `frozen_unpaid`), or None when there is no case."""
    month = wages.month_key(last_day)
    due = due_by(last_day)
    days, how, days_est = days_worked_this_month(last_day, given=days_given, checkin_dates=checkin_dates,
                                                 start_date=start_date, days_per_week=days_per_week)
    items: list[dict[str, Any]] = []
    notes: list[str] = []
    sources: list[str] = [wages.SRC_S17_2, SRC_OUR_READING]

    facts = clean_facts(case_facts or {})
    earlier_items = list((earlier or {}).get("items") or [])
    counted_unpaid = set(((earlier or {}).get("months") or {}).get("counted")
                         or ((earlier or {}).get("inputs") or {}).get("unpaid_months") or [])
    paid_months = {wages.month_key(wages.parse_month(k)): float(v) for k, v in (facts.get("paid_months") or {}).items()}

    # 1. this month's days (part-month)
    part_amount, div, part_basis = part_month_pay(monthly_wage, days, days_per_week)
    paid_this_month = paid_months.get(month)
    already_full = month in counted_unpaid
    lump = 0.0
    removed_paid: dict[str, Any] | None = None
    if already_full:
        notes.append(f"{wages.month_label(month)} is already counted in full in your case, so it is not added again.")
    else:
        owed = part_amount
        basis = part_basis
        if paid_this_month is not None:
            owed = max(0.0, part_amount - paid_this_month)
            basis += f" - {wages.fmt_inr(paid_this_month)} already paid for {wages.month_label(month)}"
            removed_paid = {"month": month, "amount": paid_this_month}
            # the case's own "part unpaid" line for this month is replaced by the part-month line
            earlier_items = [i for i in earlier_items if not (i.get("kind") == "unpaid_wage" and i.get("month") == month)]
        lump = owed
        items.append({"kind": "final_settlement", "month": month, "amount": wages.money(owed), "is_estimate": days_est,
                      "included_in_total": True, "days_worked": days, "days_how": how,
                      "label": f"Wages for {days:g} days worked in {wages.month_label(month)}",
                      "basis": basis, "source": SRC_PART_MONTH.format(div=div), "due_date": due.isoformat()})
        sources.append(SRC_PART_MONTH.format(div=div))

    # 2. earlier dues from the existing case (unpaid months, cuts taken back, advance, shortfall lines)
    for it in earlier_items:
        if it.get("kind") == "min_wage_shortfall" and it.get("month") == month and not already_full:
            continue  # this month's minimum-wage line is recomputed for the part-month below
        kind = it.get("kind") if it.get("kind") in ALLOWED_KINDS else "unpaid_wage"
        items.append({"kind": kind, "month": it.get("month"), "amount": wages.money(float(it.get("amount") or 0)),
                      "is_estimate": bool(it.get("is_estimate")), "included_in_total": bool(it.get("included_in_total", True)),
                      "label": it.get("label") or "", "basis": it.get("note") or "", "source": it.get("source") or "",
                      "due_date": it.get("due_date"), "from_case": True})
        if it.get("source"):
            sources.append(it["source"])
    if amount_paid > 0:
        items.append({"kind": "paid_back", "month": None, "amount": -wages.money(amount_paid), "is_estimate": False,
                      "included_in_total": True, "label": "Already paid back through Baaki (subtracted)", "basis": "",
                      "source": "", "due_date": None, "from_case": True})

    # 3. this month's minimum-wage gap (estimate, shown, not added)
    if not already_full:
        sf = part_month_shortfall(month, days, part_amount, category=category, hours_per_day=hours_per_day,
                                  days_per_week=days_per_week)
        if sf:
            sf["due_date"] = due.isoformat()
            items.append(sf)
            sources.append(sf["source"])

    total = wages.money(max(0.0, sum(i["amount"] for i in items if i["included_in_total"])))
    shortfall_shown = wages.money(sum(i["amount"] for i in items
                                      if i["kind"] == "min_wage_shortfall" and not i["included_in_total"]))
    sources.append(NOT_CLAIMED)

    # what the case should hold so the normal Polite step asks for this amount
    patch: dict[str, Any] = {"dismissed_on": last_day.isoformat()}
    if frozen_unpaid is not None and not facts.get("unpaid_months"):
        # months_unpaid without a list would otherwise be re-anchored on the dismissal month
        patch["unpaid_months"] = list(frozen_unpaid)
    if frozen_parts and not facts.get("part_months"):
        patch["part_months"] = dict(frozen_parts)  # "dhai mahine" keeps its half month after the exit
    # typed fact (not an owed lump): the case keeps the estimate label, the s.17(2) source and the due date
    patch["final_settlement"] = ({"month": month, "amount": wages.money(lump), "days_worked": days,
                                  "is_estimate": days_est, "due_date": due.isoformat(),
                                  "label": f"Wages for {days:g} days worked in {wages.month_label(month)}",
                                  "basis": part_basis if paid_this_month is None else
                                  f"{part_basis} - {wages.fmt_inr(paid_this_month)} already paid for {wages.month_label(month)}",
                                  "source": SRC_PART_MONTH.format(div=div)} if lump > 0 else {})
    patch["owed_lumps"] = list(facts.get("owed_lumps") or [])
    if removed_paid:
        pm = dict(facts.get("paid_months") or {})
        pm.pop(removed_paid["month"], None)
        pm.pop(removed_paid["month"] + "-01", None)
        patch["paid_months"] = pm
    patch["exit_kit"] = {"lump": lump, "typed": True, "month": month, "days_worked": days,
                         "last_day": last_day.isoformat(), "removed_paid_month": removed_paid,
                         "prev_dismissed_on": facts.get("dismissed_on"),
                         "frozen_parts": bool(frozen_parts and not facts.get("part_months"))}

    return {
        "last_day": last_day.isoformat(),
        "month": month,
        "due_by": due.isoformat(),
        "due_weekday": due.strftime("%A"),
        "basis": {"due_rule": wages.SRC_S17_2, "due_note": DUE_NOTE, "our_reading": SRC_OUR_READING,
                  "part_month": None if already_full else part_basis, "days_worked": days, "days_how": how,
                  "divisor": div, "monthly_wage": wages.money(monthly_wage), "not_claimed": NOT_CLAIMED},
        "items": items,
        "total": total,
        "shortfall_estimate_not_in_total": shortfall_shown,
        "is_estimate_flags": {"days_worked": days_est, "part_month": days_est,
                              "min_wage_shortfall": shortfall_shown > 0,
                              "due_date_ignores_holidays": True,
                              "any": days_est or shortfall_shown > 0 or any(i["is_estimate"] for i in items)},
        "notes": notes,
        "case_facts_patch": patch,
        "sources": list(dict.fromkeys(s for s in sources if s)),
        "disclaimer": wages.DISCLAIMER,
    }


def find_never_claims(result: dict[str, Any]) -> list[str]:
    """Item labels/kinds that would claim something Baaki must never claim (should always be empty)."""
    bad = []
    for it in result.get("items") or []:
        text = f"{it.get('kind', '')} {it.get('label', '')}".lower()
        if it.get("kind") not in ALLOWED_KINDS or any(w in text for w in NEVER_CLAIM_WORDS):
            bad.append(it.get("label") or it.get("kind") or "?")
    return bad


__all__ = ["ExitKit", "build", "due_by", "part_month_pay", "days_worked_this_month", "calendar_working_days",
           "checklist_texts", "clean_facts", "find_never_claims", "norm_lang", "CHECKLIST", "NOT_CLAIMED"]
