"""Baaki Meter: partial transcript -> running total with amount chips. No LLM, a few milliseconds.

Works on Telugu script, romanised Telugu (with or without IAST marks), Hindi, Hinglish and English:
  "మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు"   -> 3 x 4,000 = 12,000
  "mūḍu nelalu, nelaku nālugu vēlu"                 -> 12,000
  "teen mahine ki salary chaar hazaar"              -> 12,000
  "₹4,000" / "4 thousand"                           -> 4,000

Every rupee value comes from app.lang.amounts; this module only decides what each amount is (a monthly wage,
a cut, an advance, a payment, a stated total) from the words around it, and how many months it covers.
The meter is a live tally of what she SAYS. The legal analysis (proportional absence cuts, minimum wage)
happens in app.wages after she confirms.
"""
from __future__ import annotations

import time
from typing import Any

from .lang._text import Tok, norm_deva, norm_telu, skel
from .lang.amounts import extract_amounts
from .lang.numbers import canon_lang, scan


def _k(words: list[str]) -> set[str]:
    out = set()
    for w in words:
        if any("ఀ" <= c <= "౿" for c in w):
            out.add(norm_telu(w))
        elif any("ऀ" <= c <= "ॿ" for c in w):
            out.add(norm_deva(w))
        else:
            out.add(skel(w))
    return out


def _key(t: Tok) -> str:
    if t.script == "telu":
        return norm_telu(t.w)
    if t.script == "deva":
        return norm_deva(t.w)
    return skel(t.w)


# ---- vocabularies (keys: Latin skeleton / Devanagari / Telugu normalised) --------------------------------
MONTHS_COUNT = _k(["mahine", "mahino", "mahinon", "months", "month", "mahina", "nelalu", "nelala", "nela",
                   "nelaluga", "महीने", "महीनों", "महीना", "माह"])
MONTHS_COUNT_TE = [norm_telu(w) for w in ["నెలలు", "నెలల", "నెలలుగా", "నెలా"]]
MONTHS_COUNT_TE_EXACT = {norm_telu("నెల")}
DAYS_COUNT = _k(["din", "dino", "dinon", "days", "day", "roju", "rojulu", "rojula", "दिन", "दिनों"])
DAYS_COUNT_TE = [norm_telu(w) for w in ["రోజులు", "రోజుల", "రోజు"]]
HOURS_COUNT = _k(["ghante", "ghanta", "ghanton", "hours", "hour", "hrs", "gantalu", "ganta", "gantala",
                  "घंटे", "घंटा", "घंटों"])
HOURS_COUNT_TE = [norm_telu(w) for w in ["గంటలు", "గంట", "గంటల"]]

PER_MONTH = _k(["nelaku", "nelaki", "monthly", "per", "har", "every", "prati", "maheena", "हर", "प्रति", "मासिक"])
PER_MONTH_TE = [norm_telu(w) for w in ["నెలకు", "నెలకి", "ప్రతి"]]
PER_MONTH_AFTER = _k(["mahina", "month", "maah", "monthly", "nelaku", "nela", "महीना", "माह"])
DEDUCT = _k(["cut", "kaat", "kaata", "kaati", "kaate", "kata", "katauti", "deducted", "deduct", "deduction",
             "kat", "katoti", "कटौती", "काट", "काटा", "काटे", "काटी", "कट"])
DEDUCT_TE = [norm_telu(w) for w in ["కట్", "కోత", "కటింగ్", "కట్టింగ్", "తగ్గించ"]]
ADVANCE = _k(["advance", "udhaar", "udhar", "loan", "एडवांस", "उधार"])
ADVANCE_TE = [norm_telu(w) for w in ["అడ్వాన్స్", "అప్పు"]]
PAID = _k(["paid", "pays", "pay", "diya", "diye", "di", "dia", "dete", "deti", "deta", "dethe", "mila", "mile", "mili",
           "milta", "milte", "received", "got", "gave", "gives", "give", "ichcharu", "istaru", "isthaaru", "isthaadu",
           "istundi", "देते", "देती", "देता", "मिलता", "मिलते",
           "ichaaru", "icharu", "ichhaaru", "ichhadu", "ichadu", "ichindi", "dita", "दिया", "दिए", "दी", "मिला",
           "मिले", "मिली"])
PAID_TE = [norm_telu(w) for w in ["ఇచ్చారు", "ఇచ్చాడు", "ఇచ్చింది", "ఇచ్చా", "ఇస్తారు", "ఇస్తాడు", "ఇస్తుంది",
                                   "వచ్చాయి"]]
NEG = _k(["nahi", "nahin", "nai", "na", "not", "no", "never", "didnt", "didn't", "ledu", "ivvaledu", "ivvale",
          "raledu", "kaadu", "bina", "नहीं", "नही", "ना", "न"])
NEG_TE = [norm_telu(w) for w in ["లేదు", "ఇవ్వలేదు", "రాలేదు", "ఇవ్వలే", "కాదు", "లేరు"]]
ABSENCE = _k(["bimar", "bimaar", "sick", "fever", "bukhar", "chutti", "chhutti", "leave", "absent", "jvaram",
              "jwaram", "selavu", "बीमार", "बुखार", "छुट्टी"])
