"""Which home is this? Match a spoken employer name to one of the worker's homes without the LLM.

"శర్మ గారు", "शर्मा जी", "Sharma garu" and "sharma" all mean the home stored as "Sharma ji". Two steps:
1. the demo-name table (messages.NAME_SCRIPTS: every script a known name is written in), then
2. a consonant skeleton: Telugu / Devanagari letters are romanised to consonant classes (vowels, vowel signs and
   honorifics dropped), Latin names reduced the same way; equal skeletons of 2+ consonants match.
One tap on the suggested home then never creates a second Sharma ji.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional, Protocol

from .messages import NAME_SCRIPTS

HONORIFICS_LATN = {"ji", "jee", "garu", "gaaru", "gari", "madam", "madem", "mam", "maam", "sir", "saab", "sahab",
                   "saheb", "amma", "ammagaru", "aunty", "anty", "uncle", "babu", "bhai", "bhaiya", "didi", "mr",
                   "mrs", "ms", "shri", "sri", "smt", "ke", "ka", "ki", "ghar", "illu", "intlo", "family"}
HONORIFICS_NATIVE = {"గారు", "గారి", "గారికి", "గారింట్లో", "గారిల్లు", "మేడమ్", "మేడం", "అమ్మగారు", "అమ్మ", "సార్", "ఇంట్లో",
                     "జీ", "जी", "साहब", "साब", "मैडम", "मेडम", "सर", "आंटी", "भैया", "दीदी", "गारु", "के", "का", "की",
                     "घर", "श्री", "श्रीमती"}

# Consonant classes (aspirates folded into the plain stop, retroflex into dental, sibilants into s).
_TE = {"క": "k", "ఖ": "k", "గ": "g", "ఘ": "g", "ఙ": "n", "చ": "c", "ఛ": "c", "జ": "j", "ఝ": "j", "ఞ": "n",
       "ట": "t", "ఠ": "t", "డ": "d", "ఢ": "d", "ణ": "n", "త": "t", "థ": "t", "ద": "d", "ధ": "d", "న": "n",
       "ప": "p", "ఫ": "p", "బ": "b", "భ": "b", "మ": "m", "య": "y", "ర": "r", "ఱ": "r", "ల": "l", "ళ": "l",
       "వ": "v", "శ": "s", "ష": "s", "స": "s", "హ": "h", "ం": "n"}
_DEVA = {"क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "c", "छ": "c", "ज": "j", "झ": "j", "ञ": "n",
         "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n",
         "प": "p", "फ": "p", "ब": "b", "भ": "b", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
         "श": "s", "ष": "s", "स": "s", "ह": "h", "ं": "n", "ँ": "n", "ज़": "j", "फ़": "p", "क़": "k", "ख़": "k",
         "ग़": "g", "ड़": "d", "ढ़": "d"}
_LATN_DIGRAPHS = (("ksh", "ks"), ("sh", "s"), ("ch", "c"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("ph", "p"),
                  ("kh", "k"), ("gh", "g"), ("jh", "j"), ("ck", "k"), ("q", "k"), ("x", "ks"), ("z", "j"),
                  ("f", "p"), ("w", "v"))


class _Named(Protocol):
    id: Optional[int]
    name: str


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text or "")
    return [w for w in re.split(r"[\s,.;:!?()\"'“”‘’/-]+", text) if w]


def _strip_honorifics(words: list[str]) -> list[str]:
    out = []
    for w in words:
        lw = w.lower()
        if lw in HONORIFICS_LATN or w in HONORIFICS_NATIVE:
            continue
        for suf in ("గారు", "గారి", "జీ", "जी"):  # attached: "శర్మగారు"
            if w.endswith(suf) and len(w) > len(suf):
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def _skel_native(word: str, table: dict[str, str]) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", word):
        c = table.get(ch)
        if c:
            out.append(c)
    return "".join(out)


def _skel_latin(word: str) -> str:
    w = re.sub(r"[^a-z]", "", word.lower())
    for a, b in _LATN_DIGRAPHS:
        w = w.replace(a, b)
    return re.sub(r"[aeiouy]", "", w)


def _fold(s: str) -> str:
    s = s.replace("h", "")  # "Mehta" / "మెహతా" / "Meta": the h is spoken or not
    s = re.sub(r"(.)\1+", r"\1", s)  # doubled consonants: Reddy = Redy
    return re.sub(r"[yv]$", "", s)  # final glide: రావు = Rao


def skeleton(name: str) -> str:
    """Consonant skeleton of a name in any of the three scripts, honorifics removed."""
    parts = []
    for w in _strip_honorifics(_words(name)):
        if re.search(r"[ఀ-౿]", w):
            parts.append(_skel_native(w, _TE))
        elif re.search(r"[ऀ-ॿ]", w):
            parts.append(_skel_native(w, _DEVA))
        else:
            parts.append(_skel_latin(w))
    return _fold("".join(parts))


def _first_skeleton(name: str) -> str:
    words = _strip_honorifics(_words(name))
    return skeleton(words[0]) if words else ""


def _known_key(spoken: str) -> Optional[str]:
    """The Latin key of a demo name written in any script ("శర్మ గారు" -> "sharma ji")."""
    s = unicodedata.normalize("NFC", (spoken or "").strip())
    low = re.sub(r"\s+", " ", s.lower())
    for key, scripts in NAME_SCRIPTS.items():
        if low == key or s in scripts.values():
            return key
    return None


def match_home(spoken: str, homes: Iterable[_Named]) -> tuple[Optional[_Named], str]:
    """(home, method) for the spoken name; (None, "none") when nothing matches confidently."""
    homes = list(homes)
    if not (spoken or "").strip() or not homes:
        return None, "none"
    low = spoken.strip().lower()
    for h in homes:
        if h.name.strip().lower() == low:
            return h, "exact"
    key = _known_key(spoken)
    if key:
        target = skeleton(key)
        for h in homes:
            if _known_key(h.name) == key or skeleton(h.name) == target:
                return h, "script_table"
    sk = skeleton(spoken)
    if len(sk) >= 2:
        hits = [h for h in homes if skeleton(h.name) == sk or (_first_skeleton(h.name) == sk)]
        if len(hits) == 1:
            return hits[0], "skeleton"
    return None, "none"


__all__ = ["match_home", "skeleton"]
