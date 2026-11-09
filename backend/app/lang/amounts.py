"""Deterministic rupee-amount extraction from code-mixed transcripts.

extract_amounts(text, lang_hint=None) -> list of
    {"amount_inr": int, "start": int, "end": int, "source_text": str,
     "label_hint": str | None}

Spans index into the original text and cover the currency sign/word when it
is there ("₹2,000/-", "55 వేల రూపాయలు"). Every value comes from
``numbers.compose``; nothing is guessed.

What counts as an amount
* a number with a currency mark: ₹, Rs, INR, रु, రూ, rupees/rupaye/రూపాయలు, "/-"
* a number with a multiplier: hazaar, vela/velu, వేలు, lakh, లక్ష, crore, k ...
  (fractions included: dedh/dhai/sava/sade/paune, అర/పావు/ముప్పావు, -న్నర, 2.5 lakh)
* digits with Indian/Western grouping ("1,20,000", "55,000")
* bare digits >= 100 ("painting 5000"), unless they look like something else

What is rejected
* approximate ranges: "do teen hazaar", "2-3 lakh", "bees pachees hazaar", "2 se 3 lakh"
* years (a bare 1900-2100 needs an item label next to it), dates ("15th", "15వ"),
  times (10:30, 5 baje), phone numbers (incl. masked 98XXX XXX10), PIN codes
  after "pin", Hyderabad door numbers (8-2-293/82), flat/room/plot numbers,
  meter readings, counts ("2 rooms", "3 months", "200 units", "1200 sqft")
* number words without a currency word or multiplier ("teen", "ఒకటి")
* "ek rupaya bhi nahi" / "ఒక్క రూపాయి కూడా" (not even one rupee)
"""
from __future__ import annotations

import re
from datetime import date
from fractions import Fraction

from ._text import Tok, norm_deva, norm_telu, skel
from .dates import extract_dates
from .numbers import MAX_INR, canon_lang, scan