ABSENCE_TE = [norm_telu(w) for w in ["జ్వరం", "సెలవు", "ఒంట్లో", "బాలేదు"]]
EMPLOYER_AWAY = _k(["gaon", "village", "ooru", "uru", "trip", "vacation", "bahar", "गांव", "गाँव"])
EMPLOYER_AWAY_TE = [norm_telu(w) for w in ["ఊరు", "ఊరికి", "ఊర్లో"]]
BREAKAGE = _k(["broke", "broken", "toota", "tuta", "tooti", "tuti", "glass", "plate", "damage", "pagilindi",
               "टूटा", "टूटी"])
BREAKAGE_TE = [norm_telu(w) for w in ["పగిలి", "పగిలింది", "విరిగి"]]
BARRIER_WORDS = _k(["and", "aur", "phir", "but", "lekin", "kani", "kaani", "inka", "plus", "also", "और", "फिर",
                    "लेकिन", "మరియు", "కానీ", "ఇంకా", "తర్వాత"])
BARRIER_SYMS = {",", ";", ".", "!", "?", "।", "॥", "|"}

KIND_LABEL = {
    "rate": "Salary per month", "cut": "Cut from pay", "advance": "Advance taken", "paid": "Paid",
    "stated_total": "Total she said", "owed": "Amount owed", "months": "Months unpaid", "days": "Days",
    "hours": "Hours a day",
}


def _te_in(k: str, prefixes: list[str]) -> bool:
    return any(k.startswith(p) for p in prefixes)


def _is(t: Tok | None, latin: set[str], te: list[str] | None = None, te_exact: set[str] | None = None) -> bool:
    if t is None or t.kind != "word":
        return False
    k = _key(t)
    if t.script == "telu":
        return bool((te_exact and k in te_exact) or (te and _te_in(k, te)))
    return k in latin


def _tok_range(toks: list[Tok], start: int, end: int) -> tuple[int, int]:
    i0 = next((i for i, t in enumerate(toks) if t.end > start), len(toks))
    i1 = max((i for i, t in enumerate(toks) if t.start < end), default=i0)
    return i0, i1


def _barrier(t: Tok) -> bool:
    return (t.kind == "sym" and t.w in BARRIER_SYMS) or (t.kind == "word" and _key(t) in BARRIER_WORDS)


def _clause(toks: list[Tok], i0: int, i1: int) -> tuple[int, int]:
    a = i0
    while a - 1 >= 0 and not _barrier(toks[a - 1]):
        a -= 1
    b = i1
    while b + 1 < len(toks) and not _barrier(toks[b + 1]):
        b += 1
    return a, b


def _counts(text: str, lang: str | None, toks: list[Tok], amount_tok_spans: list[tuple[int, int]]):
    """Number phrases followed by month / day / hour words (not inside an amount span)."""
    _, ptoks, _, phrases = scan(text, lang)
    out = []
    for p in phrases:
        if p.approx or p.value is None or p.value.denominator != 1 or p.value <= 0 or p.value > 60:
            continue
        if any(p.start < e and s < p.end for s, e in amount_tok_spans):
            continue
        nxt = ptoks[p.ti1 + 1] if p.ti1 + 1 < len(ptoks) else None
        if _is(nxt, ABSENCE, ABSENCE_TE) and p.ti1 + 2 < len(ptoks):  # "2 sick days", "do bimari ke din"
            nxt = ptoks[p.ti1 + 2] if _is(ptoks[p.ti1 + 2], DAYS_COUNT, DAYS_COUNT_TE) else nxt
        kind = None
        if _is(nxt, MONTHS_COUNT, MONTHS_COUNT_TE, MONTHS_COUNT_TE_EXACT):
            kind = "months"
        elif _is(nxt, DAYS_COUNT, DAYS_COUNT_TE):
            kind = "days"
        elif _is(nxt, HOURS_COUNT, HOURS_COUNT_TE):
            kind = "hours"
        if kind and nxt is not None:
            out.append({"kind": kind, "value": int(p.value), "start": p.start, "end": nxt.end,
                        "text": text[p.start:nxt.end]})
    return out


