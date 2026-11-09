"""V09 Hisaab Milao: turning the employer's words into a proposed correction, and the texts around it.

Every rupee figure and month comes from the deterministic parsers in app.lang (or the employer's typed number),
never from an LLM. The correction is only a proposal "said by the employer": Baaki verifies nothing, and under
the Code on Wages the employer has to prove payment (s.59). The worker decides; nothing is auto-accepted.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Optional

from .lang import extract_amounts, extract_dates, today_ist
from .messages import MONTHS, fmt_money, money_words, month_name, name_in, norm_lang, parse_lang

KINDS = ("cash", "upi", "advance", "other")
# Payment.method for each kind (Payment allows upi | cash | bank | other)
METHOD_OF = {"cash": "cash", "upi": "upi", "advance": "other", "other": "other"}
KIND_EN = {"cash": "cash", "upi": "UPI", "advance": "advance", "other": "payment", "bank": "bank transfer",
           "said_paid": "payment"}

_KIND_WORDS: dict[str, list[str]] = {
    "advance": ["advance", "advanced", "एडवांस", "एडवान्स", "अग्रिम", "అడ్వాన్స్", "అడ్వాన్సు", "udhaar", "udhar",
                "उधार"],
    "upi": ["upi", "gpay", "g pay", "google pay", "phonepe", "phone pe", "paytm", "online", "transfer",
            "transferred", "bank", "account", "यूपीआई", "यूपीआइ", "गूगल पे", "फोनपे", "फ़ोनपे", "पेटीएम", "ऑनलाइन",
            "ट्रांसफर", "बैंक", "అకౌంట్", "యూపీఐ", "ఆన్‌లైన్", "ఆన్లైన్", "ఫోన్ పే", "గూగుల్ పే", "బ్యాంక్"],
    "cash": ["cash", "kash", "naqad", "nakad", "nagad", "haath mein", "hath me", "कैश", "केश", "नकद", "नक़द",
             "हाथ में", "క్యాష్", "నగదు", "చేతికి"],
}
_LAST_MONTH = re.compile(r"(pichh?le|pichhla|pichla|picchle)\s+mah[ie]+ne|last\s+month|पिछले\s+महीने|पिछला\s+महीना|"
                         r"गए\s+महीने|పోయిన\s+నెల|గత\s+నెల", re.IGNORECASE)
_THIS_MONTH = re.compile(r"(is|iss)\s+mah[ie]+ne|this\s+month|इस\s+महीने|ఈ\s+నెల", re.IGNORECASE)
_BARE_NUM = re.compile(r"(?<![\d.,])(\d{2,3}(?:,\d{2,3})*,\d{3}|\d{3,6})(?![\d.,]*\d)")


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def detect_kind(text: str, label_hint: Optional[str] = None) -> str:
    """cash | upi | advance | other, from fixed word lists (advance wins: it changes what the money was)."""
    if label_hint == "advance":
        return "advance"
    low = " " + _norm_text(text).lower() + " "
    for kind in ("advance", "upi", "cash"):
        for w in _KIND_WORDS[kind]:
            if w.isascii():
                if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                    return kind
            elif w in low:
                return kind
    return "other"


def _prev_month(today: dt.date, k: int = 1) -> str:
    y, m = today.year, today.month - k
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def resolve_month(text: str, lang_hint: str, today: dt.date | None = None) -> tuple[Optional[str], Optional[str]]:
    """The month a past payment was made in -> ("2026-10", "October"), or (None, None).

    app.lang.dates resolves a bare month name forward (it was built for deadlines), so a named month that lands
    in the future is moved back a year: on 10 Nov 2026 "October" means October 2026."""
    today = today or today_ist()
    m = _LAST_MONTH.search(text or "")
    if m:
        return _prev_month(today), m.group(0)
    m = _THIS_MONTH.search(text or "")
    if m:
        return f"{today.year:04d}-{today.month:02d}", m.group(0)
    for d in extract_dates(text or "", lang_hint, today=today):
        if d.get("precision") not in ("month", "day"):
            continue
        try:
            day = dt.date.fromisoformat(d.get("range_start") or d["iso"])
        except (TypeError, ValueError, KeyError):
            continue
        if day > today:
            if (day - today).days <= 31 and d.get("precision") == "day":
                day = today  # "kal" read as tomorrow: the payment is still this month
            while day > today:
                day = day.replace(year=day.year - 1, day=min(day.day, 28))
        return f"{day.year:04d}-{day.month:02d}", d.get("source_text")
    return None, None


def _date_spans(text: str, lang_hint: str, today: dt.date) -> list[tuple[int, int]]:
    return [(d["start"], d["end"]) for d in extract_dates(text, lang_hint, today=today)]


def find_amounts(text: str, lang_hint: str, today: dt.date | None = None) -> list[dict[str, Any]]:
    """Rupee amounts in his words. app.lang.amounts first; it rejects a bare 1900-2100 as a probable year
    ("maine 2000 diye"), and here every number is about money, so a bare 3-6 digit number that is not part of a
    date is re-read through the same parser with a rupee sign in front."""
    today = today or today_ist()
    found = [dict(a, how="parser") for a in extract_amounts(text, lang_hint)]
    if found:
        return found
    spans = _date_spans(text, lang_hint, today)
    out = []
    for m in _BARE_NUM.finditer(text or ""):
        if any(s < m.end() and m.start() < e for s, e in spans):
            continue
        again = extract_amounts("₹" + m.group(1), lang_hint)
        if again:
            out.append({"amount_inr": again[0]["amount_inr"], "start": m.start(), "end": m.end(),
                        "source_text": m.group(1), "label_hint": None, "how": "parser_rupee"})
    return out


def parse_correction(text: str, employer_lang: str, today: dt.date | None = None) -> dict[str, Any]:
    """{amount, amount_text, candidates, month, month_text, kind} from his words. amount is None if none heard."""
    text = _norm_text(text)
    hint = parse_lang(employer_lang)
    today = today or today_ist()
    amts = find_amounts(text, hint, today)
    first = amts[0] if amts else None
    month, month_text = resolve_month(text, hint, today)
    return {
        "amount": float(first["amount_inr"]) if first else None,
        "amount_text": first["source_text"] if first else None,
        "candidates": [{"amount": float(a["amount_inr"]), "text": a["source_text"]} for a in amts],
        "multiple": len(amts) > 1,
        "month": month,
        "month_text": month_text,
        "kind": detect_kind(text, first.get("label_hint") if first else None),
    }


def parse_typed_amount(raw: str | float | None) -> Optional[float]:
    """The employer's typed number ("2000", "₹2,000", "do hazaar") through the same parser."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        v = float(s.replace(",", "").replace("₹", "").strip())
        return round(v, 2) if v > 0 else None
    except ValueError:
        pass
    a = extract_amounts(s if s.startswith("₹") else s, "hinglish") or extract_amounts("₹" + s, "hinglish")
    return float(a[0]["amount_inr"]) if a else None


