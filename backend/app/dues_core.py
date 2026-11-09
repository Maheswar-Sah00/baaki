"""Baaki for every promise: pure logic (no I/O, no LLM). Used by routes/dues.py.

- parse_items():   "October doodh 1850, paper 320" / "అక్టోబర్ పాలు 1,850" -> chips with a running total. Amounts come
                   from app.lang.extract_amounts only; the label is the user's own words, recognised as a month and
                   an item (milk, paper, ironing, ...) so the reminder can name it in the other party's language.
- parse_promise(): "agle mahine pehle hafte" / "ఈ వారం చివరికి" / "1 tareekh" -> one due date, resolved from the day it
                   was said (app.lang.extract_dates, plus a "first week of next month" rule the parser lacks).
- promise_status() / counter(): pending | kept | broken as of a date; "made N times, broken M times, first promised
                   <date> (X months ago)".
- reminder():      polite template in the OTHER party's language (te-IN / hi-en / en), per kind. Every rupee figure
                   is filled from data and re-extracted with the parsers; it must equal the expected set. No threats,
                   no legal claims, no penalties or interest, no accusation words.
- chain:           log_hash() / verify_log() for the per-account hash chain (DuesLog).
- pack_blocks():   the record pack (chit / other, after PACK_MIN_BROKEN broken promises): promise log, hashes,
                   amounts, free legal aid. Never claims fraud; carries the not-legal-advice line.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any, Iterable, Optional

from .inbox_logic import detect_lang
from .lang import extract_amounts, extract_dates
from .messages import (DLSA, FORBIDDEN, MONTHS, NALSA, amounts_in, fmt_date, fmt_money, money_words, name_in,
                       norm_lang, parse_lang)

KINDS = ("vendor", "chit", "other")
PACK_MIN_BROKEN = 3
LANGS = ("hi-en", "te-IN", "en")

# Synthetic demo names in each script (stored in Latin). messages.NAME_SCRIPTS covers Reddy garu, Lakshmi, ...
_NAMES: dict[str, dict[str, str]] = {
    "ramu": {"hi-en": "रामू", "te-IN": "రాము"},
    "srinivas agent": {"hi-en": "श्रीनिवास जी", "te-IN": "శ్రీనివాస్ గారు", "en": "Srinivas garu"},
    "srinivas": {"hi-en": "श्रीनिवास जी", "te-IN": "శ్రీనివాస్ గారు", "en": "Srinivas garu"},
}


def name_of(name: str, lang: str) -> str:
    lang = norm_lang(lang)
    key = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", (name or "").lower())).strip()
    if lang == "en":
        return _NAMES.get(key, {}).get("en") or name
    return _NAMES.get(key, {}).get(lang) or name_in(name, lang)


def norm_kind(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    return k if k in KINDS else "other"


def lang_of(text: str, hint: str | None) -> str:
    """hi-en | te-IN | en for a text; 'auto' / None reads the script and Telugu/Hindi roman words."""
    h = (hint or "").strip().lower()
    if h in ("", "auto", "unknown", "indic-auto"):
        return detect_lang(text, None, "hi-en")
    return norm_lang(h)


# ------------------------------------------------------------------ items
_MONTH_WORDS: dict[int, tuple[str, ...]] = {}
_EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
              "november", "december"]
_EXTRA_MONTHS = {9: ("sept", "sitambar", "सितम्बर"), 10: ("oct", "aktubar", "aktoobar", "अक्तूबर"),
                 11: ("nov", "navambar", "नवम्बर"), 12: ("dec", "disambar", "दिसम्बर"), 8: ("aug", "agast"),
                 1: ("jan", "janvari"), 2: ("feb", "farvari"), 6: ("jun",), 7: ("jul", "julai")}
for _i, _en in enumerate(_EN_MONTHS, start=1):
    _MONTH_WORDS[_i] = (_en, MONTHS["hi-en"][_i - 1], MONTHS["te-IN"][_i - 1], *_EXTRA_MONTHS.get(_i, ()))

ITEM_WORDS: dict[str, tuple[str, ...]] = {
    "milk": ("milk", "doodh", "dudh", "paalu", "palu", "పాలు", "दूध"),
    "paper": ("newspaper", "news paper", "paper", "akhbaar", "akhbar", "pathrika", "పేపర్", "పత్రిక", "अखबार",
              "अख़बार", "पेपर"),
    "ironing": ("ironing", "istri", "istree", "press", "dhobi", "iron", "इस्त्री", "प्रेस", "धोबी", "ఇస్త్రీ"),
    "vegetables": ("vegetables", "veggies", "sabzi", "sabji", "kooragayalu", "kuragayalu", "కూరగాయలు", "सब्ज़ी",
                   "सब्जी"),
    "water": ("water can", "water", "paani", "neellu", "నీళ్ళు", "నీళ్లు", "पानी"),
    "chit": ("chit", "chitti", "chitty", "chiti", "cheeti", "చిట్టీ", "చీటీ", "చిట్", "चिट"),
    "loan": ("hand loan", "loan", "udhaar", "udhar", "appu", "అప్పు", "उधार"),
    "savings": ("savings", "bachat", "podupu", "పొదుపు", "बचत"),
}
ITEM_LABEL: dict[str, dict[str, str]] = {
    "milk": {"en": "milk", "hi-en": "दूध", "te-IN": "పాలు"},
    "paper": {"en": "newspaper", "hi-en": "अख़बार", "te-IN": "పేపర్"},
    "ironing": {"en": "ironing", "hi-en": "इस्त्री", "te-IN": "ఇస్త్రీ"},
    "vegetables": {"en": "vegetables", "hi-en": "सब्ज़ी", "te-IN": "కూరగాయలు"},
    "water": {"en": "water cans", "hi-en": "पानी", "te-IN": "నీళ్ల క్యాన్లు"},
    "chit": {"en": "chit money", "hi-en": "चिट के पैसे", "te-IN": "చిట్టీ డబ్బులు"},
    "loan": {"en": "hand loan", "hi-en": "उधार", "te-IN": "అప్పు"},
    "savings": {"en": "savings", "hi-en": "बचत के पैसे", "te-IN": "పొదుపు డబ్బులు"},
}
KIND_DEFAULT_LABEL = {
    "vendor": {"en": "bill", "hi-en": "बिल", "te-IN": "బిల్లు"},
    "chit": {"en": "chit money", "hi-en": "चिट के पैसे", "te-IN": "చిట్టీ డబ్బులు"},
    "other": {"en": "money", "hi-en": "पैसे", "te-IN": "డబ్బులు"},
}
_STOP = {"aur", "and", "or", "ka", "ki", "ke", "ko", "hai", "hain", "baaki", "baki", "rupaye", "rupees", "rs", "inr",
         "the", "for", "of", "bill", "total", "mariyu", "inka", "ivvali", "dena", "dene", "hain", "tha", "the", "se",
         "garu", "ji", "bhai", "का", "की", "के", "और", "है", "बाकी", "रुपये", "మరియు", "బాకీ", "రూపాయలు", "ఇంకా"}
_WORD = re.compile(r"[\wఀ-౿ऀ-ॿ]+", re.UNICODE)


def _has_word(text: str, word: str) -> bool:
    low = text.lower()
    if not word.isascii():
        return word in low
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", low) is not None


def find_month(text: str) -> Optional[int]:
    for m, words in _MONTH_WORDS.items():
        if any(_has_word(text, w) for w in words if len(w) > 2):
            return m
    return None


def find_item(text: str) -> Optional[str]:
    for key, words in ITEM_WORDS.items():
        if any(_has_word(text, w) for w in words):
            return key
    return None


def _clean_label(seg: str, exclude: Iterable[str] = ()) -> str:
    ex = {e.lower() for e in exclude}
    words = [w for w in _WORD.findall(seg) if not w.isdigit() and not re.search(r"\d", w)
             and w.lower() not in _STOP and w.lower() not in ex]
    return " ".join(words[-4:])


def item_label(item_key: Optional[str], month: Optional[int], raw: str, lang: str, kind: str = "vendor",
               oblique: bool = False) -> str:
    """Render an item in a language: "October milk" / "अक्टूबर का दूध" / "అక్టోబర్ పాలు".
    oblique=True gives the Hindi form before "का bill": "अक्टूबर के दूध"."""
    lang = norm_lang(lang)
    mname = MONTHS[lang][month - 1] if month else ""
    ka = "के" if oblique else "का"
    if item_key:
        what = ITEM_LABEL[item_key][lang]
        if not mname:
            return what
        return {"en": f"{mname} {what}", "hi-en": f"{mname} {ka} {what}", "te-IN": f"{mname} {what}"}[lang]
    if mname:
        base = KIND_DEFAULT_LABEL[norm_kind(kind)][lang]
        return {"en": f"{mname} {base}", "hi-en": f"{mname} {ka} {base}", "te-IN": f"{mname} {base}"}[lang]
    return raw or KIND_DEFAULT_LABEL[norm_kind(kind)][lang]


def parse_items(text: str, lang: str | None = None, kind: str = "vendor", party: str = "") -> dict[str, Any]:
    """Amounts (app.lang) -> chips. Each chip's label comes from the words just before its amount (or just after,
    when the amount comes first). A month named once carries to the next chips ("October doodh 1850, paper 320")."""
    text = (text or "").strip()
    lg = lang_of(text, lang)
    amounts = extract_amounts(text, parse_lang(lg)) if text else []
    items: list[dict[str, Any]] = []
    prev_end = 0
    carry_month: Optional[int] = None
    ex = _WORD.findall(party or "")
    for i, a in enumerate(amounts):
        before = text[prev_end:a["start"]]
        nxt = amounts[i + 1]["start"] if i + 1 < len(amounts) else len(text)
        after = text[a["end"]:nxt]
        seg = before if (find_item(before) or find_month(before) or _clean_label(before)) else after
        month = find_month(seg) or (find_month(after) if seg is before else None)
        if month:
            carry_month = month
        else:
            month = carry_month
        key = find_item(seg) or (find_item(after) if not find_item(before) and seg is before else None)
        raw = _clean_label(seg, ex)
        items.append({
            "label": raw or item_label(key, month, "", lg, kind),
            "item_key": key, "month": month, "amount": float(a["amount_inr"]), "source_text": a["source_text"],
            "display": {l: item_label(key, month, raw, l, kind) for l in LANGS},
        })
        prev_end = a["end"]
    total = round(sum(x["amount"] for x in items), 2)
    return {"lang": lg, "items": items, "total": total, "total_display": fmt_money(total)}


# ------------------------------------------------------------------ promises
FIRST_WEEK = ("first week", "1st week", "pehle hafte", "pehla hafta", "pehle week", "first hafte", "starting week",
              "modati vaaram", "modati varam", "modatlo", "మొదటి వారం", "पहले हफ्ते", "पहले हफ़्ते", "पहला हफ्ता",
              "पहला हफ़्ता")
NEXT_MONTH = ("next month", "agle mahine", "agla mahina", "agle month", "vacche nela", "vache nela", "vachhe nela",
              "వచ్చే నెల", "अगले महीने", "अगला महीना")


def _add_month(d: dt.date, n: int = 1) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def parse_promise(text: str, lang: str | None, said_on: dt.date) -> Optional[dict[str, Any]]:
    """One promise per thing said: the due date (relative to `said_on`) and an amount if one was named."""
    text = (text or "").strip()
    if not text:
        return None
    lg = lang_of(text, lang)
    hint = parse_lang(lg)
    low = text.lower()
    amounts = extract_amounts(text, hint)
    amount = float(amounts[0]["amount_inr"]) if amounts else None
    fw = next((w for w in FIRST_WEEK if w in low), None)
    if fw:
        nm = next((w for w in NEXT_MONTH if w in low), None)
        start = _add_month(said_on) if (nm or said_on.day > 7) else said_on.replace(day=1)
        due = start.replace(day=7)
        phrase = f"{nm} {fw}" if nm else fw
        return {"due_date": due.isoformat(), "range_start": start.isoformat(), "precision": "week",
                "phrase": phrase, "quote": text, "lang": lg, "amount": amount}
    dates = [d for d in extract_dates(text, hint, today=said_on) if d["iso"] >= said_on.isoformat()]
    if not dates:
        return None
    d = sorted(dates, key=lambda x: x["start"])[0]
    return {"due_date": d["iso"], "range_start": d.get("range_start"), "precision": d["precision"],
            "phrase": d["source_text"], "quote": text, "lang": lg, "amount": amount}


def months_between(a: dt.date, b: dt.date) -> int:
    n = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        n -= 1
    return max(n, 0)


def _d(x: str) -> dt.date:
    return dt.date.fromisoformat(x[:10])


def promise_status(p: dict[str, Any], as_of: dt.date, items: list[dict[str, Any]]) -> str:
    """pending | kept | broken. Stored kept/broken wins. Otherwise kept = payments between the day it was said and
    the due date cover the promised amount (or clear everything owed by then); broken = the date passed unpaid."""
    if p.get("status") in ("kept", "broken"):
        return p["status"]
    said, due = _d(p["said_on"]), _d(p["due_date"])
    upto = min(due, as_of)
    paid_window = sum(i["amount"] for i in items if i["kind"] == "paid" and said <= _d(i["said_on"]) <= upto)
    owed = sum(i["amount"] for i in items if i["kind"] == "due" and _d(i["said_on"]) <= said)
    paid_before = sum(i["amount"] for i in items if i["kind"] == "paid" and _d(i["said_on"]) < said)
    need = p.get("amount") or max(owed - paid_before, 0)
    if need > 0 and paid_window + 0.5 >= need:
        return "kept"
    return "broken" if as_of > due else "pending"


def counter(promises: list[dict[str, Any]], as_of: dt.date) -> dict[str, Any]:
    made = [p for p in promises if _d(p["said_on"]) <= as_of]
    broken = sum(1 for p in made if p["status"] == "broken")
    kept = sum(1 for p in made if p["status"] == "kept")
    first = min((p["said_on"] for p in made), default=None)
    months = months_between(_d(first), as_of) if first else 0
    days = (as_of - _d(first)).days if first else 0
    text = (f"Promise made {len(made)} time{'s' if len(made) != 1 else ''}, broken {broken} time"
            f"{'s' if broken != 1 else ''}" + (f", first promised {fmt_date(first, 'en')} ({months} months ago)"
                                              if first and months else
                                              (f", first promised {fmt_date(first, 'en')} ({days} days ago)" if first else "")))
    return {"made": len(made), "broken": broken, "kept": kept, "pending": len(made) - broken - kept,
            "first_promised": first, "months_ago": months, "days_ago": days, "text_en": text}


# ------------------------------------------------------------------ reminder (the other party's language)
REMINDER: dict[str, dict[str, dict[str, str]]] = {
    "vendor": {
        "hi-en": {"open": "नमस्ते {party}, {owner} की तरफ़ से एक छोटी सी याद।",
                  "items": "{items} का bill {total} बाकी है।",
                  "items_many": "{items}, कुल {total} बाकी है।",
                  "total": "{what} का {total} बाकी है।",
                  "promise": "आपने {said} को कहा था: “{quote}”।",
                  "close": "जब सुविधा हो, भेज दीजिए। धन्यवाद।",
                  "upi": "UPI से भेजने का link नीचे है।",
                  "footer": "(Baaki app से)"},
        "te-IN": {"open": "నమస్కారం {party}, {owner} తరఫున ఒక చిన్న గుర్తు.",
                  "items": "{items} బిల్లు {total} ఇంకా రావాలి.",
                  "items_many": "{items}, మొత్తం {total} ఇంకా రావాలి.",
                  "total": "{what} {total} ఇంకా రావాలి.",
                  "promise": "{said} న మీరు ఇలా అన్నారు: “{quote}”.",
                  "close": "వీలైనప్పుడు పంపించండి. ధన్యవాదాలు.",
                  "upi": "UPI లింక్ కింద ఉంది.",
                  "footer": "(Baaki యాప్ నుండి)"},
        "en": {"open": "Hello {party}, a small reminder from {owner}.",
               "items": "The bill for {items} comes to {total}, still pending.",
               "items_many": "{items}: {total} in all, still pending.",
               "total": "{total} for {what} is still pending.",
               "promise": "On {said} you said: “{quote}”.",
               "close": "Please send it when convenient. Thank you.",
               "upi": "The UPI link is below.",
               "footer": "(from the Baaki app)"},
    },
    "chit": {
        "hi-en": {"open": "नमस्ते {party}, {owner} की तरफ़ से एक छोटी सी याद।",
                  "total": "{what}, {total}, अभी आने बाकी हैं।",
                  "promise": "{said} को आपने कहा था: “{quote}”।",
                  "close": "जब हो सके, बता दीजिए कि कब तक मिल जाएगा। धन्यवाद।",
                  "footer": "(Baaki app से)"},
        "te-IN": {"open": "నమస్కారం {party}, {owner} తరఫున ఒక చిన్న గుర్తు.",
                  "total": "{what} {total} ఇంకా రావాలి.",
                  "promise": "{said} న మీరు ఇలా అన్నారు: “{quote}”.",
                  "close": "ఎప్పటికి ఇవ్వగలరో వీలైనప్పుడు చెప్పండి. ధన్యవాదాలు.",
                  "footer": "(Baaki యాప్ నుండి)"},
        "en": {"open": "Hello {party}, a small reminder from {owner}.",
               "total": "{total} of {what} is still to come.",
               "promise": "On {said} you said: “{quote}”.",
               "close": "When you can, please let me know by when it will come. Thank you.",
               "footer": "(from the Baaki app)"},
    },
}
REMINDER["other"] = REMINDER["chit"]

# Never in a reminder: accusation, threats, legal claims, penalties, interest (plus messages.FORBIDDEN).
ACCUSE = ("fraud", "cheat", "scam", "liar", "lied", "broke your", "broken", "thief", "dhokha", "dhoka", "jhooth",
          "jhoot", "chor", "धोखा", "झूठ", "चोर", "మోసం", "అబద్ధం", "దొంగ", "తప్పారు", "court", "complaint",
          "registrar", "case file", "notice", "legal")


def bad_words(text: str) -> list[str]:
    low = f" {text.lower()} "
    return sorted({w for w in (*FORBIDDEN, *ACCUSE) if w.lower() in low})


def _items_phrase(items: list[dict[str, Any]], lang: str, kind: str) -> str:
    parts = [f"{item_label(i.get('item_key'), i.get('month'), i.get('label', ''), lang, kind)} {fmt_money(i['amount'])}"
             for i in items]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    sep = {"en": " and ", "hi-en": " और ", "te-IN": ", "}[lang]
    return ", ".join(parts[:-1]) + sep + parts[-1]


def _what(items: list[dict[str, Any]], lang: str, kind: str) -> str:
    keys = {i.get("item_key") for i in items if i.get("item_key")}
    if len(keys) == 1:
        return ITEM_LABEL[keys.pop()][lang]
    return KIND_DEFAULT_LABEL[kind][lang]


def reminder(*, kind: str, party: str, owner: str, lang: str, balance: float, items: list[dict[str, Any]],
             last_promise: Optional[dict[str, Any]], upi: Optional[str] = None,
             mask: Iterable[str] = ()) -> dict[str, Any]:
    """Text (what they read) + speech (amounts in words, for Timbre) + checks. `items` are the open due items."""
    kind, lang = norm_kind(kind), norm_lang(lang)
    T = REMINDER[kind][lang]
    total = fmt_money(balance)
    p, s = name_of(party, lang), name_of(owner, lang)
    use_items = kind == "vendor" and items and abs(sum(i["amount"] for i in items) - balance) < 0.5 and len(items) <= 4

    def render(money, with_items: bool) -> list[str]:
        out = [T["open"].format(party=p, owner=s)]
        if kind == "vendor" and with_items:
            if len(items) > 1:
                out.append(T["items_many"].format(items=_items_phrase(items, lang, kind), total=money))
            else:
                out.append(T["items"].format(items=item_label(items[0].get("item_key"), items[0].get("month"),
                                                              items[0].get("label", ""), lang, kind, oblique=True),
                                             total=money))
        else:
            out.append(T["total"].format(what=_what(items, lang, kind), total=money))
        if last_promise and kind != "vendor":
            out.append(T["promise"].format(said=fmt_date(last_promise["said_on"], lang, year=False),
                                           quote=last_promise["quote"]))
        out.append(T["close"])
        if kind == "vendor" and upi:
            out.append(T["upi"])
        return out

    def check(text: str, with_items: bool) -> dict[str, Any]:
        expected = [int(round(balance))]
        if kind == "vendor" and with_items and len(items) > 1:
            expected += [int(round(i["amount"])) for i in items]
        if last_promise and kind != "vendor":
            expected += [int(round(a["amount_inr"]))
                         for a in extract_amounts(last_promise["quote"], parse_lang(last_promise.get("lang") or lang))]
        found = [int(round(a)) for a in amounts_in(text, lang, mask)]
        bad = bad_words(text)
        return {"amounts_expected": sorted(expected), "amounts_found": sorted(found),
                "amounts_ok": sorted(found) == sorted(expected), "no_accusation": not bad, "flagged_words": bad}

    sents = render(total, bool(use_items))
    text = " ".join(sents)
    checks = check(text, bool(use_items))
    if not checks["amounts_ok"] and use_items:
        # an item label carried a number-like word: fall back to the total only
        use_items = False
        sents = render(total, False)
        text = " ".join(sents)
        checks = check(text, False)
    if not checks["amounts_ok"] and last_promise:
        last_promise = None   # their quote misread as a figure: leave the quote out rather than send a wrong number
        sents = render(total, bool(use_items))
        text = " ".join(sents)
        checks = check(text, bool(use_items))
    speech = render(money_words(balance, lang), False)
    share = f"{text}\n{T['footer']}" + (f"\n{upi}" if upi else "")
    return {"text": text, "sentences": sents, "speech_sentences": speech, "language": lang, "share_text": share,
            "checks": checks, "source": "template", "items_listed": bool(use_items),
            "quoted_promise": bool(last_promise and kind != "vendor")}


# ------------------------------------------------------------------ hash chain
def log_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    canon = json.dumps({k: entry.get(k) for k in ("account_id", "kind", "said_on", "text", "data_json", "timestamp")},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canon}".encode("utf-8")).hexdigest()


def verify_log(entries: list[dict[str, Any]]) -> dict[str, Any]:
    prev = ""
    for e in entries:
        if e["prev_hash"] != prev or log_hash(e["prev_hash"], e) != e["hash"]:
            return {"valid": False, "broken_at": e.get("id"), "head": None, "count": len(entries)}
        prev = e["hash"]
    return {"valid": True, "broken_at": None, "head": prev or None, "count": len(entries)}


# ------------------------------------------------------------------ record pack
LEGAL_AID = [
    f"Free legal aid: NALSA helpline {NALSA} (toll-free).",
    f"District Legal Services Authority: {DLSA}. Legal aid is free for many people, including women.",
]
NOT_ADVICE = "Baaki is not a lawyer. This is not legal advice. This record lists what was said and when; it does not say why."
PACK_SOURCES = ["NALSA: https://nalsa.gov.in (helpline 15100)",
                "Telangana State Legal Services Authority: https://tslsa.telangana.gov.in"]


def pack_eligible(kind: str, broken: int) -> bool:
    return norm_kind(kind) in ("chit", "other") and broken >= PACK_MIN_BROKEN


def pack_blocks(view: dict[str, Any]) -> list[Any]:
    """PDF blocks (app.pdf.Block) for the record pack. `view` is routes/dues.account_view() output."""
    from .pdf import Block

    a, c, ch = view["account"], view["counter"], view["chain"]
    ol = norm_lang(a["owner_lang"])
    blocks: list[Any] = [
        Block("Record of money owed and promises made", size=17, space_after=2),
        Block(f"Prepared with the Baaki app on {fmt_date(view['as_of'], 'en')} for {a['owner_name']}.", size=10),
        Block(f"Owed by: {a['party_name']}   ·   What: {a['title'] or KIND_DEFAULT_LABEL[a['kind']]['en']}", size=12),
        Block(f"Still owed: {fmt_money(view['balance'])}  (owed {fmt_money(view['total_due'])}, received "
              f"{fmt_money(view['total_paid'])})", size=13),
        Block(c["text_en"] + ".", size=12, space_after=5),
        Block("Amounts", size=13, space_after=1),
    ]
    for i in view["items"]:
        sign = "received" if i["kind"] == "paid" else "owed"
        blocks.append(Block(f"{fmt_date(i['said_on'], 'en')}  ·  {i['display']['en']}  ·  {fmt_money(i['amount'])} "
                            f"{sign}  ·  #{i['hash'][:12]}", size=10, space_after=1))
    blocks.append(Block("Promises, in their own words", size=13, space_after=1))
    for n, p in enumerate(view["promises"], start=1):
        amt = f", {fmt_money(p['amount'])}" if p.get("amount") else ""
        blocks.append(Block(f"{n}. Said {fmt_date(p['said_on'], 'en')}: “{p['quote']}”", size=10, space_after=0))
        blocks.append(Block(f"    Due by {fmt_date(p['due_date'], 'en')}{amt}  ·  {p['status']}  ·  #{p['hash'][:16]}",
                            size=9, space_after=2))
    blocks += [
        Block(f"Hash chain: {'intact' if ch['valid'] else 'CHANGED at entry ' + str(ch['broken_at'])}, "
              f"{ch['count']} entries, head {ch['head'] or '-'}. Each entry's code is sha256 of the previous code and "
              "the entry, so a changed line breaks every code after it.", size=9, space_after=5),
        Block("Help", size=13, space_after=1),
        *[Block(x, size=11, space_after=1) for x in LEGAL_AID],
        Block(PACK_HELP[ol], size=11, space_after=4),
        Block(NOT_ADVICE, size=9, space_after=1),
        Block("Sources: " + "; ".join(PACK_SOURCES), size=8),
    ]
    return blocks


PACK_HELP = {
    "en": "Take this record when you talk to legal aid. It shows the amounts, the dates and their words.",
    "hi-en": "Legal aid से बात करते समय यह record साथ ले जाइए। इसमें रकम, तारीख़ें और उनके अपने शब्द हैं।",
    "te-IN": "లీగల్ ఎయిడ్‌తో మాట్లాడేటప్పుడు ఈ రికార్డు తీసుకెళ్లండి. ఇందులో మొత్తాలు, తేదీలు, వారి మాటలు ఉన్నాయి.",
}