def _classify(a: dict, toks: list[Tok]) -> tuple[str, dict[str, Any]]:
    i0, i1 = _tok_range(toks, a["start"], a["end"])
    c0, c1 = _clause(toks, i0, i1)
    clause = toks[c0:c1 + 1]
    near_before = toks[max(c0, i0 - 3):i0]
    near_after = toks[i1 + 1:min(c1, i1 + 3) + 1]
    hint = a.get("label_hint")
    extra: dict[str, Any] = {}

    def any_in(ts, latin, te=None):
        return any(_is(t, latin, te) for t in ts)

    negated = any_in(clause, NEG, NEG_TE)
    if hint == "advance" or any_in(near_before + near_after, ADVANCE, ADVANCE_TE):
        return "advance", extra
    if hint == "deduction" or any_in(clause, DEDUCT, DEDUCT_TE):
        if any_in(clause, ABSENCE, ABSENCE_TE) or any_in(toks[max(0, c0 - 8):c0], ABSENCE, ABSENCE_TE):
            extra["reason"] = "sick"
        elif any_in(clause, EMPLOYER_AWAY, EMPLOYER_AWAY_TE):
            extra["reason"] = "employer_away"
        elif any_in(clause, BREAKAGE, BREAKAGE_TE):
            extra["reason"] = "breakage"
        return "cut", extra
    if hint in ("balance", "total"):
        return "stated_total", extra
    per_month = any_in(near_before, PER_MONTH, PER_MONTH_TE) or any_in(near_after[:1], PER_MONTH_AFTER, ["నెలకు", "నెలకి"])
    if any_in(clause, PAID, PAID_TE) and not negated and hint != "wage":
        extra["per_month"] = per_month
        return "paid", extra
    if hint == "wage" or per_month:
        return "rate", extra
    return "owed", extra


def meter(text: str, lang: str | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    text = text or ""
    lang_c = canon_lang(lang, strict=False)
    amounts = extract_amounts(text, lang_c) if text.strip() else []
    _, toks, _, _ = scan(text, lang_c) if text.strip() else ("", [], [], [])
    counts = _counts(text, lang_c, toks, [(a["start"], a["end"]) for a in amounts]) if text.strip() else []

    chips: list[dict[str, Any]] = []
    for a in amounts:
        kind, extra = _classify(a, toks)
        chips.append({"kind": kind, "value": a["amount_inr"], "label": KIND_LABEL[kind], "label_hint": a["label_hint"],
                      "span": [a["start"], a["end"]], "text": a["source_text"], **extra})
    for c in counts:
        chips.append({"kind": c["kind"], "value": c["value"], "label": KIND_LABEL[c["kind"]], "label_hint": None,
                      "span": [c["start"], c["end"]], "text": c["text"], "is_count": True})
    chips.sort(key=lambda c: c["span"][0])
    for i, c in enumerate(chips):
        c["id"] = f"c{i + 1}"

    summary = summarise(chips)
    summary["ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return {"text": text, "lang": lang, "chips": chips, **summary}


def summarise(chips: list[dict[str, Any]]) -> dict[str, Any]:
    """Running total from (possibly edited) chips. The worker can remove or fix chips; call this again."""
    rates = [c for c in chips if c["kind"] == "rate"]
    owed = [c for c in chips if c["kind"] == "owed"]
    months_c = [c for c in chips if c["kind"] == "months"]
    days_c = [c for c in chips if c["kind"] == "days"]
    cuts = [c for c in chips if c["kind"] == "cut"]
    advances = [c for c in chips if c["kind"] == "advance"]
    paid = [c for c in chips if c["kind"] == "paid"]
    stated = [c for c in chips if c["kind"] == "stated_total"]

    months = months_c[0]["value"] if months_c else None
    rate = rates[-1]["value"] if rates else None
    if rate is None and months and owed:
        # "teen mahine, chaar hazaar" with no rate word: one amount next to a month count is the monthly wage
        rate = owed.pop(0)["value"]
        for c in chips:
            if c["kind"] == "owed" and c["value"] == rate:
                c["kind"], c["label"], c["inferred"] = "rate", KIND_LABEL["rate"], True
                break
    steps: list[int] = []
    total = 0
    formula: list[str] = []
    if rate is not None:
        n = months or 1
        for i in range(1, n + 1):
            total = rate * i
            steps.append(total)
        formula.append(f"{n} x {rate:,}" if months else f"{rate:,}")
    for c in owed:
        total += c["value"]
        steps.append(total)
        formula.append(f"+ {c['value']:,}")
    for c in cuts:
        total += c["value"]
        steps.append(total)
        formula.append(f"+ {c['value']:,} cut")
    for c in paid:
        sub = c["value"] * (months or 1) if c.get("per_month") else c["value"]
        total = max(0, total - sub)
        steps.append(total)
        formula.append(f"- {sub:,} paid")
    for c in advances:
        total = max(0, total - c["value"])
        steps.append(total)
        formula.append(f"- {c['value']:,} advance")
    stated_total = stated[-1]["value"] if stated else None
    if total == 0 and stated_total:
        total = stated_total
        steps.append(total)
        formula.append(f"{stated_total:,} (said)")
    days = days_c[0]["value"] if days_c else None
    return {
        "total": total,
        "steps": steps,
        "formula": " ".join(formula),
        "monthly_wage": rate,
        "months_unpaid": months,
        "cuts": [{"amount": c["value"], "reason": c.get("reason"), "days_absent": days if c.get("reason") == "sick" else None}
                 for c in cuts],
        "advance": sum(c["value"] for c in advances),
        "paid": [{"amount": c["value"], "per_month": bool(c.get("per_month"))} for c in paid],
        "stated_total": stated_total,
        "matches_stated_total": (stated_total == total) if stated_total is not None else None,
        "days": days,
        "hours_per_day": next((c["value"] for c in chips if c["kind"] == "hours"), None),
    }


__all__ = ["meter", "summarise"]