def valid_month(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})", raw.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError("month must look like 2026-10")
    return raw.strip()


# --------------------------------------------------------------------------- texts
def _female(name: str) -> bool:
    return bool(re.search(r"\b(madam|aunty|auntie|didi|bhabhi|amma|ben|behen|ma'am|mam)\b", (name or "").lower()))


_TE_KIND = {"cash": "క్యాష్ ", "upi": "యూపీఐ లో ", "advance": "అడ్వాన్స్ గా ", "other": ""}
_HI_KIND = {"cash": "कैश ", "upi": "यूपीआई से ", "advance": "एडवांस में ", "other": ""}
_EN_KIND = {"cash": " in cash", "upi": " by UPI", "advance": " as an advance", "other": ""}


def readback(employer_name: str, amount: float, kind: str, month: Optional[str], worker_lang: str) -> dict[str, str]:
    """What she hears and reads, in her language: "Sharma garu antunnaru: October lo rendu vela cash ichcharu.
    Nijamena?" The amount is written as words for Timbre (from app.lang), with <slow> on it."""
    wl = norm_lang(worker_lang)
    who = name_in(employer_name, wl)
    if wl == "te-IN":
        mpart = f"{MONTHS['te-IN'][int(month[5:7]) - 1]} లో " if month else ""
        tpl = "{who} అంటున్నారు: {m}{amt} {k}ఇచ్చారు. నిజమేనా?"
        display = tpl.format(who=who, m=mpart, amt=fmt_money(amount), k=_TE_KIND[kind])
        speech = (f"{who} అంటున్నారు: {mpart}<slow> {money_words(amount, wl)} {_TE_KIND[kind]}ఇచ్చారు. "
                  f"<pauses> నిజమేనా?")
    elif wl == "hi-en":
        mpart = f"{MONTHS['hi-en'][int(month[5:7]) - 1]} में " if month else ""
        verb = "कह रही हैं" if _female(employer_name) else "कह रहे हैं"
        display = f"{who} {verb}: {mpart}{fmt_money(amount)} {_HI_KIND[kind]}दिए थे। क्या यह सही है?"
        speech = (f"{who} {verb}: {mpart}<slow> {money_words(amount, wl)} {_HI_KIND[kind]}दिए थे। "
                  f"<pauses> क्या यह सही है?")
    else:
        mpart = f" in {month_name(month, 'en')}" if month else ""
        display = f"{who} says they gave you {fmt_money(amount)}{_EN_KIND[kind]}{mpart}. Is that right?"
        speech = (f"{who} says they gave you <slow> {money_words(amount, wl)}{_EN_KIND[kind]}{mpart}. "
                  f"<pauses> Is that right?")
    return {"text": display, "speech": speech, "language": wl}