# ---------------------------------------------------------------------------
# Item labels -> English slug
# ---------------------------------------------------------------------------
LABELS: dict[str, list[str]] = {
    "painting": ["painting", "paintings", "paint", "repaint", "repainting", "whitewash", "white wash", "colour",
                 "color", "rang", "rangai", "putai", "putty", "पेंटिंग", "पेंट", "रंग", "रंगाई", "पुताई",
                 "పెయింటింగ్", "పెయింట్", "పెయింటు", "రంగులు", "రంగు", "వైట్ వాష్", "సున్నం"],
    "cleaning": ["cleaning", "clean", "deep cleaning", "safai", "safaai", "सफाई", "सफ़ाई", "क्लीनिंग",
                 "క్లీనింగ్", "క్లీనింగు", "క్లీన్", "శుభ్రం"],
    "deposit": ["deposit", "security deposit", "security", "advance", "डिपॉजिट", "डिपोजिट", "डिपाजिट", "एडवांस",
                "एडवान्स", "सिक्योरिटी", "అడ్వాన్స్", "అడ్వాన్సు", "డిపాజిట్", "డిపాజిట్టు", "సెక్యూరిటీ"],
    "rent": ["rent", "rental", "kiraya", "kiraaya", "kiraye", "bhada", "bhaada", "adde", "addhe", "किराया",
             "किराए", "किराये", "भाड़ा", "रेंट", "అద్దె", "రెంట్", "రెంటు"],
    "lift": ["lift", "elevator", "lift usage", "लिफ्ट", "లిఫ్ట్", "లిఫ్టు"],
    "maintenance": ["maintenance", "maintainance", "maintenence", "society charges", "society maintenance",
                    "मेंटेनेंस", "मेंटिनेंस", "మెయింటెనెన్స్", "మెయింటెనెన్సు", "మెంటెనెన్స్"],
    "electricity": ["electricity", "electricity bill", "current bill", "current", "light bill", "power bill",
                    "eb bill", "bijli", "bijli bill", "बिजली", "बिजली बिल", "करंट", "కరెంట్", "కరెంటు",
                    "విద్యుత్"],
    "water": ["water", "water bill", "paani", "pani", "पानी", "నీళ్ళు", "నీళ్లు", "నీటి", "వాటర్"],
    "fan": ["fan", "fans", "pankha", "पंखा", "फैन", "ఫ్యాన్", "ఫ్యాను"],
    "geyser": ["geyser", "geysers", "heater", "water heater", "गीजर", "గీజర్", "గీజరు"],
    "tap": ["tap", "taps", "nal", "nalka", "kulayi", "नल", "ట్యాప్", "కుళాయి", "కొళాయి"],
    "wall": ["wall", "walls", "deewar", "diwar", "goda", "दीवार", "గోడ", "వాల్"],
    "door": ["door", "doors", "darwaza", "darwaja", "talupu", "दरवाजा", "తలుపు", "డోర్"],
    "key": ["key", "keys", "chabi", "chaabi", "chaabiyan", "duplicate key", "चाबी", "चाभी", "తాళం చెవి",
            "తాళంచెవి", "కీస్"],
    "lock": ["lock", "locks", "tala", "taala", "ताला", "తాళం", "లాక్"],
    "window": ["window", "windows", "khidki", "खिड़की", "కిటికీ", "విండో"],
    "light": ["bulb", "bulbs", "tubelight", "tube light", "light", "lights", "बल्ब", "लाइट", "బల్బు", "బల్బ్",
              "లైట్"],
    "ac": ["ac", "air conditioner", "एसी", "ఏసీ"],
    "furniture": ["furniture", "sofa", "sofa cleaning", "bed", "table", "chair", "cot", "mattress", "curtains",
                  "curtain", "फर्नीचर", "पर्दे", "ఫర్నిచర్", "కర్టెన్లు"],
    "cupboard": ["cupboard", "wardrobe", "almirah", "almari", "अलमारी", "బీరువా"],
    "kitchen": ["kitchen", "chimney", "sink", "किचन", "వంటగది", "కిచెన్"],
    "bathroom": ["bathroom", "toilet", "washroom", "बाथरूम", "టాయిలెట్", "బాత్రూమ్", "బాత్రూం"],
    "plumbing": ["plumbing", "plumber", "pipe", "pipes", "leakage", "leak", "प्लंबर", "ప్లంబర్", "పైపు"],
    "repair": ["repair", "repairs", "marammat", "damage", "damages", "nuksan", "मरम्मत", "नुकसान", "रिपेयर",
               "రిపేర్", "రిపేరు", "మరమ్మతు", "డ్యామేజ్", "నష్టం"],
    "tiles": ["tiles", "tile", "flooring", "टाइल्स", "టైల్స్", "ఫ్లోరింగ్"],
    "brokerage": ["brokerage", "broker", "commission", "दलाली", "ब्रोकर", "బ్రోకర్", "కమీషన్"],
    "parking": ["parking", "पार्किंग", "పార్కింగ్"],
    "gas": ["gas", "cylinder", "गैस", "గ్యాస్"],
    "internet": ["internet", "wifi", "broadband", "ఇంటర్నెట్"],
    "pest_control": ["pest control", "pest"],
    "carpentry": ["carpenter", "carpentry", "వడ్రంగి"],
    "notice_period": ["notice", "notice period", "नोटिस", "నోటీసు", "నోటీస్"],
    "balance": ["balance", "baaki", "baki", "remaining", "bakaya", "migatha", "migata", "migathadi", "बाकी",
                "बाक़ी", "बकाया", "మిగతా", "మిగిలిన", "మిగతాది", "బ్యాలెన్స్", "బాకీ"],
    "refund": ["refund", "return", "wapas", "vapas", "वापस", "రిఫండ్", "తిరిగి"],
    "total": ["total", "kul", "mottam", "motham", "कुल", "टोटल", "మొత్తం", "టోటల్"],
}


