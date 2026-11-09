"""G13: the consent sentence she repeats (te-IN, hi-en, en) and the fuzzy matcher that checks a transcript.

The same recording is the consent record and the voice-clone sample, so the sentence is written to take
about 12-16 s when read slowly (the clone needs 10-20 s).

Matching (deterministic, no LLM):
  * every word goes through one "skeleton": Telugu -> Devanagari by Unicode offset (the two blocks share a
    layout), Devanagari -> rough Latin, then lower case, aspiration "h" after a consonant dropped, every vowel
    but a word-initial one dropped, look-alike letters folded (f->p, z->j, w->v, q->k, x->ks, sh->s, ch->c).
    So "Lakshmi", "లక్ష్మి" and "लक्ष्मी" all become "lksm", whichever script Prisma writes.
  * a target word matches if any transcript token (or two adjacent tokens joined) is equal after
    normalising, or its skeleton is similar enough (difflib ratio), or starts with the target's skeleton.
  * pass = her name heard AND at least 70% of the content words heard.
The result lists every word with matched true/false, so the screen can turn words green or grey.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

PASS_RATIO = 0.70      # share of content words that must be heard
WORD_SIM = 0.72        # skeleton similarity for a content word
NAME_SIM = 0.75        # skeleton similarity for her name
MIN_PREFIX = 3         # a token starting with the target skeleton (Telugu case endings) counts if >= 3 letters

LANGS = ("te-IN", "hi-en", "en")
LANG_ALIASES = {"te": "te-IN", "te-in": "te-IN", "telugu": "te-IN",
                "hi": "hi-en", "hi-in": "hi-en", "hindi": "hi-en", "hi-en": "hi-en", "hinglish": "hi-en",
                "en": "en", "en-in": "en", "english": "en"}
# Prisma: never `transcribe` with several languages (it drops numbers); codemix is used for the presets.
STT_ARGS = {"te-IN": ("te", "codemix"), "hi-en": ("hinglish", "codemix"), "en": ("en-IN", "transcribe")}
TTS_LANG = {"te-IN": "te-IN", "hi-en": "hi-en", "en": "en-IN"}

# "*" marks a content word (counted); "{name}" is her name; everything else is a filler word (shown, not counted).
TEMPLATES = {
    "te-IN": "నా పేరు {name}. నా *గొంతుతో నా *యజమానులకు *సందేశాలు *పంపడానికి *బాకీకి *అనుమతి *ఇస్తున్నాను. "
             "*ప్రతి *సందేశం *ముందు ఇది *AI *సందేశం అని *చెబుతుంది. నేను *ఎప్పుడైనా దీన్ని *తొలగించవచ్చు.",
    "hi-en": "मेरा नाम {name} है। मैं *Baaki को अपनी *आवाज़ में मेरे *employers को *message *भेजने की *अनुमति *देती हूँ। "
             "*हर *message *पहले *बताएगा कि यह *AI *message है। मैं इसे *कभी भी *delete कर *सकती हूँ।",
    "en": "My name is {name}. I *allow *Baaki to *send *messages to my *employers in my *voice. "
          "*Every *message will *first *say that it is an *AI *message. I can *delete this at any *time.",
}
MEANING_EN = ("My name is {name}. I allow Baaki to send messages to my employers in my voice. Every message will "
              "first say that it is an AI message. I can delete this at any time.")

# Spellings Prisma may write instead of the display word (other script, English loanwords, split words).
VARIANTS: dict[str, list[str]] = {
    "బాకీకి": ["baaki", "baki", "బాకీ", "బాకి"],
    "AI": ["ai", "a.i", "ఏఐ", "ఎఐ", "ఏఈ", "एआई", "ए.आई", "एआइ"],
    "Baaki": ["baaki", "baki", "बाकी", "बाक़ी", "बाक़ि", "बाकि"],
    "employers": ["employer", "एम्प्लॉयर", "एंप्लॉयर", "एम्प्लोयर", "इम्प्लॉयर", "एम्प्लॉयर्स", "एंप्लॉयर्स"],
    "message": ["messages", "massage", "मैसेज", "मेसेज", "मैसेजेस"],
    "messages": ["message", "मैसेज", "मेसेज"],
    "delete": ["डिलीट", "डिलिट", "delet"],
    "आवाज़": ["आवाज", "awaaz", "awaz", "aawaz"],
    "సందేశం": ["సందేశము", "సందేశాలు", "message", "మెసేజ్"],
    "సందేశాలు": ["సందేశం", "messages", "మెసేజ్‌లు", "మెసేజ్లు"],
    "యజమానులకు": ["యజమానికి", "యజమానులు", "employers", "ఎంప్లాయర్"],
}

# Her name written the way Prisma tends to write it in each script (synthetic demo names only).
KNOWN_NAMES: dict[str, dict[str, str]] = {
    "lakshmi": {"te-IN": "లక్ష్మి", "hi-en": "लक्ष्मी", "en": "Lakshmi"},
    "rafiq": {"te-IN": "రఫీక్", "hi-en": "रफ़ीक़", "en": "Rafiq"},
}
NAME_VARIANTS: dict[str, list[str]] = {
    "lakshmi": ["laxmi", "lakhsmi", "లక్ష్మీ", "लक्ष्मि", "लछमी"],
    "rafiq": ["rafeeq", "rafik", "రఫీఖ్", "रफीक", "रफ़ीक"],
}

# --------------------------------------------------------------------------- transliteration
_TE_START, _TE_END, _OFFSET = 0x0C00, 0x0C7F, 0x0300
_VIRAMA = "्"
_DEV_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "ऩ": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ऱ": "r", "ल": "l",
    "ळ": "l", "ऴ": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    "क़": "k", "ख़": "kh", "ग़": "g", "ज़": "j", "ड़": "r", "ढ़": "rh", "फ़": "p", "य़": "y",
}
_DEV_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri", "ॠ": "ri", "ऌ": "li",
    "ऍ": "e", "ऎ": "e", "ए": "e", "ऐ": "ai", "ऑ": "o", "ऒ": "o", "ओ": "o", "औ": "au",
}
_DEV_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "ृ": "ri", "ॄ": "ri", "ॅ": "e", "ॆ": "e", "े": "e",
    "ै": "ai", "ॉ": "o", "ॊ": "o", "ो": "o", "ौ": "au",
}
_DEV_MARKS = {"ं": "n", "ँ": "n", "ः": "h", "़": "", "ఁ": "n"}


def _te_to_dev(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if _TE_START <= cp <= _TE_END and cp not in (0x0C55, 0x0C56):
            out.append(chr(cp - _OFFSET))
        elif cp in (0x0C55, 0x0C56):     # Telugu length marks: no Devanagari twin, no sound change we need
            continue
        else:
            out.append(ch)
    return "".join(out)


def to_latin(text: str) -> str:
    """Telugu / Devanagari / Latin -> rough lower-case Latin (good enough to compare, not to display)."""
    text = unicodedata.normalize("NFC", _te_to_dev(text))
    out: list[str] = []
    pending_a = False                    # a consonant's inherent "a" not yet written
    for ch in text:
        if ch in _DEV_CONS:
            if pending_a:
                out.append("a")
            out.append(_DEV_CONS[ch])
            pending_a = True
        elif ch in _DEV_MATRAS:
            out.append(_DEV_MATRAS[ch])
            pending_a = False
        elif ch == _VIRAMA:
            pending_a = False
        elif ch in _DEV_VOWELS:
            if pending_a:
                out.append("a")
            out.append(_DEV_VOWELS[ch])
            pending_a = False
        elif ch in _DEV_MARKS:
            if pending_a and _DEV_MARKS[ch]:
                out.append("a")
                pending_a = False
            out.append(_DEV_MARKS[ch])
        else:
            if pending_a:
                out.append("a")
                pending_a = False
            out.append(ch.lower())
    if pending_a:
        out.append("a")
    return "".join(out)


_VOWELS = set("aeiou")


def skeleton(word: str) -> str:
    """Consonant skeleton of one word in any of the three scripts."""
    s = re.sub(r"[^a-z]", "", to_latin(word))
    if not s:
        return ""
    s = s.replace("sh", "s").replace("ch", "c").replace("x", "ks")
    s = s.translate(str.maketrans({"f": "p", "z": "j", "w": "v", "q": "k"}))
    out: list[str] = []
    for i, ch in enumerate(s):
        if ch == "h" and i > 0 and s[i - 1] not in _VOWELS:
            continue                      # aspiration: kh -> k, th -> t, bh -> b
        if ch in _VOWELS and i > 0:
            continue
        if out and out[-1] == ch:
            continue                      # doubled letters
        out.append(ch)
    return "".join(out)


_PUNCT = re.compile(r"[\s.,!?;:\"'“”‘’()\[\]{}…।॥\-–—/\\|]+")


def norm_word(word: str) -> str:
    """Lower case, NFC, no punctuation and no zero-width joiners."""
    w = unicodedata.normalize("NFC", word).replace("‌", "").replace("‍", "").lower()
    return _PUNCT.sub("", w)


def tokens(transcript: str) -> list[str]:
    return [t for t in (norm_word(x) for x in _PUNCT.split(transcript or "")) if t]


# --------------------------------------------------------------------------- consent text
def norm_lang(lang: str | None) -> str:
    return LANG_ALIASES.get((lang or "").strip().lower(), "te-IN")


def lang_for_worker(worker_lang: str | None, lang: str | None = None) -> str:
    """An explicit lang wins; else the worker's own language."""
    return norm_lang(lang) if lang else norm_lang(worker_lang)


