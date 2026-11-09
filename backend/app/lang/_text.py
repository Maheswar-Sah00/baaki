"""Shared text helpers for the deterministic language layer.

Everything here keeps character offsets stable: ``work_text`` only does 1:1
character substitutions, so a span found in the work string indexes the
original transcript exactly.

Python's ``\\w`` and ``\\b`` treat Indic vowel signs and viramas as non-word
characters, which splits Telugu and Devanagari words in the middle. We use an
explicit letter class instead and never rely on ``\\b`` for Indic text.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# ---------------------------------------------------------------------------
# Work string: same length as the input, native digits -> ASCII digits.
# ---------------------------------------------------------------------------
_WORK_TABLE: dict[int, str] = {}
for _i in range(10):
    _WORK_TABLE[0x0966 + _i] = str(_i)  # Devanagari digits
    _WORK_TABLE[0x0C66 + _i] = str(_i)  # Telugu digits
for _cp in (0x00A0, 0x2007, 0x2009, 0x202F):  # no-break / thin spaces
    _WORK_TABLE[_cp] = " "
for _cp in range(0x2010, 0x2016):  # hyphen, en dash, em dash ...
    _WORK_TABLE[_cp] = "-"
_WORK_TABLE[0x2212] = "-"  # minus sign
_WORK_TABLE[0x2019] = "'"  # right single quote


def work_text(text: str) -> str:
    """Return a same-length copy of ``text`` that is easier to scan."""
    return text.translate(_WORK_TABLE)


# Letters of the scripts we read: Latin (+ accents, IAST romanisation such as mūḍu), Devanagari letters and
# signs (not the danda or digits), Telugu letters and signs, ZWNJ/ZWJ.
LETTERS = "A-Za-zÀ-ɏ̀-ͯḀ-ỿऀ-ॣॱ-ॿఀ-ౣ‌‍"  # + IAST dots (ḍ ṇ ṭ ṅ) and combining marks
TOKEN_RE = re.compile(
    rf"(?P<num>[0-9]+(?:[.,][0-9]+)*)|(?P<word>[{LETTERS}][{LETTERS}']*)|(?P<sym>\S)"
)

_DEVA_RE = re.compile("[ऀ-ॿ]")
_TELU_RE = re.compile("[ఀ-౿]")


@dataclass
class Tok:
    i: int
    start: int
    end: int
    text: str  # slice of the original text
    w: str  # slice of the work text
    kind: str  # 'num' | 'word' | 'sym'
    script: str  # 'latin' | 'deva' | 'telu' | 'digit' | 'sym'

    @property
    def low(self) -> str:
        return self.w.lower()


def _script_of(word: str) -> str:
    if _TELU_RE.search(word):
        return "telu"
    if _DEVA_RE.search(word):
        return "deva"
    return "latin"


_INDIAN_GROUPED = re.compile(r"^[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}$")
_WESTERN_GROUPED = re.compile(r"^[0-9]{1,3}(?:,[0-9]{3})+$")


def _valid_grouping(intpart: str) -> bool:
    if "," not in intpart:
        return True
    return bool(_INDIAN_GROUPED.match(intpart) or _WESTERN_GROUPED.match(intpart))


def tokenize(work: str, original: str | None = None) -> list[Tok]:
    """Split the work string into number, word and symbol tokens.

    Number tokens keep valid Indian/Western comma grouping and one decimal
    part ("1,20,000", "2.5", "₹2,000.00"). Anything else that looks like a
    number list ("55,10", "15.12.2026") is split into separate tokens so the
    callers can decide what it is.
    """
    if original is None:
        original = work
    out: list[Tok] = []

    def add(start: int, end: int, kind: str, script: str) -> None:
        out.append(Tok(len(out), start, end, original[start:end], work[start:end], kind, script))

    for m in TOKEN_RE.finditer(work):
        s, e = m.span()
        if m.lastgroup == "num":
            raw = m.group()
            if _num_ok(raw):
                add(s, e, "num", "digit")
            else:
                # split on separators, keep separators as symbols
                pos = s
                for part in re.finditer(r"[0-9]+|[.,]", raw):
                    ps, pe = s + part.start(), s + part.end()
                    if part.group()[0].isdigit():
                        add(ps, pe, "num", "digit")
                    else:
                        add(ps, pe, "sym", "sym")
                    pos = pe
        elif m.lastgroup == "word":
            add(s, e, "word", _script_of(m.group()))
        else:
            add(s, e, "sym", "sym")
    return out


def _num_ok(raw: str) -> bool:
    if raw.count(".") > 1:
        return False
    if "." in raw:
        intpart, dec = raw.split(".")
        if "," in dec:
            return False
    else:
        intpart = raw
    return _valid_grouping(intpart)


# ---------------------------------------------------------------------------
# Normalisers used as dictionary keys
# ---------------------------------------------------------------------------
_ZW = {0x200C: None, 0x200D: None}


@lru_cache(maxsize=65536)
def norm_telu(word: str) -> str:
    return unicodedata.normalize("NFC", word).translate(_ZW)


_DEVA_FIX = {0x093C: None, 0x200C: None, 0x200D: None, 0x0901: "ं"}


@lru_cache(maxsize=65536)
def norm_deva(word: str) -> str:
    """NFC, drop nukta (ज़ == ज, ड़ == ड), chandrabindu -> anusvara."""
    return unicodedata.normalize("NFC", word).translate(_DEVA_FIX)


@lru_cache(maxsize=65536)
def skel(word: str) -> str:
    """Spelling-tolerant key for romanised Hindi/Telugu/English words.

    pachpan/pachpun stay apart, but hazaar/hazar/hajar, pannendu/panendu,
    chhe/che, terah/tera, moodu/mudu all collapse to one key. 't' and 'th'
    stay distinct because saat (7) and saath (60) differ only there.
    """
    s = unicodedata.normalize("NFKD", word.lower())
    s = "".join(c for c in s if "a" <= c <= "z")
    s = s.replace("chch", "ch").replace("cch", "ch").replace("chh", "ch")
    s = s.replace("ee", "i").replace("oo", "u")
    s = s.replace("w", "v").replace("z", "j").replace("q", "k")
    s = s.replace("sh", "s")
    s = re.sub(r"(.)\1+", r"\1", s)
    s = re.sub(r"([aeiou])h$", r"\1", s)
    return s


def key_for(tok_text: str, script: str) -> str:
    if script == "telu":
        return norm_telu(tok_text)
    if script == "deva":
        return norm_deva(tok_text)
    return skel(tok_text)
