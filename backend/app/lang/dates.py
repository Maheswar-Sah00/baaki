"""Deterministic date extraction from code-mixed transcripts.

extract_dates(text, lang_hint=None, today=None) -> list of
    {"iso": "YYYY-MM-DD", "start": int, "end": int, "source_text": str,
     "precision": "day" | "week" | "month",
     "range_start": "YYYY-MM-DD" | None, "range_end": "YYYY-MM-DD" | None}

``iso`` is always one date (for a window it is the window's last day, i.e.
the deadline). ``range_start``/``range_end`` are set only for windows such as
"ee vaaram" (this week), "agle hafte" (next week) or "agle mahine".

Spans index into the original text. ``today`` defaults to the current date in
India (IST), not the server's clock.

Resolution rules
* A bare day ("15th", "15 tarikh", "15వ తేదీ") that has already passed this
  month means next month; today's own day number means today. Days past the
  end of a short month are clamped (31st in November -> 30 Nov).
* "ఈ నెల 15" / "is mahine 15" is this month even if the day has passed.
* Month names without a year: this year, or next year if already past.
* Weekdays mean the next one strictly after today ("Monday" said on a Monday
  is a week later). "next Monday" is treated the same.
* Weeks run Monday-Sunday. "ee vaaram" / "this week" = today..Sunday;
  "vacche vaaram" / "agle hafte" / "next week" = next Monday..Sunday.
* "1 week lo" = today + 7; "10 days lo" = today + 10; "rendu vaaraallo" =
  today + 14; "2 months lo" = same day two months on (clamped).
* "next month" / "agle mahine" / "వచ్చే నెల" with no day = the whole of next
  month (iso = its last day). "ee nela" / "is mahine" alone only counts with
  a "within" marker (ఈ నెలలో, is mahine mein): "ee nela konchem kashtam"
  ("this month is hard") is not a date.
* Hindi "kal", a bare day and a weekday are read as future unless a Hindi
  past-tense word sits in the same clause ("kal flat khaali kiya",
  "teen tareekh ko baat hui thi"): then kal = yesterday and the day/weekday
  is the most recent one.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

from ._text import Tok, _script_of, norm_deva, norm_telu, skel, tokenize, work_text
from .numbers import NT, TE_LATN_LEX, canon_lang, compose, latin_order, lookup_word

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(IST).date()


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
_TE_SUF = {"", "కి", "కు", "న", "లో", "్లో", "లోగా", "లోపు", "లోపల", "కల్లా", "వరకు", "దాకా",
           "నాటికి", "ే", "ో", "ున", "ులో", "ుకి", "ం", "ి"}
_TE_WITHIN = {"లో", "్లో", "లోగా", "లోపు", "లోపల", "కల్లా", "వరకు", "దాకా", "ులో", "నాటికి"}
_LAT_SUF = ("lo", "ki", "ku", "na", "loga", "lopu", "kalla", "varaku")
_LAT_WITHIN = {"lo", "loga", "lopu", "kalla", "varaku"}


class _VM:
    """Word -> value lookup across Latin (spelling skeleton), Devanagari and
    Telugu (with case suffixes such as -లో, -కి, -న)."""

    def __init__(self, entries, telu_prefix: bool = False, max_rem: int = 5):
        self.lat: dict = {}
        self.dev: dict = {}
        self.tel: dict = {}
        self.prefix = telu_prefix
        self.max_rem = max_rem
        for value, words in entries:
            for w in words:
                sc = _script_of(w)
                if sc == "latin":
                    self.lat[skel(w)] = value
                elif sc == "deva":
                    self.dev[norm_deva(w)] = value
                else:
                    self.tel[norm_telu(w)] = value
        self.tel_sorted = sorted(self.tel, key=len, reverse=True)
        self._cache: dict = {}

    def get(self, tok: Tok | None):
        """(value, suffix) or None."""
        if tok is None or tok.kind != "word":
            return None
        ck = (tok.script, tok.w)
        if ck not in self._cache:
            self._cache[ck] = self._get(tok)
        return self._cache[ck]

    def _get(self, tok: Tok):
        if tok.script == "latin":
            k = skel(tok.w)
            if k in self.lat:
                return self.lat[k], ""
            for suf in _LAT_SUF:
                if k.endswith(suf) and len(k) - len(suf) >= 3 and k[: -len(suf)] in self.lat:
                    return self.lat[k[: -len(suf)]], suf
            return None
        if tok.script == "deva":
            k = norm_deva(tok.w)
            return (self.dev[k], "") if k in self.dev else None
        k = norm_telu(tok.w)
        if k in self.tel:
            return self.tel[k], ""
        cands = []
        for p in self.tel_sorted:
            if k.startswith(p):
                rem = k[len(p):]
                if rem in _TE_SUF or (self.prefix and len(rem) <= self.max_rem):
                    cands.append((self.tel[p], rem))
        if not cands:
            return None
        for c in cands:  # నెలలో = నెల + లో, not నెలల + ో
            if c[1] in _TE_WITHIN:
                return c
        return cands[0]

    def has(self, tok) -> bool:
        return self.get(tok) is not None


MONTHS = _VM([
    (1, ["january", "jan", "जनवरी", "జనవరి"]),
    (2, ["february", "feb", "फ़रवरी", "फरवरी", "ఫిబ్రవరి", "ఫిబ్రవరీ"]),
    (3, ["march", "mar", "मार्च", "మార్చి", "మార్చ్"]),
    (4, ["april", "apr", "अप्रैल", "ఏప్రిల్", "ఏప్రిల్"]),
    (5, ["may", "मई", "మే"]),
    (6, ["june", "jun", "जून", "జూన్"]),
    (7, ["july", "jul", "जुलाई", "జూలై", "జులై"]),
    (8, ["august", "aug", "अगस्त", "ఆగస్టు", "ఆగస్ట్"]),
    (9, ["september", "sep", "sept", "सितंबर", "सितम्बर", "సెప్టెంబర్", "సెప్టెంబరు"]),
    (10, ["october", "oct", "अक्टूबर", "अक्तूबर", "అక్టోబర్", "అక్టోబరు"]),
    (11, ["november", "nov", "नवंबर", "नवम्बर", "నవంబర్", "నవంబరు"]),
    (12, ["december", "dec", "दिसंबर", "दिसम्बर", "డిసెంబర్", "డిసెంబరు"]),
])
_SHORT_MONTH = {skel(w) for w in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept",
                                  "oct", "nov", "dec", "march")}

WEEKDAYS = _VM([
    (0, ["monday", "somvar", "somvaar", "somavaram", "somavaaram", "सोमवार"]),
    (1, ["tuesday", "mangalvar", "mangalvaar", "mangalavaram", "mangalavaaram", "मंगलवार"]),
    (2, ["wednesday", "budhvar", "budhvaar", "budhavaram", "budhavaaram", "बुधवार"]),
    (3, ["thursday", "guruvar", "guruvaar", "brihaspativar", "veervar", "guruvaram", "guruvaaram",
         "गुरुवार", "बृहस्पतिवार", "वीरवार"]),
    (4, ["friday", "shukravar", "shukravaar", "sukravar", "shukravaram", "sukravaram", "शुक्रवार"]),
    (5, ["saturday", "shanivar", "shanivaar", "sanivar", "shanivaram", "sanivaram", "शनिवार"]),
    (6, ["sunday", "ravivar", "ravivaar", "itvar", "itvaar", "adivaram", "aadivaram", "रविवार", "इतवार"]),
])
_TE_WEEKDAYS = _VM([
    (0, ["సోమవార"]), (1, ["మంగళవార"]), (2, ["బుధవార"]), (3, ["గురువార"]),
    (4, ["శుక్రవార"]), (5, ["శనివార"]), (6, ["ఆదివార"]),
], telu_prefix=True)

REL_DAYS = _VM([
    (0, ["today", "aaj", "ivala", "ivvala", "eeroju", "iroju", "ippude", "आज", "ఈరోజు", "ఇవాళ", "ఇవ్వాళ",
         "ఇవాళే", "ఈరోజే", "ఇప్పుడే"]),
    (1, ["tomorrow", "tmrw", "tmr", "kal", "kall", "repu", "repati", "repatiki", "कल", "రేపు", "రేపటి",
         "రేపటికి", "రేపే", "రేపటిలోగా"]),
    (2, ["parson", "parso", "parsoon", "parsun", "ellundi", "परसों", "ఎల్లుండి", "ఎల్లుండే"]),
])
NEXT = _VM([(1, ["next", "agle", "agla", "agli", "agale", "coming", "upcoming", "vachche", "vache",
                 "vacche", "vachhe", "vachey", "अगले", "अगला", "अगली", "వచ్చే", "వచ్చేటి"])])
THIS = _VM([(0, ["this", "is", "isi", "iss", "ee", "current", "इस", "इसी", "ఈ"])])
MONTH_UNIT = _VM([(1, ["month", "mahine", "mahina", "maheene", "mahinay", "nela", "महीने", "महीना", "माह", "నెల"])])
WEEK_UNIT = _VM([(1, ["week", "hafte", "hafta", "haftey", "vaaram", "varam", "हफ्ते", "हफ़्ते", "हफ्ता", "सप्ताह", "వారం"])])
# units for "in N days/weeks/months"
DUR_UNITS = _VM([
    ("day", ["day", "days", "din", "dino", "dinon", "roju", "rojulu", "rojula", "दिन", "दिनों",
             "రోజు", "రోజులు", "రోజుల"]),
    ("week", ["week", "weeks", "hafte", "hafta", "hafton", "haftey", "vaaram", "varam", "vaaralu", "varalu",
              "varala", "vara", "हफ्ते", "हफ़्ते", "हफ्ता", "हफ़्ता", "हफ्तों", "सप्ताह", "వారం", "వారాలు", "వారాల"]),
    ("month", ["month", "months", "mahine", "mahina", "mahino", "mahinon", "nela", "nelalu", "nelala",
               "महीने", "महीना", "महीनों", "నెల", "నెలలు", "నెలల"]),
])
_IMPLICIT_ONE = {"week", "month"}
DATE_WORD = _VM([(1, ["tarikh", "tareekh", "tarik", "tareek", "taarikh", "taareekh", "date", "tedi", "tedhi",
                      "thedi", "theedi", "tariku", "tarikhu", "tareeku", "तारीख", "तारीख़", "तारीक", "तिथि",
                      "తేదీ", "తేది", "తారీఖు", "తారీఖ", "తారీకు"])])
_TE_DATE_WORD = _VM([(1, ["తేదీ", "తేది", "తారీఖ", "తారీక"])], telu_prefix=True, max_rem=4)
PRE_MARK = _VM([(1, ["in", "within", "after", "inside", "by"])])
POST_MARK = _VM([(1, ["lo", "mein", "me", "mai", "andar", "baad", "tak", "varaku", "lopu", "loga",
                      "lopala", "tarvata", "taruvata", "kalla", "में", "बाद", "तक", "अंदर",
                      "లో", "లోపు", "లోగా", "లోపల", "తర్వాత", "తరువాత", "కల్లా", "వరకు", "దాకా"])])
_FILLER = {skel(w) for w in ("ki", "ke", "ka", "of", "the", "on", "ko", "lo")} | {norm_deva(w) for w in ("की", "के", "का", "को")}
_OF = {skel(w) for w in ("of", "the", "ki", "ke", "ka")} | {norm_deva(w) for w in ("की", "के", "का")}
END_WORD = _VM([(1, ["end", "ant", "aakhir", "akhir", "aakhri", "last", "अंत", "आखिर", "आख़िर", "एंड", "आखरी"])])
_TE_MONTH_END = _VM([(1, ["నెలాఖర", "నెలాఖరి", "nelaakharu", "nelakharu", "nelaakhari", "nelaaakhari"])],
                    telu_prefix=True)
_TE_CHIVARA = _VM([(1, ["చివర", "ఆఖర"])], telu_prefix=True)
_NOT_DATE_AFTER = _VM([(1, ["floor", "flr", "cross", "main", "stage", "phase", "block", "sector", "street", "road",
                            "lane", "class", "standard", "std", "rank", "place", "time", "times", "attempt",
                            "installment", "instalment", "week", "month", "year", "century", "anniversary",
                            "मंजिल", "అంతస్తు", "ఫ్లోర్"])])
_LAT_ORD_SUF = {"st", "nd", "rd", "th"}
_TE_ORD_SUF = {"వ", "వది", "న", "వ్", "ో", "వా"}

EN_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirtieth": 30,
}
_EN_ORD = {skel(k): v for k, v in EN_ORDINALS.items()}
_KAL = {skel("kal"), skel("kall"), norm_deva("कल")}
# Hindi/Hinglish past-tense words (reported speech verbs like "bola"/"kaha"
# are left out on purpose: "owner ne kaha 15 tarikh ko denge" is a promise).
_PAST = {skel(w) for w in ("tha", "thi", "hua", "hui", "hue", "kiya", "kiye", "gaya", "gayi", "gaye", "gya",
                          "diya", "diye", "liya", "mila", "mili", "aaya", "aaye", "aayi", "aya", "bheja",
                          "bheje", "bheji", "paid", "was", "did", "sent", "received", "transferred", "gave",
                          "happened")} | \
        {norm_deva(w) for w in ("था", "थी", "थे", "हुआ", "हुई", "हुए", "किया", "किए", "किये", "गया", "गई",
                                "गए", "दिया", "दिए", "लिया", "मिला", "मिली", "आया", "आए", "आई", "भेजा",
                                "भेजे", "भेजी")}
_CLAUSE_END = {".", ",", "!", "?", "।", "॥", ";", "|"}
_FIRST_WORDS = _VM([(1, ["pehli", "pahli", "pehla", "pahla", "pehle", "पहली", "पहला", "మొదటి"])])


# ---------------------------------------------------------------------------
# Date arithmetic
# ---------------------------------------------------------------------------
def _clamp(y: int, m: int, d: int) -> date:
    return date(y, m, min(d, calendar.monthrange(y, m)[1]))


def _add_months(d: date, k: int, day: int | None = None) -> date:
    y, m = divmod(d.month - 1 + k, 12)
    return _clamp(d.year + y, m + 1, day if day is not None else d.day)


def _month_end(d: date, k: int = 0) -> date:
    first = _add_months(d.replace(day=1), k, 1)
    return _clamp(first.year, first.month, 31)


def _bare_day(today: date, d: int) -> date:
    if d >= today.day:
        return _clamp(today.year, today.month, d)
    return _add_months(today.replace(day=1), 1, d)


def _named_month(today: date, m: int, d: int | None, y: int | None) -> date:
    if y is not None:
        return _clamp(y, m, d if d is not None else 31)
    cand = _clamp(today.year, m, d if d is not None else 31)
    if cand < today:
        cand = _clamp(today.year + 1, m, d if d is not None else 31)
    return cand


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------
class _Matcher:
    def __init__(self, text: str, lang_hint: str | None, today: date):
        self.text = text
        self.work = work_text(text)
        self.toks = tokenize(self.work, text)
        self.n = len(self.toks)
        self.today = today
        self.order = latin_order(lang_hint)

    # --- token helpers -----------------------------------------------------
    def tok(self, i: int) -> Tok | None:
        return self.toks[i] if 0 <= i < self.n else None

    def attached(self, i: int, gap: int = 1) -> bool:
        """token i starts within ``gap`` chars of token i-1's end."""
        return 0 < i < self.n and self.toks[i].start - self.toks[i - 1].end <= gap

    def int_tok(self, i: int) -> int | None:
        t = self.tok(i)
        if t is None or t.kind != "num" or not t.w.isdigit():
            return None
        return int(t.w)

    def num_word(self, i: int) -> tuple[NT, ...] | None:
        t = self.tok(i)
        if t is None or t.kind != "word":
            return None
        lex = lookup_word(t, self.order)
        if not lex or any(x.kind != "num" for x in lex):
            return None
        return tuple(NT(x.kind, x.value, i, tens=x.tens) for x in lex)

    def is_amountish(self, i: int) -> bool:
        """token i is a multiplier/currency word (so the number before it is money)."""
        t = self.tok(i)
        if t is None:
            return False
        if t.kind == "sym":
            return t.w in ("₹", "%")
        if t.script == "latin" and t.low in ("k", "l") and self.attached(i):
            return True
        lex = lookup_word(t, self.order)
        return bool(lex) and lex[0].kind in ("mult", "cur", "frac")

    def past(self, i0: int, i1: int) -> bool:
        """A Hindi past-tense word in the same clause as tokens i0..i1-1."""
        for rng in (range(i1, min(self.n, i1 + 8)), range(i0 - 1, max(-1, i0 - 7), -1)):
            for j in rng:
                t = self.toks[j]
                if t.kind == "sym" and t.w in _CLAUSE_END:
                    break
                if t.kind != "word":
                    continue
                key = skel(t.w) if t.script == "latin" else norm_deva(t.w)
                if key in _PAST:
                    return True
        return False

    def date_word(self, i: int) -> bool:
        t = self.tok(i)
        return DATE_WORD.has(t) or _TE_DATE_WORD.has(t)

    # --- day of month ------------------------------------------------------
    def te_ordinal(self, i: int) -> int | None:
        """పదిహేనో / పదిహేనవ / ఇరవయ్యో -> 15 / 15 / 20; మొదటి -> 1."""
        t = self.tok(i)
        if t is None or t.kind != "word":
            return None
        if t.script == "latin":
            k = skel(t.w)
            for suf in ("va", "o"):
                if k.endswith(suf) and len(k) > len(suf) + 2:
                    stem = k[: -len(suf)]
                    for c in (stem + "u", stem + "i", stem):
                        lex = TE_LATN_LEX.get(c)
                        if lex and len(lex) == 1 and lex[0].kind == "num" and 1 <= lex[0].value <= 31 \
                                and lex[0].value.denominator == 1:
                            return int(lex[0].value)
            return None
        if t.script != "telu":
            return None
        k = norm_telu(t.w)
        for suf in ("వది", "వ", "ో"):
            if k.endswith(suf) and len(k) > len(suf):
                stem = k[: -len(suf)]
                cands = [stem + "ు", stem + "ి", stem]
                if stem.endswith("య్య"):
                    cands.append(stem[:-3] + "ై")
                for c in cands:
                    lex = lookup_word(Tok(i, t.start, t.end, c, c, "word", "telu"))
                    if lex and all(x.kind == "num" for x in lex):
                        v = compose([NT(x.kind, x.value, i, tens=x.tens) for x in lex])
                        if v is not None and v.denominator == 1 and 1 <= v <= 31:
                            return int(v)
        return None

    def day_at(self, i: int, allow_weak: bool):
        """Parse a day of month starting at token i -> (day, end_exclusive, strong)."""
        t = self.tok(i)
        if t is None:
            return None
        v = self.int_tok(i)
        if v is not None:
            if not (1 <= v <= 31):
                return None
            j, strong = i + 1, False
            nt = self.tok(j)
            if nt is not None and nt.kind == "word" and self.attached(j):
                if (nt.script == "latin" and nt.low in _LAT_ORD_SUF) or \
                        (nt.script == "telu" and norm_telu(nt.w) in _TE_ORD_SUF):
                    j, strong = j + 1, True
            if self.date_word(j):
                j, strong = j + 1, True
            if strong and _NOT_DATE_AFTER.has(self.tok(j)):
                return None
            if not strong:
                if not allow_weak or self.is_amountish(j) or self.tok(j) is not None and \
                        self.tok(j).kind == "sym" and self.tok(j).w in (":", ".") and self.int_tok(j + 1) is not None:
                    return None
                nxt = self.tok(j)
                if nxt is not None and DUR_UNITS.has(nxt):
                    return None
            return v, j, strong
        if t.kind != "word":
            return None
        # English ordinal words: fifteenth, twenty first, twenty-first
        k = skel(t.w)
        if k in _EN_ORD:
            return self._ord_ctx(_EN_ORD[k], i + 1, i, allow_weak)
        lex = self.num_word(i)
        if lex is not None and len(lex) == 1 and lex[0].tens:
            j = i + 1
            if self.tok(j) is not None and self.tok(j).w == "-":
                j += 1
            nt = self.tok(j)
            if nt is not None and skel(nt.w) in _EN_ORD and _EN_ORD[skel(nt.w)] < 10:
                return self._ord_ctx(int(lex[0].value) + _EN_ORD[skel(nt.w)], j + 1, i, allow_weak)
        # pehli tarikh / పదిహేనో తారీఖు / ఇరవై ఐదో తేదీ / pandrah tarikh
        if _FIRST_WORDS.has(t):
            if self.date_word(i + 1):
                return 1, i + 2, True
            return None
        tv = self.te_ordinal(i)
        if tv is not None:
            if self.date_word(i + 1):
                return tv, i + 2, True
            if allow_weak and not _NOT_DATE_AFTER.has(self.tok(i + 1)):
                return tv, i + 1, False
            return None
        if lex is not None:
            nts = list(lex)
            j = i + 1
            nxt = self.num_word(j)
            tv2 = self.te_ordinal(j) if nxt is None else None
            if tv2 is not None and nts[-1].tens and tv2 < 10:
                if self.date_word(j + 1):
                    return int(nts[-1].value) + tv2, j + 2, True
                if allow_weak:
                    return int(nts[-1].value) + tv2, j + 1, False
                return None
            if nxt is not None:
                nts += list(nxt)
                j += 1
            if self.date_word(j):
                val = compose(nts)
                if val is not None and val.denominator == 1 and 1 <= val <= 31:
                    return int(val), j + 1, True
        return None

    def _ord_ctx(self, v: int, j: int, i: int, allow_weak: bool = False):
        """English ordinal words as days: "fifteenth ki", "December fifth",
        "the first". "first" and "second" are everyday words, so they need
        date context ("first tarikh", "the first", "first of December")."""
        if not (1 <= v <= 31):
            return None
        nt = self.tok(j)
        if self.date_word(j):
            return v, j + 1, True
        if _NOT_DATE_AFTER.has(nt):
            return None
        if nt is not None and (MONTHS.has(nt) or skel(nt.w) == "of"):
            return v, j, True
        prev = self.tok(i - 1)
        if prev is not None and skel(prev.w) == "the":
            return v, j, True
        if v >= 3:
            return v, j, True
        if allow_weak:
            return v, j, False
        return None

    # --- month context: "ee nela", "agle mahine", "next month" ---------------
    def month_ctx(self, i: int):
        """-> (offset_months, end_exclusive) for THIS/NEXT + month word."""
        t = self.tok(i)
        if t is None:
            return None
        if t.script == "telu":
            k = norm_telu(t.w)
            if k.startswith("వచ్చేనెల"):
                return 1, i + 1
            if k.startswith("ఈనెల"):
                return 0, i + 1
        for vm, off in ((NEXT, 1), (THIS, 0)):
            if vm.has(t) and MONTH_UNIT.has(self.tok(i + 1)):
                return off, i + 2
        return None

    def year_at(self, i: int):
        j = i
        if self.tok(j) is not None and self.tok(j).w == ",":
            j += 1
        y = self.int_tok(j)
        if y is not None and 1900 <= y <= 2100 and len(self.tok(j).w) == 4:
            return y, j + 1
        return None

    # --- patterns ------------------------------------------------------------
    def p_numeric(self, i: int):
        d = self.int_tok(i)
        if d is None or not (1 <= d <= 31) or len(self.tok(i).w) > 2:
            return None
        sep = self.tok(i + 1)
        if sep is None or sep.w not in ("/", "-", ".") or not self.attached(i + 1, 0) or not self.attached(i + 2, 0):
            return None
        m = self.int_tok(i + 2)
        if m is None or not (1 <= m <= 12):
            return None
        j = i + 3
        y = None
        s2 = self.tok(j)
        if s2 is not None and s2.w == sep.w and self.attached(j, 0) and self.attached(j + 1, 0):
            yv = self.int_tok(j + 1)
            if yv is not None and len(self.tok(j + 1).w) in (2, 4):
                y = yv + 2000 if yv < 100 else yv
                j += 2
        if y is None and sep.w != "/":
            return None
        try:
            iso = date(y, m, d) if y else _named_month(self.today, m, d, None)
        except ValueError:
            return None
        return j, iso, "day"

    def p_ctx_then_day(self, i: int):
        mc = self.month_ctx(i)
        if mc is None:
            return None
        off, j = mc
        k = j
        while k < self.n and k - j < 2 and self.tok(k).kind == "word" and \
                (skel(self.tok(k).w) in _FILLER or norm_deva(self.tok(k).w) in _FILLER):
            k += 1
        day = self.day_at(k, allow_weak=True)
        if day is None:
            return None
        d, end, _ = day
        base = self.today.replace(day=1)
        return end, _add_months(base, off, d), "day"

    def p_day_then_ctx(self, i: int):
        day = self.day_at(i, allow_weak=False)
        if day is None:
            return None
        d, j, _ = day
        k = j
        while k < self.n and k - j < 2 and self.tok(k).kind == "word" and \
                (skel(self.tok(k).w) in _OF or norm_deva(self.tok(k).w) in _OF):
            k += 1
        mc = self.month_ctx(k)
        if mc is not None:
            off, end = mc
            return end, _add_months(self.today.replace(day=1), off, d), "day"
        mo = MONTHS.get(self.tok(k))
        if mo is not None:
            yv = self.year_at(k + 1)
            y, end = (yv if yv else (None, k + 1))
            return end, _named_month(self.today, mo[0], d, y), "day"
        return None

    def p_weak_day_then_month(self, i: int):
        """15 December, 15 దిసెంబర్, 15 दिसंबर (no ordinal)."""
        d = self.int_tok(i)
        if d is None or not (1 <= d <= 31):
            return None
        mo = MONTHS.get(self.tok(i + 1))
        if mo is None:
            return None
        yv = self.year_at(i + 2)
        y, end = (yv if yv else (None, i + 2))
        return end, _named_month(self.today, mo[0], d, y), "day"

    def p_month_then_day(self, i: int):
        mo = MONTHS.get(self.tok(i))
        if mo is None:
            return None
        day = self.day_at(i + 1, allow_weak=True)
        if day is None:
            return None
        d, j, _ = day
        yv = self.year_at(j)
        y, end = (yv if yv else (None, j))
        return end, _named_month(self.today, mo[0], d, y), "day"

    def p_day_alone(self, i: int):
        day = self.day_at(i, allow_weak=False)
        if day is None:
            return None
        d, j, strong = day
        if not strong:
            return None
        if self.past(i, j):  # "teen tareekh ko baat hui thi" -> the most recent 3rd
            if d <= self.today.day:
                return j, _clamp(self.today.year, self.today.month, d), "day"
            return j, _add_months(self.today.replace(day=1), -1, d), "day"
        return j, _bare_day(self.today, d), "day"

    def p_relative(self, i: int):
        t = self.tok(i)
        if t is None or t.kind != "word":
            return None
        k = skel(t.w) if t.script == "latin" else None
        # aaj kal / आजकल = "these days": not a date
        if (k == "aj" and self.tok(i + 1) is not None and skel(self.tok(i + 1).w) == "kal") or \
                (t.script == "deva" and norm_deva(t.w) in ("आजकल",)):
            return i + 2 if k == "aj" else i + 1, None, None
        if t.script == "deva" and norm_deva(t.w) == "आज" and self.tok(i + 1) is not None and \
                norm_deva(self.tok(i + 1).w) == "कल":
            return i + 2, None, None
        if k == "day" and skel(self.tok(i + 1).w if self.tok(i + 1) else "") == "after" and \
                REL_DAYS.get(self.tok(i + 2)) == (1, ""):
            return i + 3, self.today + timedelta(days=2), "day"
        rel = REL_DAYS.get(t)
        if rel is None:
            # ఈ రోజు (two words)
            if THIS.has(t) and self.tok(i + 1) is not None and self.tok(i + 1).kind == "word" and \
                    (skel(self.tok(i + 1).w) == "roju" or norm_telu(self.tok(i + 1).w).startswith("రోజు")):
                return i + 2, self.today, "day"
            return None
        off = rel[0]
        end = i + 1
        key = skel(t.w) if t.script == "latin" else norm_deva(t.w)
        if off == 1 and key in _KAL and self.past(i, i + 1):
            return end, self.today - timedelta(days=1), "day"
        # kal parson / kal-parson = within a day or two -> the later day
        j = i + 1
        if self.tok(j) is not None and self.tok(j).w == "-":
            j += 1
        nxt = REL_DAYS.get(self.tok(j))
        if off == 1 and nxt is not None and nxt[0] == 2:
            off, end = 2, j + 1
        return end, self.today + timedelta(days=off), "day"

    def p_weekday(self, i: int):
        j = i
        t = self.tok(i)
        if NEXT.has(t) or THIS.has(t):
            j = i + 1
        wd = WEEKDAYS.get(self.tok(j)) or _TE_WEEKDAYS.get(self.tok(j))
        if wd is None:
            return None
        if self.past(i, j + 1):
            back = (self.today.weekday() - wd[0]) % 7 or 7
            return j + 1, self.today - timedelta(days=back), "day"
        delta = (wd[0] - self.today.weekday()) % 7 or 7
        return j + 1, self.today + timedelta(days=delta), "day"

    def p_month_end(self, i: int):
        t = self.tok(i)
        if t is None:
            return None
        off, j = 0, i
        if NEXT.has(t) and not MONTH_UNIT.has(t):
            off, j = 1, i + 1
        elif THIS.has(t):
            j = i + 1
        tj = self.tok(j)
        if tj is None:
            return None
        if tj.script == "telu":
            k = norm_telu(tj.w)
            if k.startswith("వచ్చేనెలాఖర"):
                return j + 1, _month_end(self.today, 1), "month"
        if _TE_MONTH_END.has(tj):
            return j + 1, _month_end(self.today, off), "month"
        if MONTH_UNIT.has(tj):
            # నెల చివర / mahine ke end / month end / month-end
            k = j + 1
            if self.tok(k) is not None and self.tok(k).w == "-":
                k += 1
            while self.tok(k) is not None and self.tok(k).kind == "word" and \
                    (skel(self.tok(k).w) in _OF or norm_deva(self.tok(k).w) in _OF):
                k += 1
            if END_WORD.has(self.tok(k)) or _TE_CHIVARA.has(self.tok(k)):
                return k + 1, _month_end(self.today, off), "month"
            return None
        # end of (the|this|next) month
        if off == 0 and j == i and skel(tj.w) == "end" and self.tok(j + 1) is not None and \
                skel(self.tok(j + 1).w) == "of":
            k = j + 2
            if self.tok(k) is not None and skel(self.tok(k).w) == "the":
                k += 1
            o2 = 0
            if NEXT.has(self.tok(k)):
                o2, k = 1, k + 1
            elif THIS.has(self.tok(k)):
                k += 1
            if MONTH_UNIT.has(self.tok(k)):
                return k + 1, _month_end(self.today, o2), "month"
        if skel(tj.w) in ("monthend",):
            return j + 1, _month_end(self.today, off), "month"
        return None

    def p_next_week_month(self, i: int):
        t = self.tok(i)
        if t is None:
            return None
        today = self.today

        def next_month():
            return _add_months(today.replace(day=1), 1, 1), _month_end(today, 1)

        if t.script == "telu":
            k = norm_telu(t.w)
            if k.startswith("వచ్చేనెల"):
                nm = next_month()
                return i + 1, nm[1], "month", nm
        if NEXT.has(t):
            if WEEK_UNIT.has(self.tok(i + 1)):
                mon = today + timedelta(days=7 - today.weekday())
                return i + 2, mon + timedelta(days=6), "week", (mon, mon + timedelta(days=6))
            if MONTH_UNIT.has(self.tok(i + 1)):
                nm = next_month()
                return i + 2, nm[1], "month", nm
        if THIS.has(t):
            if WEEK_UNIT.has(self.tok(i + 1)):
                sun = today + timedelta(days=6 - today.weekday())
                return i + 2, sun, "week", (today, sun)
            mu = MONTH_UNIT.get(self.tok(i + 1))
            if mu is not None:
                end = i + 2
                within = mu[1] in _TE_WITHIN or mu[1] in _LAT_WITHIN
                if not within and POST_MARK.has(self.tok(end)):
                    within, end = True, end + 1
                prev = self.tok(i - 1)
                if not within and prev is not None and skel(prev.w) in ("by", "in", "within"):
                    within = True
                if within:
                    me = _month_end(today, 0)
                    return end, me, "month", (today, me)
        return None

    def p_duration(self, i: int):
        """in 10 days / 10 days lo / 10 din mein / 10 రోజుల్లో / 1 week lo / వారంలో"""
        start = i
        j = i
        pre = False
        if PRE_MARK.has(self.tok(j)):
            pre = True
            j += 1
        # number (digits or up to two number words)
        nval = None
        k = j
        v = self.int_tok(k)
        tk = self.tok(k)
        if v is not None:
            nval, k = v, k + 1
        elif tk is not None and tk.script == "latin" and tk.low in ("a", "an"):
            nval, k = 1, k + 1
        else:
            nts = self.num_word(k)
            if nts is not None:
                nts = list(nts)
                k += 1
                more = self.num_word(k)
                if more is not None:
                    nts += list(more)
                    k += 1
                c = compose(nts)
                if c is None:
                    return None  # "do teen din" = a few days
                if c.denominator == 1:
                    nval = int(c)
        if nval is not None:
            # "2-3 din", "do teen din": the number before is part of a range
            def small(ix: int) -> bool:
                iv = self.int_tok(ix)
                return (iv is not None and iv < 100) or self.num_word(ix) is not None

            p1 = self.tok(j - 1)
            if not pre and p1 is not None and small(j - 1) and p1.end >= self.toks[j].start - 1:
                return None
            if not pre and p1 is not None and p1.w == "-" and small(j - 2):
                return None
        unit = DUR_UNITS.get(self.tok(k))
        if unit is None:
            return None
        u, suf = unit
        end = k + 1
        post = suf in _TE_WITHIN or suf in _LAT_WITHIN
        if not post:
            m = end
            if self.tok(m) is not None and skel(self.tok(m).w) in ("ke",) or \
                    (self.tok(m) is not None and norm_deva(self.tok(m).w) == "के"):
                m += 1
            if POST_MARK.has(self.tok(m)):
                post = True
                end = m + 1
        if not (pre or post):
            return None
        if nval is None:
            if u not in _IMPLICIT_ONE or k != j:
                return None
            nval = 1
        if nval <= 0 or nval > 366:
            return None
        if u == "day":
            return end, self.today + timedelta(days=nval), "day"
        if u == "week":
            return end, self.today + timedelta(days=7 * nval), "week"
        return end, _add_months(self.today, nval), "month"

    def p_month_alone(self, i: int):
        t = self.tok(i)
        mo = MONTHS.get(t)
        if mo is None or skel(t.w) in _SHORT_MONTH:
            return None
        prev = self.tok(i - 1)
        within = mo[1] in _TE_WITHIN or mo[1] in _LAT_WITHIN
        if not within and prev is not None and skel(prev.w) in ("in", "by", "till", "until"):
            within = True
        nxt = self.tok(i + 1)
        if not within and POST_MARK.has(nxt):
            within = True
        yv = self.year_at(i + 1)
        if yv:
            return yv[1], _named_month(self.today, mo[0], None, yv[0]), "month"
        if not within:
            return None
        last = _named_month(self.today, mo[0], None, None)
        first = last.replace(day=1)
        return i + 1, last, "month", (max(first, self.today), last)

    PATTERNS = ("p_numeric", "p_ctx_then_day", "p_day_then_ctx", "p_weak_day_then_month", "p_month_then_day",
                "p_day_alone", "p_relative", "p_month_end", "p_weekday", "p_next_week_month", "p_duration",
                "p_month_alone")

    def run(self) -> list[dict]:
        out = []
        i = 0
        while i < self.n:
            hit = None
            for name in self.PATTERNS:
                hit = getattr(self, name)(i)
                if hit is not None:
                    break
            if hit is None:
                i += 1
                continue
            end, iso, precision = hit[:3]
            rng = hit[3] if len(hit) > 3 else None
            if iso is not None:
                s, e = self.toks[i].start, self.toks[end - 1].end
                out.append({"iso": iso.isoformat(), "start": s, "end": e,
                            "source_text": self.text[s:e], "precision": precision,
                            "range_start": rng[0].isoformat() if rng else None,
                            "range_end": rng[1].isoformat() if rng else None})
            i = max(end, i + 1)
        return out


def extract_dates(text: str, lang_hint: str | None = None, today: date | None = None) -> list[dict]:
    """Dates and deadlines in a transcript, resolved against ``today`` (IST)."""
    if not text:
        return []
    canon_lang(lang_hint, strict=False)
    return _Matcher(text, lang_hint, today or today_ist()).run()


__all__ = ["extract_dates", "today_ist", "IST"]
