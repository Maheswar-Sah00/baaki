"""Read-back text for Timbre: what she said, slowly, with pauses, amounts written as words.

Feasibility test 2: `<pauses>` gives a 0.7-1.0 s gap in te-IN and hi-en and is never spoken; `<slow>` at most
slightly slows speech. Test 3: write amounts as words (they come from the deterministic formatter, so the
read-back says exactly what the screen shows). For a Latin-only Hinglish sentence, words like
"chaar hazaar rupaye" are read correctly; digits would be read as English.

The total she said comes from app.calc_inputs.said_tally, the same function the Baaki Meter and the case use, so
the three never disagree. Months are named ("August, September aur October"), the current month is flagged as
not yet due (s.17), money already paid is read back, and an unclear month count is asked about. When Baaki's
calculation differs (a cut checked under s.18 to s.20), it is said as "Baaki's calculation", never as what the
law gives her, and never as zero.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from . import calc_inputs, wages
from .lang.numbers import inr_to_words, number_to_words

LANGS = ("te-IN", "hi-en", "hi-IN", "en-IN")
MONTH_WORDS = {
    "te-IN": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్",
              "డిసెంబర్"],
    "hi-IN": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "hi-en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"],
    "en-IN": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"],
}
WORDS_LANG = {"te-IN": "te", "hi-en": "hinglish", "hi-IN": "hi", "en-IN": "en"}
AND = {"te-IN": ",", "hi-en": "aur", "hi-IN": "और", "en-IN": "and"}
HALF = {"hi-en": {0.5: "aadha", 1.5: "dedh", 2.5: "dhai"}, "hi-IN": {0.5: "आधा", 1.5: "डेढ़", 2.5: "ढाई"}}
SAADHE = {"hi-en": "saadhe", "hi-IN": "साढ़े"}
MORE_THAN = {"hi-en": "{n} se zyada", "hi-IN": "{n} से ज़्यादा", "te-IN": "{n} కంటే ఎక్కువ", "en-IN": "more than {n}"}


def _int(x: float | int | None) -> int:
    return int(round(float(x or 0)))


def _money(x: float, lang: str) -> str:
    return inr_to_words(_int(x), WORDS_LANG[lang])


def _num(n: int, lang: str) -> str:
    return number_to_words(int(n), WORDS_LANG[lang])


def _month(m: str, lang: str) -> str:
    return MONTH_WORDS[lang][int(m[5:7]) - 1]


def _list(names: list[str], lang: str) -> str:
    if len(names) <= 1:
        return "".join(names)
    if lang == "te-IN":
        return ", ".join(names)
    return ", ".join(names[:-1]) + f" {AND[lang]} " + names[-1]


def months_phrase(months: list[str], lang: str) -> str:
    """'August, September aur October' (up to six months), else 'from June to November'."""
    if not months:
        return ""
    if len(months) <= 6:
        return _list([_month(m, lang) for m in months], lang)
    a, b = _month(months[0], lang), _month(months[-1], lang)
    return {"te-IN": f"{a} నుండి {b} వరకు", "hi-en": f"{a} se {b} tak", "hi-IN": f"{a} से {b} तक",
            "en-IN": f"from {a} to {b}"}[lang]


def count_words(x: float, lang: str) -> str:
    """3 -> 'teen'; 2.5 -> 'dhai' / 'రెండున్నర' / 'two and a half'. A fraction is never dropped."""
    whole, frac = int(x), round(float(x) - int(x), 2)
    if not frac:
        return "ఒక" if (lang == "te-IN" and whole == 1) else _num(whole, lang)
    if frac != 0.5:
        return MORE_THAN[lang].format(n=_num(whole, lang))
    if lang in HALF:
        return HALF[lang].get(float(x)) or f"{SAADHE[lang]} {_num(whole, lang)}"
    if lang == "te-IN":
        return "అర" if whole == 0 else f"{_num(whole, lang)}న్నర"
    return "half a" if whole == 0 else f"{_num(whole, lang)} and a half"


def _due_words(m: str, lang: str, facts: dict[str, Any]) -> str:
    due = wages.normal_due_date(m)
    if facts.get("dismissed_on"):
        due = min(due, wages.add_working_days(dt.date.fromisoformat(str(facts["dismissed_on"])[:10]), 2))
    mon = MONTH_WORDS[lang][due.month - 1]
    day = _num(due.day, lang)
    return f"{mon} {day}" if lang == "te-IN" else f"{day} {mon}"


def _calc_basis(facts: dict[str, Any]) -> int | None:
    """Which section explains the difference: s.20 (absence cut in proportion), s.18 (other cuts)."""
    cuts = facts.get("deductions") or []
    if any((d.get("reason") or "").lower() in wages.ABSENCE_REASONS for d in cuts):
        return 20
    if cuts:
        return 18
    return None


def _view(f: dict[str, Any], today: dt.date | None) -> dict[str, Any]:
    inp = calc_inputs.facts_to_calc_inputs(f, today)
    mv = inp["months"]
    return {"inp": inp, "months": mv["counted"], "count": mv["count"], "not_yet_due": mv["not_yet_due"],
            "ppm": float(f.get("paid_per_month") or 0), "lumps": [float(x) for x in f.get("paid_lumps") or [] if x],
            "unclear": bool(f.get("months_unclear")) and not mv["counted"]}


# --------------------------------------------------------------------------- per-language sentences
def _parts_te(f: dict[str, Any], said: int, legal: int | None, v: dict[str, Any], lang: str = "te-IN") -> list[str]:
    out = []
    name = f.get("employer_name")
    if name:
        out.append(f"{name} దగ్గర.")
    wage = f.get("monthly_wage")
    if v["count"] and wage:
        head = f"{months_phrase(v['months'], lang)}, " if v["months"] else ""
        if v["ppm"]:
            out.append(f"{head}{count_words(v['count'], lang)} నెలలుగా జీతం నెలకు {_money(wage, lang)},")
            out.append(f"కానీ నెలకు {_money(v['ppm'], lang)} మాత్రమే ఇస్తున్నారు.")
        else:
            out.append(f"{head}{count_words(v['count'], lang)} {'నెల' if v['count'] == 1 else 'నెలల'} జీతం రాలేదు,")
            out.append(f"నెలకు {_money(wage, lang)}.")
    elif wage:
        out.append(f"నెలకు జీతం {_money(wage, lang)}.")
    for m in v["not_yet_due"]:
        out.append(f"{_month(m, lang)} జీతం గడువు ఇంకా రాలేదు, {_due_words(m, lang, f)} లోపు ఇవ్వాలి.")
    if v["unclear"]:
        out.append("ఎన్ని నెలల జీతం రాలేదు? చెప్పండి.")
    if f.get("hours_per_day"):
        out.append(f"రోజుకు {_num(_int(f['hours_per_day']), lang)} గంటల పని.")
    for d in f.get("deductions") or []:
        days = f" {_num(_int(d['days_absent']), lang)} రోజులకు" if d.get("days_absent") else ""
        out.append(f"{days} {_money(d['amount'], lang)} కట్ చేశారు.".strip())
    for x in v["lumps"]:
        out.append(f"{_money(x, lang)} అందింది.")
    if f.get("advance_outstanding"):
        out.append(f"అడ్వాన్స్ {_money(f['advance_outstanding'], lang)}.")
    if said:
        out.append(f"మొత్తం {inr_to_words(said, 'te')}.")
    if legal and wage and legal != said:
        sec = _calc_basis(f)
        basis = f", కోడ్ ఆన్ వేజెస్ సెక్షన్ {_num(sec, lang)}" if sec else ""
        out.append(f"బాకీ లెక్క{basis}: {inr_to_words(legal, 'te')}.")
    out.append("సరేనా?")
    return out


def _parts_hinglish(f: dict[str, Any], said: int, legal: int | None, v: dict[str, Any],
                    lang: str = "hi-en") -> list[str]:
    out = []
    name = f.get("employer_name")
    if name:
        out.append(f"{name}.")
    wage = f.get("monthly_wage")
    if v["count"] and wage:
        mw = "mahina" if v["count"] <= 1 else "mahine"
        head = f"{months_phrase(v['months'], lang)}, " if v["months"] else ""
        if v["ppm"]:
            out.append(f"{head}{count_words(v['count'], lang)} {mw} se salary {_money(wage, lang)} har mahina,")
            out.append(f"par har mahine sirf {_money(v['ppm'], lang)} milte hain.")
        else:
            out.append(f"{head}{count_words(v['count'], lang)} {mw} ki salary nahi mili,")
            out.append(f"{_money(wage, lang)} har mahina.")
    elif wage:
        out.append(f"Salary {_money(wage, lang)} har mahina.")
    for m in v["not_yet_due"]:
        out.append(f"{_month(m, lang)} ki salary abhi due nahi hui, {_due_words(m, lang, f)} tak deni hai.")
    if v["unclear"]:
        out.append("Kitne mahine ki salary baaki hai? Bata dijiye.")
    if f.get("hours_per_day"):
        h = _int(f["hours_per_day"])
        out.append(f"Roz {_num(h, lang)} {'ghanta' if h == 1 else 'ghante'} kaam.")
    for d in f.get("deductions") or []:
        days = f"{_num(_int(d['days_absent']), lang)} din ke liye " if d.get("days_absent") else ""
        out.append(f"{days}{_money(d['amount'], lang)} kaate gaye.")
    for x in v["lumps"]:
        out.append(f"{_money(x, lang)} mil chuke hain.")
    if f.get("advance_outstanding"):
        out.append(f"Advance {_money(f['advance_outstanding'], lang)}.")
    if said:
        out.append(f"Kul {inr_to_words(said, 'hinglish')}.")
    if legal and wage and legal != said:
        sec = _calc_basis(f)
        basis = f", Code on Wages section {_num(sec, lang)}" if sec else ""
        out.append(f"Baaki ka hisaab{basis}: {inr_to_words(legal, 'hinglish')}.")
    out.append("Sahi hai?")
    return out


def _parts_hi(f: dict[str, Any], said: int, legal: int | None, v: dict[str, Any], lang: str = "hi-IN") -> list[str]:
    out = []
    if f.get("employer_name"):
        out.append(f"{f['employer_name']}।")
    wage = f.get("monthly_wage")
    if v["count"] and wage:
        head = f"{months_phrase(v['months'], lang)}, " if v["months"] else ""
        if v["ppm"]:
            out.append(f"{head}{count_words(v['count'], lang)} महीने से तनख्वाह हर महीने {_money(wage, lang)},")
            out.append(f"पर हर महीने सिर्फ़ {_money(v['ppm'], lang)} मिलते हैं।")
        else:
            out.append(f"{head}{count_words(v['count'], lang)} महीने की तनख्वाह नहीं मिली,")
            out.append(f"हर महीने {_money(wage, lang)}।")
    elif wage:
        out.append(f"तनख्वाह हर महीने {_money(wage, lang)}।")
    for m in v["not_yet_due"]:
        out.append(f"{_month(m, lang)} की तनख्वाह अभी due नहीं हुई, {_due_words(m, lang, f)} तक देनी है।")
    if v["unclear"]:
        out.append("कितने महीने की तनख्वाह बाकी है? बताइए।")
    for d in f.get("deductions") or []:
        out.append(f"{_money(d['amount'], lang)} काटे गए।")
    for x in v["lumps"]:
        out.append(f"{_money(x, lang)} मिल चुके हैं।")
    if said:
        out.append(f"कुल {inr_to_words(said, 'hi')}।")
    if legal and wage and legal != said:
        sec = _calc_basis(f)
        basis = f", Code on Wages धारा {_num(sec, lang)}" if sec else ""
        out.append(f"Baaki का हिसाब{basis}: {inr_to_words(legal, 'hi')}।")
    out.append("सही है?")
    return out


def _parts_en(f: dict[str, Any], said: int, legal: int | None, v: dict[str, Any], lang: str = "en-IN") -> list[str]:
    out = []
    if f.get("employer_name"):
        out.append(f"{f['employer_name']}.")
    wage = f.get("monthly_wage")
    if v["count"] and wage:
        head = f"{months_phrase(v['months'], lang)}: " if v["months"] else ""
        unit = "month" if v["count"] == 1 else "months"
        if v["ppm"]:
            out.append(f"{head}for {count_words(v['count'], lang)} {unit} the salary was {_money(wage, lang)} a month,")
            out.append(f"but only {_money(v['ppm'], lang)} is paid each month.")
        else:
            out.append(f"{head}{count_words(v['count'], lang)} {unit} of salary not paid,")
            out.append(f"{_money(wage, lang)} a month.")
    elif wage:
        out.append(f"Salary {_money(wage, lang)} a month.")
    for m in v["not_yet_due"]:
        out.append(f"{_month(m, lang)} wages are not due yet: they are due by {_due_words(m, lang, f)}.")
    if v["unclear"]:
        out.append("For how many months is the salary unpaid? Please say.")
    for d in f.get("deductions") or []:
        out.append(f"{_money(d['amount'], lang)} cut from pay.")
    for x in v["lumps"]:
        out.append(f"{_money(x, lang)} already received.")
    if said:
        out.append(f"Total {inr_to_words(said, 'en')}.")
    if legal and wage and legal != said:
        sec = _calc_basis(f)
        basis = f", Code on Wages section {_num(sec, lang)}" if sec else ""
        out.append(f"Baaki's calculation{basis}: {inr_to_words(legal, 'en')}.")
    out.append("Is that right?")
    return out


def said_total(facts: dict[str, Any], today: dt.date | None = None) -> int:
    """What she said adds up to (before the legal check), from the same conversion as the case and the meter:
    owed months (only the gap for part-paid ones) + cuts + lumps owed - money received - advance."""
    return max(0, _int(calc_inputs.said_tally(facts, today)["total"]))


def build_readback(facts: dict[str, Any], lang: str = "te-IN", legal_total: float | None = None,
                   today: dt.date | None = None) -> dict[str, Any]:
    """-> {text (with tags), plain (tags removed), lang, sentences, said_total, legal_total, months, asks}.
    The calculation line is dropped when there is no wage or Baaki's figure is zero."""
    lang = lang if lang in LANGS else "te-IN"
    v = _view(facts, today)
    total = max(0, _int(calc_inputs.said_tally(facts, today, inputs=v["inp"])["total"]))
    legal = _int(legal_total) if legal_total is not None else None
    builder = {"te-IN": _parts_te, "hi-en": _parts_hinglish, "hi-IN": _parts_hi, "en-IN": _parts_en}[lang]
    parts = []
    for p in builder(facts, total, legal, v):
        if p and p[:1].isascii() and (not parts or parts[-1][-1:] in ".?!"):
            p = p[:1].upper() + p[1:]  # a new sentence starts with a capital; a continuation after "," does not
        if p:
            parts.append(p)
    text = "<slow> " + " <pauses> ".join(parts)
    return {"text": text, "plain": " ".join(parts), "lang": lang, "sentences": parts, "said_total": total,
            "legal_total": legal, "months": v["months"], "not_yet_due": v["not_yet_due"],
            "asks": ["months"] if v["unclear"] else []}


__all__ = ["build_readback", "said_total", "months_phrase", "count_words"]