_GENERIC_LABELS = {"repair", "total", "balance", "refund"}


def _wkey(t: Tok) -> str:
    if t.script == "telu":
        return norm_telu(t.w)
    if t.script == "deva":
        return norm_deva(t.w)
    return skel(t.w)


_LABEL_1: dict[str, str] = {}  # single word (Latin skeleton / Devanagari)
_LABEL_2: dict[tuple[str, str], str] = {}  # two words
_LABEL_TE: list[tuple[str, str]] = []  # Telugu prefixes (case suffixes attach to the noun)
for _slug, _forms in LABELS.items():
    for _f in _forms:
        _parts = _f.split()
        if any("ఀ" <= c <= "౿" for c in _f):
            if len(_parts) == 1:
                _LABEL_TE.append((norm_telu(_f), _slug))
            else:
                _LABEL_2[(norm_telu(_parts[0]), norm_telu(_parts[1]))] = _slug
            continue
        keyf = norm_deva if any("ऀ" <= c <= "ॿ" for c in _f) else skel
        if len(_parts) == 1:
            _LABEL_1[keyf(_f)] = _slug
        else:
            _LABEL_2[(keyf(_parts[0]), keyf(_parts[1]))] = _slug
_LABEL_TE.sort(key=lambda x: len(x[0]), reverse=True)


def _label_of(t: Tok) -> str | None:
    if t.kind != "word":
        return None
    if t.script == "telu":
        k = norm_telu(t.w)
        for form, slug in _LABEL_TE:
            if k.startswith(form) and len(k) - len(form) <= 4:
                return slug
        return None
    k = _wkey(t)
    hit = _LABEL_1.get(k)
    if hit is None and t.script == "latin" and k.endswith("s"):
        hit = _LABEL_1.get(k[:-1])
    return hit


def _find_labels(toks: list[Tok]) -> dict[int, tuple[int, str]]:
    """token index -> (label id, slug). Two-word labels win over one-word ones."""
    out: dict[int, tuple[int, str]] = {}
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t.kind == "word" and i + 1 < n and toks[i + 1].kind == "word":
            slug = _LABEL_2.get((_wkey(t), _wkey(toks[i + 1])))
            if slug is not None:
                out[i] = out[i + 1] = (i, slug)
                i += 2
                continue
        slug = _label_of(t)
        if slug is not None:
            out[i] = (i, slug)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Context word lists (keys: Latin skeleton, Devanagari / Telugu normalised)
# ---------------------------------------------------------------------------
def _keys(words) -> set[str]:
    out = set()
    for w in words:
        if any("ఀ" <= c <= "౿" for c in w):
            out.add(norm_telu(w))
        elif any("ऀ" <= c <= "ॿ" for c in w):
            out.add(norm_deva(w))
        else:
            out.add(skel(w))
    return out


_BARRIER_WORDS = _keys(["and", "aur", "also", "then", "phir", "but", "lekin", "inka", "kani", "kaani", "plus",
                        "और", "फिर", "लेकिन", "మరియు", "ఇంకా", "కానీ", "తర్వాత"])
_BARRIER_SYMS = {",", ";", "!", "?", "।", "॥", "|", ".", ":"}
_PREP_AFTER = _keys(["for", "towards", "as", "against"])
# immediately before a bare number: it is an identifier, not money
_ID_BEFORE = _keys(["flat", "flats", "room", "door", "house", "h", "hno", "plot", "block", "apartment", "apt",
                    "unit", "floor", "gate", "road", "rd", "street", "sector", "phase", "wing", "tower", "bus",
                    "train", "pin", "pincode", "phone", "mobile", "mob", "call", "ph", "contact", "whatsapp",
                    "account", "acc", "acct", "upi", "ifsc", "otp", "id", "aadhaar", "aadhar", "pan", "survey",
                    "ward", "number", "num", "fl", "फ्लैट", "नंबर", "नम्बर", "मकान", "फोन", "मोबाइल", "प्लॉट",
                    "ఫ్లాట్", "నంబర్", "నెంబర్", "నంబరు", "నెంబరు", "ఇంటి", "ఫోన్", "మొబైల్", "ప్లాట్",
                    "డోర్"])