def chip(amount: float, kind: str, month: Optional[str], employer_name: str) -> dict[str, str]:
    """"−₹2,000 · cash · October (said by Sharma ji)"."""
    parts = ["−" + fmt_money(amount), KIND_EN[kind]]
    if month:
        parts.append(month_name(month, "en"))
    main = " · ".join(parts)
    return {"text": f"{main} (said by {employer_name})", "main": main, "said_by_label": f"said by {employer_name}"}


STATUS_EMPLOYER = {
    "proposed": {"hi-en": "{worker} के जवाब का इंतज़ार है", "te-IN": "{worker} సమాధానం కోసం ఎదురుచూస్తున్నాం",
                 "en": "Waiting for {worker}"},
    "accepted": {"hi-en": "{worker} ने मान लिया। हिसाब अपडेट हो गया।", "te-IN": "{worker} ఒప్పుకున్నారు. లెక్క మారింది.",
                 "en": "{worker} agreed. The account is updated."},
    "rejected": {"hi-en": "{worker} सहमत नहीं हैं: विवादित। बकाया नहीं बदला।",
                 "te-IN": "{worker} ఒప్పుకోలేదు: వివాదంలో ఉంది. బాకీ మారలేదు.",
                 "en": "{worker} disagrees: disputed. The balance did not change."},
}
STATUS_WORKER = {
    "proposed": {"te-IN": "మీ నిర్ణయం కోసం", "hi-en": "आपके फ़ैसले का इंतज़ार", "en": "Waiting for you"},
    "accepted": {"te-IN": "మీరు ఒప్పుకున్నారు", "hi-en": "आपने माना", "en": "You agreed"},
    "rejected": {"te-IN": "మీరు ఒప్పుకోలేదు (వివాదం)", "hi-en": "आपने नहीं माना (विवादित)",
                 "en": "You disagree (disputed)"},
}
DISPLAY_STATE = {"proposed": "proposed", "accepted": "accepted", "rejected": "disputed"}


def status_text(table: dict, status: str, lang: str, worker_name: str = "") -> str:
    lang = norm_lang(lang)
    return table[status][lang].format(worker=name_in(worker_name, lang))


