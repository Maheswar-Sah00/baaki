"""Share to Baaki + Promise Keeper: pure logic (no I/O). Used by routes/inbox.py.

- detect_lang():      which language the employer used (script of the transcript, Prisma's tag, Telugu-roman words)
- extract_promises(): amount (app.lang.extract_amounts) + date (app.lang.extract_dates, relative to the day it was
                      said: "agle hafte", "1 tareekh ko", "vacche vaaram", "shanivaar ko"). No LLM anywhere here.
- summary / speech:   "Sharma ji said on 9 Nov: will pay ₹12,000 by 14 Nov" in the worker's language, plus the
                      read-back sentence that Timbre speaks so she can confirm the date.
- reminder():         polite template in the EMPLOYER's language that quotes their own words back. Amounts in the
                      reminder are re-extracted and must equal the quote's amounts + the promised amount.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Any, Optional

from .lang import extract_amounts, extract_dates
from .messages import amounts_in, fmt_date, fmt_money, money_words, name_in, norm_lang, parse_lang

# ------------------------------------------------------------------ language
_TE_ROMAN = {"vaaram", "varam", "istanu", "isthanu", "istha", "ista", "pampistanu", "pampista", "garu", "ledu",
             "nela", "nelalo", "vacche", "vache", "taruvata", "tarvata", "ivvali", "icchesta", "ichestanu",
             "ippudu", "konchem", "kashtam", "jeetham", "rendu", "moodu", "veyyi", "velu", "chesta", "cheptha"}
_HI_ROMAN = {"hafte", "hafta", "dungi", "dunga", "doonga", "doongi", "abhi", "agle", "mahine", "tareekh", "tarikh",
             "bhej", "baaki", "hai", "hoon", "kar", "ko", "bolo", "thoda", "paise", "rupaye", "hazaar"}


def script_counts(text: str) -> Counter:
    c: Counter = Counter()
    for ch in text or "":
        o = ord(ch)
        if 0x0C00 <= o <= 0x0C7F:
            c["te"] += 1
        elif 0x0900 <= o <= 0x097F:
            c["deva"] += 1
        elif ch.isascii() and ch.isalpha():
            c["latin"] += 1
    return c


def detect_lang(text: str, detected_code: Optional[str] = None, fallback: str = "hi-en") -> str:
    """hi-en | te-IN | en for the employer's words."""
    c = script_counts(text)
    if c["te"] and c["te"] >= c["deva"]:
        return "te-IN"
    if c["deva"]:
        return "hi-en"
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    te, hi = len(words & _TE_ROMAN), len(words & _HI_ROMAN)
    if te > hi:
        return "te-IN"
    if hi:
        return "hi-en"
    if detected_code:
        d = detected_code.lower()
        if d.startswith("te"):
            return "te-IN"
        if d.startswith("hi"):
            return "hi-en"
        if d.startswith("en"):
            return "en"
    return norm_lang(fallback)


# ------------------------------------------------------------------ promises
# Clause ends: , . ; । ! ? newline (not a comma or full stop inside a number such as 12,692 or 615.50).
_CLAUSE = re.compile(r"(?<!\d)[,.]|[,.](?!\d)|[;।!?\n]")
_REST = ("baaki", "baki", "बाकी", "बाक़ी", "मिगता", "migatha", "migata", "migilina", "మిగతా", "మిగతాది", "మిగిలిన",
         "the rest", "remaining", "balance")
_NOW = ("abhi", "abi", "अभी", "ippudu", "ipudu", "ఇప్పుడు", "right now")
_PROMISE_VERBS = ("dunga", "dungi", "doonga", "doongi", "dedunga", "dedungi", "bhej", "karunga", "karungi",
                  "kar dunga", "kar dungi", "de denge", "denge", "istanu", "isthanu", "istha", "ista ", "pampistanu",
                  "pampista", "ichestanu", "icchestanu", "will pay", "will give", "will send", "will transfer",
                  "दूंगा", "दूँगा", "दूंगी", "दूँगी", "दूगा", "दूगी", "देंगे", "दे दे", "भेज", "करूंगा", "करूँगा", "करूंगी",
                  "करूँगी", "ఇస్తాను", "ఇస్తా", "పంపిస్తాను", "పంపిస్తా", "ఇచ్చేస్తాను", "ఇచ్చేస్తా", "చెల్లిస్తాను",
                  "వేస్తాను", "ఇస్తాం", "ఇస్తాము")