_ID_FILLER = _keys(["no", "number", "num", "nr"]) | {"#", ".", ":", "-"}
# within a few tokens before: a reading, not money (even with hazaar/lakh)
_READING_BEFORE = _keys(["reading", "meter", "odometer", "రీడింగ్", "మీటర్", "रीडिंग", "मीटर"])
# right after a bare number or multiplier phrase: a count / measure
_COUNT_AFTER = _keys([
    "rooms", "room", "bhk", "months", "month", "mahine", "mahina", "mahino", "din", "dino", "days", "day",
    "weeks", "week", "hafte", "hafta", "saal", "sal", "years", "year", "yrs", "nelalu", "nela", "nelala",
    "rojulu", "roju", "rojula", "rojullo", "varalu", "varam", "sq", "sqft", "sft", "square", "feet", "ft",
    "yards", "yard", "gaj", "gaz", "km", "kms", "kg", "kgs", "litres", "liters", "litre", "liter", "ltr", "units",
    "unit", "percent", "people", "persons", "log", "members", "baar", "times", "pieces", "pcs", "hours", "hrs",
    "hour", "ghante", "ghanta", "minutes", "mins", "min", "baje", "am", "pm", "floor", "floors", "steps",
    "कमरे", "कमरा", "महीने", "महीना", "दिन", "हफ्ते", "साल", "वर्ष", "लोग", "बार", "घंटे", "बजे", "यूनिट",
    "फीट", "गज"])
_COUNT_AFTER_TE = [norm_telu(w) for w in ["గదులు", "గది", "నెలలు", "నెలల", "రోజులు", "రోజుల", "రోజు", "వారాలు",
                                          "వారాల", "సంవత్సరాలు", "సంవత్సరం", "ఏళ్ళు", "ఏళ్లు", "సార్లు", "గంటల",
                                          "యూనిట్లు", "అడుగులు", "గజాలు", "మంది", "ఫ్లోర్", "అంతస్తు"]]
_YEAR_CTX_BEFORE = _keys(["in", "since", "year", "saal", "sal", "varsham", "సంవత్సరం", "साल", "सन"])
_YEAR_CTX_AFTER = _keys(["lo", "mein", "me", "se", "tak", "में", "से", "లో"])
_EVEN = _keys(["bhi", "kuda", "kooda", "even", "bi", "भी", "కూడా"])
_CUR_PREFIX_WORDS = _keys(["rs", "inr", "rupees", "rupee", "रु", "रू", "రూ"])
_MONTH_WORDS = _keys(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                      "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
                      "sept", "oct", "nov", "dec", "जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
                      "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर", "జనవరి", "ఫిబ్రవరి", "మార్చి",
                      "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"])

_PHONE_RE = re.compile(
    r"(?<![0-9Xx*])(?:\+?91[\s-]*)?(?:[6-9][0-9Xx*]{9}|[6-9][0-9Xx*]{4}[\s-][0-9Xx*]{5}"
    r"|[6-9][0-9Xx*]{2}[\s-][0-9Xx*]{3}[\s-][0-9Xx*]{4})(?![0-9Xx*])"
)
_ADDRESS_RE = re.compile(r"[0-9]+(?:\s?[-/]\s?[0-9]+[A-Za-z]?){2,}")
_TIME_RE = re.compile(
    r"(?<![0-9,.])[0-9]{1,2}(?::[0-9]{2}(?:\s*(?:am|pm|a\.m\.|p\.m\.))?(?![0-9])|(?:\.[0-9]{2})?\s*(?:"
    r"(?:am|pm|a\.m\.|p\.m\.|baje|o'clock|hrs)(?![A-Za-z])|बजे|గంటల))",
    re.IGNORECASE,
)


