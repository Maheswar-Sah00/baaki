"""Translation between the worker's and the employer's languages (employer replies, statements).

The LLM translates; app.lang then re-extracts every rupee amount from the source and from the
translation, and they must match exactly (as a multiset). Otherwise, or with no LLM, a fixed
template in the target language frames the original words and lists the amounts it heard.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from . import llm
from .lang import extract_amounts
from .messages import amounts_in, fmt_money, money_words, name_in, norm_lang, parse_lang

log = logging.getLogger("translate")

LANG_NAME = {
    "hi-en": {"hi-en": "Hinglish", "te-IN": "హిందీ", "en": "Hindi"},
    "te-IN": {"hi-en": "తెలుగు", "te-IN": "తెలుగు", "en": "Telugu"},
    "en": {"hi-en": "English", "te-IN": "ఇంగ్లీష్", "en": "English"},
}
TARGET_DESC = {
    "hi-en": "Hinglish in Devanagari script (simple spoken Hindi; common English words like salary, payment may stay in Latin)",
    "te-IN": "simple spoken Telugu in Telugu script",
    "en": "simple Indian English",
}
SCHEMA = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}
_RUPEE = re.compile(r"₹\s?(\d[\d,]*(?:\.\d+)?)")


@dataclass
class Translation:
    text: str                 # shown to the reader
    speech: list[str]         # spoken (amounts as words), framing included
    source: str               # llm | template
    amounts: list[int]
    checks: dict[str, Any] = field(default_factory=dict)


def _amounts(text: str, lang: str) -> list[int]:
    return [int(round(a)) for a in amounts_in(text, lang)]


def speakable(text: str, lang: str) -> str:
    """Amounts written with digits (₹13,000, 12,000 రూపాయలు, Rs 500) -> words in the target language, for
    Timbre (04_gnani_feasibility: words are the safe input, above all for Telugu)."""
    out = text
    for a in sorted(extract_amounts(text, parse_lang(lang)), key=lambda a: a["start"], reverse=True):
        if any(ch.isdigit() for ch in a["source_text"]):
            out = out[:a["start"]] + money_words(float(a["amount_inr"]), lang) + out[a["end"]:]
    return _RUPEE.sub(lambda m: money_words(float(m.group(1).replace(",", "")), lang), out)


FRAME = {
    "hi-en": ("{who} का जवाब आया है।", "उन्होंने कहा:", "इसमें बताई गई रकम: {amounts}।",
              "उनकी पूरी बात screen पर लिखी है।"),
    "te-IN": ("{who} సమాధానం ఇచ్చారు.", "వారు ఇలా చెప్పారు:", "అందులో చెప్పిన మొత్తం: {amounts}.",
              "వారి పూర్తి మాటలు స్క్రీన్ మీద ఉన్నాయి."),
    "en": ("{who} has replied.", "They said:", "Amounts mentioned: {amounts}.", "Their full words are on the screen."),
}
LABEL = {"hi-en": "Baaki अनुवाद।", "te-IN": "బాకీ అనువాదం.", "en": "Baaki translation."}


async def translate(text: str, src_lang: str, dst_lang: str, *, speaker: str | None = None,
                    use_llm: bool = True) -> Translation:
    """Translate `text` (src_lang) for a listener of dst_lang, with amount verification.

    `speaker` (e.g. the employer's name) adds a framing sentence: "Sharma ji has replied."""
    src, dst = norm_lang(src_lang), norm_lang(dst_lang)
    text = (text or "").strip()
    src_amounts = sorted(_amounts(text, src))
    who = name_in(speaker, dst) if speaker else None
    frame, said, amounts_tpl, full = FRAME[dst]
    checks: dict[str, Any] = {"source_amounts": src_amounts}

    if src == dst and text:
        body = text
        speech = [*( [frame.format(who=who)] if who else []), speakable(body, dst)]
        return Translation(body, [LABEL[dst], *speech], "same_language", src_amounts, checks)

    if use_llm and text and llm.configured():
        system = (
            f"Translate what a person said into {TARGET_DESC[dst]}. The speaker is usually a household employer "
            "replying about a domestic worker's wages, and the listener is the worker. Translate the meaning "
            "faithfully and completely (for example Hindi 'X ko bolo' means 'tell X', not 'call X'); do not add, "
            "soften or drop anything, and do not answer it. Write every money amount as digits with the rupee sign, "
            "for example ₹13,000, and keep names as they are. Return JSON {\"translation\": \"...\"}."
        )

        def validate(out: Any) -> str:
            t = (out or {}).get("translation") if isinstance(out, dict) else None
            if not isinstance(t, str) or not t.strip() or len(t) > 4 * len(text) + 200:
                raise ValueError("bad translation")
            got = sorted(_amounts(t, dst))
            if got != src_amounts:
                raise ValueError(f"amount mismatch {got} != {src_amounts}")
            return t.strip()

        try:
            out = await llm.json_call(system, json.dumps({"text": text}, ensure_ascii=False), SCHEMA,
                                      name="translation", validate=validate, max_tokens=900)
        except Exception as exc:
            log.warning("translation failed: %s", str(exc)[:120])
            out = None
        if out:
            checks["translation_amounts"] = sorted(_amounts(out, dst))
            speech = [LABEL[dst], *([frame.format(who=who)] if who else []), speakable(out, dst)]
            return Translation(out, speech, "llm", src_amounts, checks)
        checks["llm"] = "unavailable or rejected"

    # Template fallback: frame + amounts in the listener's language; the original words are shown.
    amt_disp = ", ".join(fmt_money(a) for a in src_amounts)
    amt_speech = ", ".join(money_words(a, dst) for a in src_amounts)
    lines_d = [frame.format(who=who) if who else "", f"{said} “{text}”" if text else ""]
    lines_s = [LABEL[dst], frame.format(who=who) if who else ""]
    if src_amounts:
        lines_d.append(amounts_tpl.format(amounts=amt_disp))
        lines_s.append(amounts_tpl.format(amounts=amt_speech))
    lines_s.append(full)
    return Translation(" ".join(x for x in lines_d if x), [x for x in lines_s if x], "template", src_amounts, checks)


def lang_name(lang: str, in_lang: str) -> str:
    return LANG_NAME[norm_lang(lang)][norm_lang(in_lang)]


def counter_equal(a: list[int], b: list[int]) -> bool:
    return Counter(a) == Counter(b)