def _clauses(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _CLAUSE.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _has(text: str, words) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def extract_promises(text: str, lang: str, said_on: dt.date) -> list[dict[str, Any]]:
    """Every future date in the reply becomes a promise; the amount comes from the same clause.

    "मैं शनिवार को बारह हज़ार रुपये दे दूँगा, बाकी अगले महीने" -> [₹12,000 by Sat 14 Nov, the rest by 31 Dec].
    "abhi 5,000 bhej raha hoon, baaki 1 tareekh ko" -> [the rest by 1 Dec] (₹5,000 is "now", not a promise).
    "agle hafte 12,692 de dungi" -> [₹12,692 by Sun 22 Nov (week of 16-22 Nov)].
    """
    text = (text or "").strip()
    if not text:
        return []
    hint = parse_lang(lang)
    dates = [d for d in extract_dates(text, hint, today=said_on) if d["iso"] >= said_on.isoformat()]
    if not dates:
        return []
    amounts = extract_amounts(text, hint)
    clauses = _clauses(text)

    def clause_of(pos: int) -> tuple[int, int]:
        for a, b in clauses:
            if a <= pos < b or (pos == b):
                return a, b
        return 0, len(text)

    used: set[int] = set()
    out: list[dict[str, Any]] = []
    for d in sorted(dates, key=lambda d: d["start"]):
        a, b = clause_of(d["start"])
        clause = text[a:b].strip()
        in_clause = [i for i, x in enumerate(amounts) if a <= x["start"] < b and i not in used]
        amount, is_rest = None, _has(clause, _REST)
        if in_clause:
            i = in_clause[0]
            used.add(i)
            amount = float(amounts[i]["amount_inr"])
            is_rest = False
        elif not is_rest and len(amounts) == 1 and 0 not in used and len(dates) == 1:
            ca, cb = clause_of(amounts[0]["start"])
            if not _has(text[ca:cb], _NOW):
                amount = float(amounts[0]["amount_inr"])
                used.add(0)
        conf = 0.5
        if amount is not None:
            conf += 0.2
        if _has(text, _PROMISE_VERBS):
            conf += 0.2
        if d["precision"] == "day":
            conf += 0.05
        out.append({
            "amount": amount, "is_rest": is_rest, "due_date": d["iso"], "range_start": d.get("range_start"),
            "precision": d["precision"], "phrase": d["source_text"], "quote": clause,
            "confidence": round(min(conf, 0.95), 2),
        })
    out.sort(key=lambda p: p["due_date"])
    return out


# ------------------------------------------------------------------ status
def effective_status(stored: str, due_date: str, as_of: dt.date, auto_kept: bool = False) -> str:
    """pending | passed | kept | broken. "passed" = the day after the due date, still unpaid."""
    if stored in ("kept", "broken"):
        return stored
    if auto_kept:
        return "kept"
    try:
        due = dt.date.fromisoformat(due_date[:10])
    except ValueError:
        return "pending"
    return "passed" if as_of > due else "pending"


# ------------------------------------------------------------------ worker-language text
SUMMARY = {
    "en": {"amount": "{employer} said on {said}: will pay {amount} by {due}.",
           "rest": "{employer} said on {said}: will pay the rest by {due}.",
           "date": "{employer} said on {said}: will pay by {due}.",
           "none": "{employer} replied on {said}."},
    "te-IN": {"amount": "{employer} {said} న చెప్పారు: {due} లోపు {amount} ఇస్తామని.",
              "rest": "{employer} {said} న చెప్పారు: మిగతాది {due} లోపు ఇస్తామని.",
              "date": "{employer} {said} న చెప్పారు: {due} లోపు ఇస్తామని.",
              "none": "{employer} {said} న సమాధానం ఇచ్చారు."},
    "hi-en": {"amount": "{employer} ने {said} को कहा: {due} तक {amount} देंगे।",
              "rest": "{employer} ने {said} को कहा: बाकी {due} तक देंगे।",
              "date": "{employer} ने {said} को कहा: {due} तक देंगे।",
              "none": "{employer} ने {said} को जवाब दिया।"},
}
READBACK = {
    "en": {"amount": "Promise: {amount}, by {due}.", "rest": "Promise: the rest by {due}.", "date": "Promise: by {due}.",
           "check": "Is this date right? Please check on the screen."},
    "te-IN": {"amount": "మాట: {amount}, {due} లోపు.", "rest": "మాట: మిగతాది {due} లోపు.", "date": "మాట: {due} లోపు.",
              "check": "ఈ తేదీ సరైనదేనా? స్క్రీన్ మీద చూడండి."},
    "hi-en": {"amount": "वादा: {amount}, {due} तक।", "rest": "वादा: बाकी, {due} तक।", "date": "वादा: {due} तक।",
              "check": "क्या यह तारीख़ सही है? screen पर देख लीजिए।"},
}


def _kind(p: dict[str, Any] | None) -> str:
    if not p:
        return "none"
    if p.get("amount") is not None:
        return "amount"
    return "rest" if p.get("is_rest") else "date"


def summary(employer: str, said_on: str, promise: dict[str, Any] | None, lang: str) -> str:
    lang = norm_lang(lang)
    k = _kind(promise)
    return SUMMARY[lang][k].format(
        employer=name_in(employer, lang), said=fmt_date(said_on, lang, year=False),
        amount=fmt_money(promise["amount"]) if promise and promise.get("amount") is not None else "",
        due=fmt_date(promise["due_date"], lang, year=False) if promise else "")


def readback_speech(promises: list[dict[str, Any]], lang: str) -> list[str]:
    """Spoken after the translation: the promise (amount in words) and a request to check the date."""
    lang = norm_lang(lang)
    out = []
    for p in promises[:2]:
        k = _kind(p)
        amt = money_words(p["amount"], lang) if p.get("amount") is not None else ""
        out.append(READBACK[lang][k].format(amount=amt, due=fmt_date(p["due_date"], lang, year=False)))
    if out:
        out.append(READBACK[lang]["check"])
    return out


def evidence_text(employer: str, said_on: str, source: str, transcript: str, promises: list[dict[str, Any]]) -> str:
    """The diary-chain entry (English, so the legal-pack annex reads it; key facts first: the annex cuts at 140)."""
    how = "WhatsApp voice note" if source == "audio" else "WhatsApp message"
    head = f"Employer reply ({how}), {employer}, said {fmt_date(said_on, 'en')}."
    parts = []
    for p in promises:
        what = fmt_money(p["amount"]) if p.get("amount") is not None else ("the rest" if p.get("is_rest") else "payment")
        parts.append(f"{what} by {fmt_date(p['due_date'], 'en')}")
    prom = f" Promise: {'; '.join(parts)}." if parts else ""
    return f"{head}{prom} Words: “{transcript}”"


# ------------------------------------------------------------------ reminder (employer's language)
REMINDER = {
    "hi-en": {
        "amount": "नमस्ते {employer}, {worker} की तरफ़ से एक छोटी सी याद। {said} को आपने कहा था: “{quote}”। "
                  "आपने {due} तक {amount} देने की बात कही थी। जब सुविधा हो, भेज दीजिए। धन्यवाद।",
        "rest": "नमस्ते {employer}, {worker} की तरफ़ से एक छोटी सी याद। {said} को आपने कहा था: “{quote}”। "
                "आपने बाकी पैसे {due} तक देने की बात कही थी। जब सुविधा हो, भेज दीजिए। धन्यवाद।",
        "date": "नमस्ते {employer}, {worker} की तरफ़ से एक छोटी सी याद। {said} को आपने कहा था: “{quote}”। "
                "आपने {due} तक देने की बात कही थी। जब सुविधा हो, भेज दीजिए। धन्यवाद।",
        "footer": "(Baaki app से)",
    },
    "te-IN": {
        "amount": "నమస్కారం {employer}, {worker} తరఫున ఒక చిన్న గుర్తు. {said} న మీరు ఇలా అన్నారు: “{quote}”. "
                  "{due} లోపు {amount} ఇస్తామని చెప్పారు. వీలైనప్పుడు పంపించండి. ధన్యవాదాలు.",
        "rest": "నమస్కారం {employer}, {worker} తరఫున ఒక చిన్న గుర్తు. {said} న మీరు ఇలా అన్నారు: “{quote}”. "
                "మిగతా డబ్బులు {due} లోపు ఇస్తామని చెప్పారు. వీలైనప్పుడు పంపించండి. ధన్యవాదాలు.",
        "date": "నమస్కారం {employer}, {worker} తరఫున ఒక చిన్న గుర్తు. {said} న మీరు ఇలా అన్నారు: “{quote}”. "
                "{due} లోపు ఇస్తామని చెప్పారు. వీలైనప్పుడు పంపించండి. ధన్యవాదాలు.",
        "footer": "(Baaki యాప్ నుండి)",
    },
    "en": {
        "amount": "Hello {employer}, a small reminder from {worker}. On {said} you said: “{quote}”. "
                  "You mentioned paying {amount} by {due}. Please send it when you can. Thank you.",
        "rest": "Hello {employer}, a small reminder from {worker}. On {said} you said: “{quote}”. "
                "You mentioned paying the rest by {due}. Please send it when you can. Thank you.",
        "date": "Hello {employer}, a small reminder from {worker}. On {said} you said: “{quote}”. "
                "You mentioned paying by {due}. Please send it when you can. Thank you.",
        "footer": "(from the Baaki app)",
    },
}
# Words that must never appear in a reminder (quote, don't accuse; no threats in a gentle step).
NEVER = ("broke", "broken", "liar", "jhooth", "झूठ", "police", "पुलिस", "court", "FIR", "తప్పారు", "అబద్ధం")


def reminder(*, employer: str, worker: str, employer_lang: str, worker_lang: str, said_on: str,
             quote: str, quote_lang: str, amount: Optional[float], is_rest: bool, due_date: str) -> dict[str, Any]:
    el, wl = norm_lang(employer_lang), norm_lang(worker_lang)
    p = {"amount": amount, "is_rest": is_rest, "due_date": due_date}
    k = _kind(p)

    def render(lang: str) -> str:
        return REMINDER[lang][k].format(
            employer=name_in(employer, lang), worker=name_in(worker, lang), said=fmt_date(said_on, lang, year=False),
            quote=quote, amount=fmt_money(amount) if amount is not None else "", due=fmt_date(due_date, lang, year=False))

    text, text_w = render(el), render(wl)
    # Verification: every rupee figure in the reminder is either in her employer's own quote or the promised amount.
    expected = sorted([int(round(a["amount_inr"])) for a in extract_amounts(quote, parse_lang(quote_lang))] +
                      ([int(round(amount))] if amount is not None else []))
    got = sorted(int(round(a)) for a in amounts_in(text, el))
    checks = {"amounts_expected": expected, "amounts_found": got, "amounts_ok": got == expected,
              "no_accusation": not any(w.lower() in text.lower() for w in NEVER)}
    share = f"{text}\n{REMINDER[el]['footer']}"
    return {"text": text, "language": el, "text_worker_lang": text_w, "worker_language": wl,
            "share_text": share, "source": "template", "checks": checks}