def payment_note(proposal_id: int, employer_name: str, month: Optional[str]) -> str:
    m = f", {month_name(month, 'en', year=True)}" if month else ""
    return (f"Hisaab Milao #{proposal_id}: said by the employer ({employer_name}{m}), accepted by her. "
            "Recorded on the employer's word; Baaki did not verify it (Code on Wages s.59: the employer proves payment).")


def diary_text(event: str, *, employer_name: str, worker_name: str, amount: float, kind: str,
               month: Optional[str], proposal_id: int) -> str:
    """English diary lines (the legal-pack annex prints them)."""
    what = f"{fmt_money(amount)} ({KIND_EN[kind]}" + (f", {month_name(month, 'en', year=True)}" if month else "") + ")"
    if event == "proposed":
        return f"Hisaab Milao #{proposal_id}: {employer_name} says {what} was paid. Said by the employer; not verified."
    if event == "accepted":
        return f"Hisaab Milao #{proposal_id}: {worker_name} accepted {employer_name}'s word that {what} was paid."
    return (f"Hisaab Milao #{proposal_id}: {worker_name} disputes {employer_name}'s claim that {what} was paid. "
            "No change to the balance.")


NO_AMOUNT = {
    "hi-en": "रकम सुनाई नहीं दी। कृपया रकम टाइप करें।",
    "te-IN": "మొత్తం వినిపించలేదు. దయచేసి మొత్తం టైప్ చేయండి.",
    "en": "Couldn't hear an amount. Please type it.",
}


# --------------------------------------------------------------------------- F2: "I've paid" as a claim
# The employer's tap on "I've paid" is stored as a proposal of kind "said_paid" (+ a HisaabClaim row with the
# method). It records no money. She hears "Sharma ji says he sent ₹13,000 by UPI. Did it reach you?" and confirms
# (accept) or says it did not arrive (reject = disputed). Only her confirmation goes through app.ledger.
CLAIM_KIND = "said_paid"
METHOD_EN = {"upi": "by UPI", "cash": "in cash", "bank": "by bank transfer", "other": ""}
_TE_METHOD = {"upi": "యూపీఐ లో ", "cash": "క్యాష్ ", "bank": "బ్యాంక్ లో ", "other": ""}
_HI_METHOD = {"upi": "यूपीआई से ", "cash": "कैश ", "bank": "बैंक से ", "other": ""}
DEMO_CONFIRMED = "Demo: Lakshmi confirmed (synthetic)"


def claim_readback(employer_name: str, amount: float, method: str, worker_lang: str) -> dict[str, str]:
    """What she hears and reads: "Sharma garu antunnaru: ₹13,000 UPI lo pampincharu. Meeku andaya?" """
    wl = norm_lang(worker_lang)
    who = name_in(employer_name, wl)
    method = method if method in METHOD_EN else "other"
    if wl == "te-IN":
        display = f"{who} అంటున్నారు: {fmt_money(amount)} {_TE_METHOD[method]}పంపించారు. మీకు డబ్బులు అందాయా?"
        speech = (f"{who} అంటున్నారు: <slow> {money_words(amount, wl)} {_TE_METHOD[method]}పంపించారు. "
                  f"<pauses> మీకు డబ్బులు అందాయా?")
    elif wl == "hi-en":
        verb = "कह रही हैं" if _female(employer_name) else "कह रहे हैं"
        display = f"{who} {verb}: {fmt_money(amount)} {_HI_METHOD[method]}भेज दिए हैं। क्या पैसे आपको मिल गए?"
        speech = (f"{who} {verb}: <slow> {money_words(amount, wl)} {_HI_METHOD[method]}भेज दिए हैं। "
                  f"<pauses> क्या पैसे आपको मिल गए?")
    else:
        how = (" " + METHOD_EN[method]) if METHOD_EN[method] else ""
        display = f"{who} says they sent you {fmt_money(amount)}{how}. Did it reach you?"
        speech = f"{who} says they sent you <slow> {money_words(amount, wl)}{how}. <pauses> Did it reach you?"
    return {"text": display, "speech": speech, "language": wl}


