"""Fair Pay Check (V01): the employer's self-check. Pure functions, no I/O, nothing stored.

compute()       -> the G.O.Ms.No.6 Hyderabad Zone-I minimum for this work, the gap and the cost per working day.
parse_spoken()  -> work type, hours a day, days a week and monthly pay from a Hinglish/English transcript,
                   using the deterministic app.lang parsers (never an LLM).

Every rupee figure comes from wages.minimum_wage(); this module only formats and divides.
Tone rule: information, not accusation. Part-time figures are always flagged as an estimate.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

from . import wages
from .lang import extract_amounts
from .lang.numbers import scan

# --------------------------------------------------------------------------- work types
# Each tap choice -> a designation G.O.Ms.No.6 Schedule-III lists, -> its skill category (via wages).
WORK_TYPES: dict[str, dict[str, str]] = {
    "maid": {"designation": "maid", "label": "Maid / cleaning",
             "order_line": "Sch-III 'Maid' (132), 'House keeping' (146), 'Cleaning of Vessels' (124): Unskilled"},
    "cooking": {"designation": "cook", "label": "Cooking",
                "order_line": "Sch-III 'Cook' (17): Skilled"},
    "both": {"designation": "maid", "label": "Cooking and cleaning",
             "order_line": "Sch-III 'Maid' (Unskilled) and 'Cook' (Skilled); the order has no combined role, "
                           "so the lower (Unskilled) rate is shown as the floor"},
    "care": {"designation": "caretaker", "label": "Child or elder care",
             "order_line": "Sch-III 'Ayah and other similar categories' (76), 'Care taker' (127): Unskilled"},
}

SOURCE_URL = "https://www.comply4hr.com/noti/2016/TLGMWR2026May30.PDF"
ZONE_NOTE = "Hyderabad inside GHMC = Zone-I (Municipal Corporation). Outside GHMC the Zone-II rate is lower."
VDA_NOTE = "Basic pay only: the cost-of-living allowance (VDA) is extra once the Labour Commissioner notifies it."
NOT_ADVICE = ("Information only, not legal advice. Baaki is not a lawyer or a government office. "
              "For a ruling, ask the Telangana Labour Department.")

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def current_month(today: dt.date | None = None) -> str:
    """This month in IST, never earlier than June 2026 (G.O.Ms.No.6 in force from 1 Jun 2026)."""
    d = today or dt.datetime.now(IST).date()
    return wages.month_key(max(d.replace(day=1), wages.GO6_START))


def _rupees_up(x: float) -> int:
    return int(math.ceil(round(x, 6)))


def compute(work_type: str, hours_per_day: float, days_per_week: float, monthly_pay: float,
            today: dt.date | None = None) -> dict[str, Any]:
    """The check. Raises ValueError for an unknown work type (the route validates ranges)."""
    if work_type not in WORK_TYPES:
        raise ValueError(f"work_type must be one of {sorted(WORK_TYPES)}")
    wt = WORK_TYPES[work_type]
    category = wages.category_for(wt["designation"])
    month = current_month(today)
    mw = wages.minimum_wage(month, category, hours_per_day, days_per_week)
    minimum = float(mw.amount or 0.0)
    pay = wages.money(monthly_pay)
    dpm = wages.days_per_month(days_per_week)  # working days a month (26 for a 6-day week)
    full_monthly = wages.GO6_MONTHLY[category]
    per_hour = wages.round50(full_monthly / 26 / 8)

    gap = wages.money(max(0.0, minimum - pay))
    fair = pay + 0.005 >= minimum
    per_day = _rupees_up(gap / dpm) if gap > 0 and dpm > 0 else 0

    hours_capped = min(8.0, float(hours_per_day))
    if mw.is_estimate:
        how = (f"Estimate: {wages.fmt_inr(full_monthly)} full-time monthly rate / 26 days / 8 hours "
               f"x {hours_capped:g} h a day x {dpm:g} working days a month = {wages.fmt_inr(minimum)} "
               f"(about {wages.fmt_inr(per_hour)} an hour). The order sets full-time monthly rates only; "
               f"it does not list part-time rates.")
    else:
        how = (f"Full-time (8 hours a day, 6 days a week): the notified {wages.CATEGORY_LABEL[category]} rate, "
               f"{wages.fmt_inr(full_monthly)} a month ({wages.fmt_inr(wages.per_day_rate(category))} a day = monthly / 26).")

    notes: list[str] = [VDA_NOTE, ZONE_NOTE]
    if float(hours_per_day) > 8:
        notes.append("Hours beyond 8 a day are overtime at double the rate (G.O. para 9); not added here.")
    if float(days_per_week) >= 7:
        notes.append("A 7th day is the weekly rest day: work on it is paid at double (G.O. para 5(5)); not added here.")
    alt = None
    if work_type == "both":
        cook = wages.minimum_wage(month, "skilled", hours_per_day, days_per_week)
        alt = {"category": "skilled", "label": "Cook (Skilled)", "minimum_monthly": cook.amount,
               "gap_monthly": wages.money(max(0.0, float(cook.amount or 0) - pay))}
        notes.append(f"If cooking is most of her work, the Cook (Skilled) rate applies: {wages.fmt_inr(cook.amount or 0)} "
                     "a month for these hours.")

    if fair:
        explanation = (f"You pay {wages.fmt_inr(pay)} a month. The minimum for this work is "
                       f"{'about ' if mw.is_estimate else ''}{wages.fmt_inr(minimum)}. You're paying fair. Thank you.")
    else:
        explanation = (f"You pay {wages.fmt_inr(pay)} a month. Telangana's {'estimated ' if mw.is_estimate else ''}minimum "
                       f"for this work is {wages.fmt_inr(minimum)}, a gap of {wages.fmt_inr(gap)} a month. Matching it "
                       f"costs about ₹{per_day} a working day.")

    return {
        "work_type": work_type,
        "work_label": wt["label"],
        "category": category,
        "category_label": wages.CATEGORY_LABEL[category],
        "order_line": wt["order_line"],
        "month": month,
        "hours_per_day": float(hours_per_day),
        "days_per_week": float(days_per_week),
        "working_days_per_month": dpm,
        "monthly_pay": pay,
        "minimum_monthly": minimum,
        "full_time_monthly": full_monthly,
        "per_hour_estimate": per_hour,
        "is_estimate": mw.is_estimate,
        "basis": mw.basis,
        "how": how,
        "gap_monthly": gap,
        "gap_yearly": wages.money(gap * 12),
        "per_day_to_close": per_day,
        "verdict": "fair" if fair else "below",
        "alt_rate": alt,
        "explanation": explanation,
        "notes": notes,
        "source": mw.source,
        "source_url": SOURCE_URL,
        "disclaimer": NOT_ADVICE,
    }


# --------------------------------------------------------------------------- spoken input
_HOUR_WORDS = {"ghanta", "ghante", "ghanton", "ghantey", "ghantay", "ganta", "gante", "hour", "hours", "hr", "hrs",
               "h", "घंटा", "घंटे", "घण्टे", "घंटों", "गंटे", "gantalu", "ganta", "గంటలు", "గంట"}
_DAY_WORDS = {"din", "dino", "dinon", "dinn", "day", "days", "दिन", "दिनों", "roju", "rojulu", "రోజులు", "రోజు"}
_ALL_WEEK = re.compile(r"(saaton|saato|saton|सातों|all\s+(?:7|seven)\s+days|every\s*day\s+of\s+the\s+week|"
                       r"poore\s+hafte|pura\s+hafta|bina\s+chhutti|no\s+(?:day\s+)?off)", re.I)
_ONE_OFF = re.compile(r"(ek\s+(?:din\s+)?(?:ki\s+)?chhutti|ek\s+chutti|sunday\s+(?:ko\s+)?(?:off|chhutti|chutti)|"
                      r"one\s+day\s+off|एक\s+(?:दिन\s+)?(?:की\s+)?छुट्टी|रविवार\s+(?:की\s+)?छुट्टी)", re.I)


def _kw(latin: str, indic: str) -> tuple[re.Pattern, re.Pattern]:
    # \b only around Latin words: Python's \b splits Devanagari/Telugu words at their vowel signs.
    return re.compile(r"\b(?:" + latin + r")\b", re.I), re.compile(indic)


_WORK_KW = {
    "cook": _kw(r"cook|cooking|cooks|khana|khaana|khanna|rasoi|roti|chapati|vanta",
                r"खाना|रसोई|कुक|రొట్టె|వంట"),
    "clean": _kw(r"maid|clean|cleaning|cleaner|safai|safaai|saaf|jhaadu|jhadu|pocha|poncha|bartan|bartans|vessels|"
                 r"kapde|kapda|laundry|washing|kaamwali|kamwali|bai|housekeeping|house\s*keeping|sweeping|"
                 r"panimanishi|mopping",
                 r"सफ़ाई|सफाई|झाड़ू|झाडू|पोछा|पोंछा|बर्तन|कपड़े|बाई|कामवाली|పనిమనిషి"),
    "care": _kw(r"baby|babies|bachcha|bachche|bacche|bachchon|child|children|childcare|kid|kids|nanny|ayah|"
                r"elder|elderly|buzurg|patient|dekhbhal|dekhbhaal|care|caretaker|eldercare",
                r"बच्चा|बच्चे|बच्चों|बुज़ुर्ग|बुजुर्ग|देखभाल|आया\s*का\s*काम"),
}


def _has(kind: str, text: str) -> bool:
    latin, indic = _WORK_KW[kind]
    return bool(latin.search(text) or indic.search(text))


def _next_word(toks, i: int) -> str:
    j = i + 1
    while j < len(toks) and toks[j].kind == "sym":
        j += 1
    return toks[j].text.lower().strip(".") if j < len(toks) else ""


def _work_type(text: str) -> str | None:
    cook, clean, care = _has("cook", text), _has("clean", text), _has("care", text)
    if cook and clean:
        return "both"
    if cook:
        return "cooking"
    if care and not clean:
        return "care"
    if clean:
        return "maid"
    return None


def parse_spoken(text: str) -> dict[str, Any]:
    """Transcript -> {work_type, hours_per_day, days_per_week, monthly_pay, missing}. Unknown fields are None."""
    text = (text or "").strip()
    out: dict[str, Any] = {"work_type": None, "hours_per_day": None, "days_per_week": None, "monthly_pay": None}
    if not text:
        out["missing"] = list(out)
        return out
    out["work_type"] = _work_type(text)

    _, toks, _, phrases = scan(text, "hi")
    used: list[tuple[int, int]] = []
    for p in phrases:
        if p.approx or p.value is None:
            continue
        val = float(p.value)
        nxt = _next_word(toks, p.ti1)
        if out["hours_per_day"] is None and nxt in _HOUR_WORDS and 0 < val <= 16:
            out["hours_per_day"] = val
            used.append((p.start, p.end))
        elif out["days_per_week"] is None and nxt in _DAY_WORDS and 1 <= val <= 7 and val == int(val):
            out["days_per_week"] = val
            used.append((p.start, p.end))
    if out["days_per_week"] is None:
        if _ALL_WEEK.search(text):
            out["days_per_week"] = 7.0
        elif _ONE_OFF.search(text):
            out["days_per_week"] = 6.0

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in used)

    amounts = [a for a in extract_amounts(text, "hi") if a["amount_inr"] >= 100 and free(a["start"], a["end"])]
    if not amounts:  # bare numbers like "1500" with no currency word
        amounts = [{"amount_inr": int(p.value)} for p in phrases
                   if p.value is not None and not p.approx and p.value.denominator == 1 and p.value >= 100
                   and free(p.start, p.end)]
    if amounts:
        out["monthly_pay"] = float(max(a["amount_inr"] for a in amounts))
    out["missing"] = [k for k in ("work_type", "hours_per_day", "days_per_week", "monthly_pay") if out[k] is None]
    return out


__all__ = ["compute", "parse_spoken", "WORK_TYPES", "current_month"]