def _blocked_spans(work: str) -> list[tuple[int, int]]:
    spans = []
    for rx in (_PHONE_RE, _ADDRESS_RE, _TIME_RE):
        spans += [m.span() for m in rx.finditer(work)]
    return spans


def _overlaps(a: tuple[int, int], spans) -> bool:
    return any(a[0] < e and s < a[1] for s, e in spans)


def _count_after(t: Tok | None) -> bool:
    if t is None:
        return False
    if t.kind == "sym":
        return t.w == "%"
    if t.script == "telu":
        k = norm_telu(t.w)
        return any(k.startswith(w) for w in _COUNT_AFTER_TE)
    return _wkey(t) in _COUNT_AFTER


class _Cand:
    __slots__ = ("p", "value", "t0", "t1", "start", "end", "has_cur", "year_like")

    def __init__(self, p, value, t0, t1, start, end, has_cur, year_like):
        self.p, self.value, self.t0, self.t1 = p, value, t0, t1
        self.start, self.end, self.has_cur, self.year_like = start, end, has_cur, year_like


def extract_amounts(text: str, lang_hint: str | None = None) -> list[dict]:
    """Rupee amounts in a transcript, with spans into ``text`` and an item label."""
    if not text:
        return []
    lang = canon_lang(lang_hint, strict=False)
    work, toks, anns, phrases = scan(text, lang)
    n = len(toks)
    blocked = _blocked_spans(work)
    date_spans = [(d["start"], d["end"]) for d in extract_dates(text, lang, today=date(2026, 1, 1))]
    labels = _find_labels(toks)

    def tok(i: int) -> Tok | None:
        return toks[i] if 0 <= i < n else None

    def key(i: int) -> str | None:
        t = tok(i)
        return None if t is None or t.kind != "word" else _wkey(t)

    cands: list[_Cand] = []
    for p in phrases:
        if p.approx or p.value is None:
            continue
        # currency prefix: ₹ / Rs / Rs. / INR / रु / రూ.
        t0 = p.ti0
        j = p.ti0 - 1
        if j >= 0 and anns[j].role == "curpre":
            t0 = j
        elif j >= 0 and toks[j].w == "." and j - 1 >= 0 and key(j - 1) in _CUR_PREFIX_WORDS:
            t0 = j - 1
        elif j >= 0 and key(j) in _CUR_PREFIX_WORDS:
            t0 = j
        if t0 > 0 and anns[t0 - 1].role == "curpre":  # "Rs ₹" / "₹ Rs" doubled
            t0 -= 1
        # currency suffix: rupaye / రూపాయలు / rs / "/-"
        t1 = p.ti1
        j = p.ti1 + 1
        if j < n and anns[j].role == "cur":
            t1 = j
            j += 1
        if j < n and anns[j].role == "cursuf":
            t1 = j + 1 if j + 1 < n and anns[j + 1].role == "cursuf" else j
        has_cur = t0 != p.ti0 or t1 != p.ti1
        has_mult = p.has_mult
        value: Fraction = p.value
        if value.denominator != 1:
            if has_cur and not has_mult:
                value = Fraction(int(value + Fraction(1, 2)))  # ₹3.50 -> 4: round half up
            else:
                continue
        amount = int(value)
        if amount < 0 or amount > MAX_INR or (amount == 0 and not has_cur):
            continue
        start, end = toks[t0].start, toks[t1].end
        if _overlaps((toks[p.ti0].start, toks[p.ti1].end), blocked):
            continue
        if _overlaps((toks[p.ti0].start, toks[p.ti1].end), date_spans):
            continue
        # a reading ("meter reading atharah hazaar ...") is never money
        if not has_cur and any(key(k) in _READING_BEFORE for k in range(max(0, p.ti0 - 4), p.ti0)):
            continue
        # "ek rupaya bhi nahi" / "ఒక్క రూపాయి కూడా"
        if amount == 1 and has_cur and key(t1 + 1) in _EVEN:
            continue
        year_like = False
        if not has_cur and not has_mult:
            if p.has_word:
                continue  # "teen", "ఒకటి", "fifty" alone are not money
            num_tok = toks[p.ti0]
            if p.ti0 != p.ti1 or anns[p.ti0].ordinal:
                continue
            digits = num_tok.w.replace(",", "").split(".")[0]
            if amount < 100 or len(digits) >= 10:
                continue
            # identifiers: flat 302, flat no. 302, H.No 4, phone 98765...
            k = p.ti0 - 1
            while k >= 0 and (toks[k].w in _ID_FILLER or key(k) in _ID_FILLER):
                k -= 1
            if k >= 0 and key(k) in _ID_BEFORE:
                continue
            if key(p.ti0 - 1) in _MONTH_WORDS:
                continue
            if "," not in num_tok.w and 1900 <= amount <= 2100:
                if key(p.ti0 - 1) in _YEAR_CTX_BEFORE or key(p.ti1 + 1) in _YEAR_CTX_AFTER:
                    continue
                year_like = True
        if not has_cur and _count_after(tok(t1 + 1)):
            continue
        cands.append(_Cand(p, amount, t0, t1, start, end, has_cur, year_like))

    # ------------------------------------------------------------------ labels
    def barrier(i: int) -> bool:
        t = toks[i]
        return (t.kind == "sym" and t.w in _BARRIER_SYMS and t.w not in (":",)) or key(i) in _BARRIER_WORDS

    def scan_label(i: int, stop: int, step: int):
        while (step < 0 and i >= stop) or (step > 0 and i <= stop):
            if barrier(i):
                return None
            if i in labels:
                lab = labels[i]
                # "geyser repair", "fan repair": the item beats the generic word
                if step < 0 and lab[1] in _GENERIC_LABELS and lab[0] - 1 >= stop and lab[0] - 1 in labels \
                        and labels[lab[0] - 1][1] not in _GENERIC_LABELS:
                    return labels[lab[0] - 1]
                return lab
            i += step
        return None

    def lookback_past_comma(i: int, stop: int):
        """Nothing in the amount's own clause: "Current bill pending undi,
        moodu vela rendu vandalu" -> the item named in the clause before."""
        while i >= stop and not barrier(i):
            i -= 1
        if i < stop or toks[i].w != ",":
            return None
        return scan_label(i - 1, max(stop, i - 6), -1)

    used: set[int] = set()
    out = []
    for idx, c in enumerate(cands):
        lo = cands[idx - 1].t1 + 1 if idx else 0
        hi = cands[idx + 1].t0 - 1 if idx + 1 < len(cands) else n - 1
        before = scan_label(c.t0 - 1, max(lo, c.t0 - 6), -1)
        after = scan_label(c.t1 + 1, min(hi, c.t1 + 6), +1)
        if before is None and after is None:
            before = lookback_past_comma(c.t0 - 1, lo)
        if c.year_like and before is None and after is None:
            continue  # "2025" with no item next to it is a year
        choice = None
        if key(c.t1 + 1) in _PREP_AFTER and after is not None and after[0] not in used:
            choice = after
        elif before is not None and before[0] not in used:
            choice = before
        elif after is not None and after[0] not in used:
            choice = after
        if choice is not None:
            used.add(choice[0])
        out.append({
            "amount_inr": c.value,
            "start": c.start,
            "end": c.end,
            "source_text": text[c.start:c.end],
            "label_hint": choice[1] if choice else None,
        })
    return out


__all__ = ["extract_amounts", "LABELS"]