def claim_chip(amount: float, method: str, employer_name: str) -> dict[str, str]:
    """"₹13,000 · UPI · said paid by Sharma ji"."""
    main = " · ".join(x for x in ("−" + fmt_money(amount), KIND_EN.get(method, "payment")) if x)
    return {"text": f"{main} (said paid by {employer_name})", "main": main,
            "said_by_label": f"said paid by {employer_name}"}


CLAIM_STATUS_EMPLOYER = {
    "proposed": {"hi-en": "{worker} की पुष्टि का इंतज़ार है। पैसे मिलते ही हिसाब अपडेट होगा।",
                 "te-IN": "{worker} నిర్ధారణ కోసం ఎదురుచూస్తున్నాం. డబ్బులు అందాక లెక్క మారుతుంది.",
                 "en": "Waiting for {worker} to confirm. The account updates once the money reaches her."},
    "accepted": {"hi-en": "{worker} ने पुष्टि की: पैसे मिल गए।", "te-IN": "{worker} డబ్బులు అందాయని నిర్ధారించారు.",
                 "en": "{worker} confirmed the money arrived."},
    "rejected": {"hi-en": "{worker} के मुताबिक पैसे नहीं मिले: विवादित। बकाया नहीं बदला।",
                 "te-IN": "{worker} కి డబ్బులు అందలేదు: వివాదంలో ఉంది. బాకీ మారలేదు.",
                 "en": "{worker} says the money has not arrived: disputed. The balance did not change."},
}
CLAIM_STATUS_WORKER = {
    "proposed": {"te-IN": "డబ్బులు అందాయా?", "hi-en": "क्या पैसे मिले?", "en": "Did the money arrive?"},
    "accepted": {"te-IN": "అందాయని మీరు నిర్ధారించారు", "hi-en": "आपने पुष्टि की: पैसे मिले",
                 "en": "You confirmed it arrived"},
    "rejected": {"te-IN": "అందలేదని చెప్పారు (వివాదం)", "hi-en": "आपने कहा पैसे नहीं मिले (विवादित)",
                 "en": "You said it did not arrive (disputed)"},
}
# What the employer sees right after tapping "I've paid"
CLAIM_SENT = {
    "hi-en": "धन्यवाद। {worker} पैसे मिलने की पुष्टि करेंगी, फिर हिसाब अपडेट होगा।",
    "te-IN": "ధన్యవాదాలు. డబ్బులు అందినట్టు {worker} నిర్ధారిస్తారు, తర్వాత లెక్క మారుతుంది.",
    "en": "Thank you. {worker} will confirm when the money reaches her; then the account updates.",
}


def claim_note(proposal_id: int, employer_name: str, method: str, demo: bool = False) -> str:
    who = "Demo: Lakshmi confirmed (synthetic, no real money)" if demo else "confirmed by her"
    how = (" " + METHOD_EN.get(method, "")) if METHOD_EN.get(method) else ""
    return (f"Payment claim #{proposal_id}: {employer_name} said this was paid{how}; {who}. "
            "Recorded on her confirmation (Code on Wages s.59: the employer proves payment).")


def claim_diary_text(event: str, *, employer_name: str, worker_name: str, amount: float, method: str,
                     proposal_id: int, demo: bool = False) -> str:
    how = f" ({KIND_EN.get(method, 'payment')})"
    if event == "proposed":
        return (f"Payment claim #{proposal_id}: {employer_name} says {fmt_money(amount)}{how} was paid. "
                f"Waiting for {worker_name} to confirm.")
    if event == "accepted":
        tag = " [Demo: confirmed automatically, synthetic]" if demo else ""
        return f"Payment claim #{proposal_id}: {worker_name} confirmed {fmt_money(amount)} from {employer_name} arrived.{tag}"
    return (f"Payment claim #{proposal_id}: {worker_name} says {fmt_money(amount)} from {employer_name} did not "
            "arrive. Disputed; no change to the balance.")
