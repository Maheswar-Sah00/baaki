"""Read-back text for Timbre: what she said, slowly, with pauses, amounts written as words.

Feasibility test 2: `<pauses>` gives a 0.7-1.0 s gap in te-IN and hi-en and is never spoken; `<slow>` at most
slightly slows speech. Test 3: write amounts as words (they come from the deterministic formatter, so the
read-back says exactly what the screen shows). For a Latin-only Hinglish sentence, words like
"chaar hazaar rupaye" are read correctly; digits would be read as English.
"""
from __future__ import annotations

from typing import Any

from .lang.numbers import inr_to_words, number_to_words

LANGS = ("te-IN", "hi-en", "hi-IN", "en-IN")


def _int(x: float | int | None) -> int:
    return int(round(float(x or 0)))


def _parts_te(f: dict[str, Any], said_total: int, legal_total: int | None) -> list[str]:
    out = []
    name = f.get("employer_name")
    if name:
        out.append(f"{name} దగ్గర.")
    months, wage = f.get("months_unpaid"), f.get("monthly_wage")
    if months and wage:
        out.append(f"{number_to_words(int(months), 'te')} నెలల జీతం రాలేదు,")
        out.append(f"నెలకు {inr_to_words(_int(wage), 'te')}.")
    elif wage:
        out.append(f"నెలకు జీతం {inr_to_words(_int(wage), 'te')}.")
    if f.get("hours_per_day"):
        out.append(f"రోజుకు {number_to_words(_int(f['hours_per_day']), 'te')} గంటల పని.")
    for d in f.get("deductions") or []:
        days = f" {number_to_words(_int(d['days_absent']), 'te')} రోజులకు" if d.get("days_absent") else ""
        out.append(f"{days} {inr_to_words(_int(d['amount']), 'te')} కట్ చేశారు.".strip())
    if f.get("advance_outstanding"):
        out.append(f"అడ్వాన్స్ {inr_to_words(_int(f['advance_outstanding']), 'te')}.")
    if said_total:
        out.append(f"మొత్తం {inr_to_words(said_total, 'te')}.")
    if legal_total is not None and legal_total != said_total:
        out.append(f"చట్టం ప్రకారం అడగగలిగేది {inr_to_words(legal_total, 'te')}.")
    out.append("సరేనా?")
    return out


def _parts_hinglish(f: dict[str, Any], said_total: int, legal_total: int | None) -> list[str]:
    out = []
    name = f.get("employer_name")
    if name:
        out.append(f"{name}.")
    months, wage = f.get("months_unpaid"), f.get("monthly_wage")
    if months and wage:
        mw = "mahina" if int(months) == 1 else "mahine"
        out.append(f"{number_to_words(int(months), 'hinglish')} {mw} ki salary nahi mili,")
        out.append(f"{inr_to_words(_int(wage), 'hinglish')} har mahina.")
    elif wage:
        out.append(f"Salary {inr_to_words(_int(wage), 'hinglish')} har mahina.")
    if f.get("hours_per_day"):
        h = _int(f["hours_per_day"])
        out.append(f"Roz {number_to_words(h, 'hinglish')} {'ghanta' if h == 1 else 'ghante'} kaam.")
    for d in f.get("deductions") or []:
        days = f"{number_to_words(_int(d['days_absent']), 'hinglish')} din ke liye " if d.get("days_absent") else ""
        out.append(f"{days}{inr_to_words(_int(d['amount']), 'hinglish')} kaate gaye.")
    if f.get("advance_outstanding"):
        out.append(f"Advance {inr_to_words(_int(f['advance_outstanding']), 'hinglish')}.")
    if said_total:
        out.append(f"Kul {inr_to_words(said_total, 'hinglish')}.")
    if legal_total is not None and legal_total != said_total:
        out.append(f"Kanoon ke hisaab se maang sakte hain {inr_to_words(legal_total, 'hinglish')}.")
    out.append("Sahi hai?")
    return out


def _parts_hi(f: dict[str, Any], said_total: int, legal_total: int | None) -> list[str]:
    out = []
    if f.get("employer_name"):
        out.append(f"{f['employer_name']}।")
    months, wage = f.get("months_unpaid"), f.get("monthly_wage")
    if months and wage:
        out.append(f"{number_to_words(int(months), 'hi')} महीने की तनख्वाह नहीं मिली,")
        out.append(f"हर महीने {inr_to_words(_int(wage), 'hi')}।")
    elif wage:
        out.append(f"तनख्वाह हर महीने {inr_to_words(_int(wage), 'hi')}।")
    for d in f.get("deductions") or []:
        out.append(f"{inr_to_words(_int(d['amount']), 'hi')} काटे गए।")
    if said_total:
        out.append(f"कुल {inr_to_words(said_total, 'hi')}।")
    if legal_total is not None and legal_total != said_total:
        out.append(f"कानून के हिसाब से माँग सकते हैं {inr_to_words(legal_total, 'hi')}।")
    out.append("सही है?")
    return out


def _parts_en(f: dict[str, Any], said_total: int, legal_total: int | None) -> list[str]:
    out = []
    if f.get("employer_name"):
        out.append(f"{f['employer_name']}.")
    months, wage = f.get("months_unpaid"), f.get("monthly_wage")
    if months and wage:
        out.append(f"{number_to_words(int(months), 'en')} months of salary not paid,")
        out.append(f"{inr_to_words(_int(wage), 'en')} a month.")
    elif wage:
        out.append(f"Salary {inr_to_words(_int(wage), 'en')} a month.")
    for d in f.get("deductions") or []:
        out.append(f"{inr_to_words(_int(d['amount']), 'en')} cut from pay.")
    if said_total:
        out.append(f"Total {inr_to_words(said_total, 'en')}.")
    if legal_total is not None and legal_total != said_total:
        out.append(f"Under the law you can ask for {inr_to_words(legal_total, 'en')}.")
    out.append("Is that right?")
    return out


def said_total(facts: dict[str, Any]) -> int:
    """What she said adds up to (before the legal check): months x wage + cuts + lumps - advance."""
    wage = facts.get("monthly_wage") or 0
    months = facts.get("months_unpaid") or 0
    total = wage * months
    total += sum(d.get("amount") or 0 for d in facts.get("deductions") or [])
    total += sum(facts.get("owed_lumps") or [])
    total -= facts.get("advance_outstanding") or 0
    if not total and facts.get("stated_total"):
        total = facts["stated_total"]
    return max(0, _int(total))


def build_readback(facts: dict[str, Any], lang: str = "te-IN", legal_total: float | None = None) -> dict[str, Any]:
    """-> {text (with tags), plain (tags removed), lang, sentences}."""
    lang = lang if lang in LANGS else "te-IN"
    total = said_total(facts)
    legal = _int(legal_total) if legal_total is not None else None
    builder = {"te-IN": _parts_te, "hi-en": _parts_hinglish, "hi-IN": _parts_hi, "en-IN": _parts_en}[lang]
    parts = [p for p in builder(facts, total, legal) if p]
    text = "<slow> " + " <pauses> ".join(parts)
    return {"text": text, "plain": " ".join(parts), "lang": lang, "sentences": parts, "said_total": total,
            "legal_total": legal}


__all__ = ["build_readback", "said_total"]