def display_name(name: str, lang: str) -> str:
    known = KNOWN_NAMES.get(norm_word(name))
    return known[lang] if known else name.strip()


@dataclass
class Word:
    i: int
    text: str                 # as shown (with punctuation)
    kind: str                 # name | content | filler
    key: str                  # display word without punctuation / "*"
    variants: list[str] = field(default_factory=list)


def words_for(name: str, lang: str) -> list[Word]:
    lang = norm_lang(lang)
    shown = display_name(name, lang)
    out: list[Word] = []
    for raw in TEMPLATES[lang].split():
        if "{name}" in raw:
            text = raw.replace("{name}", shown)
            nk = norm_word(name)
            out.append(Word(len(out), text, "name", shown,
                            [name, shown, *KNOWN_NAMES.get(nk, {}).values(), *NAME_VARIANTS.get(nk, [])]))
            continue
        content = raw.startswith("*")
        text = raw.lstrip("*")
        key = _PUNCT.sub("", text)
        out.append(Word(len(out), text, "content" if content else "filler", key, VARIANTS.get(key, [])))
    return out


def consent_sentence(name: str, lang: str) -> str:
    return " ".join(w.text for w in words_for(name, lang))


def sentences(name: str, lang: str) -> list[str]:
    text = consent_sentence(name, lang)
    return [p.strip() for p in re.split(r"(?<=[.।])\s+", text) if p.strip()]


def speech_text(name: str, lang: str) -> str:
    """What Timbre says for the prompt: slow, with a pause after each sentence (fixed, so it caches)."""
    return "<slow> " + " <pauses> ".join(sentences(name, lang))


def meaning_en(name: str) -> str:
    return MEANING_EN.format(name=name.strip())


# --------------------------------------------------------------------------- matching
def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _word_score(word: Word, cands: list[tuple[str, str]], threshold: float) -> tuple[float, str | None]:
    """Best (score, heard token) for one target word against candidate (norm, skeleton) pairs."""
    targets = [(norm_word(v), skeleton(v)) for v in [word.key, *word.variants] if norm_word(v)]
    best, heard = 0.0, None
    for tn, ts in targets:
        for cn, cs in cands:
            if cn == tn:
                return 1.0, cn
            if len(ts) < 2 or len(cs) < 2:
                continue                  # one-letter skeletons ("AI", "నా") must match exactly
            score = _sim(ts, cs)
            if len(ts) >= MIN_PREFIX and cs.startswith(ts):
                score = max(score, threshold)
            if score > best:
                best, heard = score, cn
    return best, heard


def match(transcript: str, name: str, lang: str) -> dict[str, Any]:
    """Check a transcript against her consent sentence. Never raises on odd input."""
    lang = norm_lang(lang)
    toks = tokens(transcript)
    cands = [(t, skeleton(t)) for t in toks]
    cands += [(a + b, skeleton(a + b)) for a, b in zip(toks, toks[1:])]   # split words: "బాకీ కి"
    out_words: list[dict[str, Any]] = []
    name_ok, n_content, n_hit = False, 0, 0
    for w in words_for(name, lang):
        row: dict[str, Any] = {"i": w.i, "text": w.text, "kind": w.kind, "matched": None}
        if w.kind in ("content", "name"):
            thr = NAME_SIM if w.kind == "name" else WORD_SIM
            score, heard = _word_score(w, cands, thr)
            ok = score >= thr
            row.update(matched=ok, score=round(score, 2), heard=heard if ok else None)
            if w.kind == "name":
                name_ok = ok
            else:
                n_content += 1
                n_hit += int(ok)
        out_words.append(row)
    ratio = n_hit / n_content if n_content else 0.0
    passed = bool(name_ok and ratio >= PASS_RATIO)
    missed = [_PUNCT.sub("", w["text"]) for w in out_words if w["matched"] is False]
    return {
        "passed": passed,
        "lang": lang,
        "name_matched": name_ok,
        "content_matched": n_hit,
        "content_total": n_content,
        "ratio": round(ratio, 3),
        "threshold": PASS_RATIO,
        "words": out_words,
        "missed": missed,
        "reason": None if passed else ("name_not_heard" if not name_ok else "too_few_words"),
    }


def blank_words(name: str, lang: str) -> list[dict[str, Any]]:
    """The karaoke list before she has spoken (matched=None everywhere)."""
    return [{"i": w.i, "text": w.text, "kind": w.kind, "matched": None} for w in words_for(name, lang)]
