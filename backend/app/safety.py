"""Safety switch: being locked in, beaten, ID taken, a minor working, trafficking -> stop the wage flow.

Keywords first (instant, offline, Telugu / Hindi / Hinglish / English). An optional LLM check can ADD flags the
keywords missed; it can never clear a keyword flag. When flagged, the app stops the wage flow and shows the
helplines and a quick-exit.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from . import llm

log = logging.getLogger("safety")

HELPLINES = [
    {"number": "112", "name": "Emergency (police, ambulance)", "for": ["locked_in", "violence", "trafficking"]},
    {"number": "181", "name": "Women Helpline", "for": ["violence", "harassment", "locked_in", "id_taken"]},
    {"number": "1098", "name": "Childline", "for": ["minor", "trafficking"]},
    {"number": "1800 833 9020", "name": "India Labourline (work and wage problems, Hyderabad desk)", "for": ["id_taken"]},
    {"number": None, "name": "NDWM (National Domestic Workers Movement)", "url": "https://ndwm.org", "for": []},
]

# Each pattern is searched case-insensitively in the raw transcript.
PATTERNS: dict[str, list[str]] = {
    "locked_in": [
        r"\block(?:ed)?\s+(?:me\s+)?(?:in|inside|up)\b", r"\bband\s+kar\s*(?:diya|dete|deti|ke|ke\s+rakh)",
        r"\bbahar\s+(?:nahi|nahin)\s+(?:jaane|nikalne)", r"\bghar\s+se\s+(?:nahi|nahin)\s+nikalne",
        r"\btaala\s+laga", r"\bnot\s+allowed\s+to\s+(?:go|leave)", r"\bbayataki\s+vellanivvaru",
        r"తాళం\s*వేసి", r"బయటకు\s*వెళ్ళనివ్వ", r"బయటికి\s*వెళ్లనివ్వ", r"లోపల\s*పెట్టి\s*తాళం",
        r"बंद\s*कर\s*(?:दिया|देते|देती|के)", r"बाहर\s*(?:नहीं|नही)\s*(?:जाने|निकलने)", r"ताला\s*लगा",
    ],
    "violence": [
        r"\bmaar(?:a|ta|te|ti|tey|aa|ke|pit|peet)\b", r"\bmaar\s+(?:diya|di|dete|deti|khaayi|khayi)\b", r"\bpeet(?:a|te|ti)\b", r"\bpitai\b", r"\bthappad\b",
        r"\bbeat(?:s|en|ing)?\b", r"\bhit\s+me\b", r"\bslap(?:ped)?\b", r"\bkottaru\b", r"\bkodataru\b",
        r"\bkottadu\b", r"\bkottindi\b", r"కొట్టారు", r"కొడతారు", r"కొట్టాడు", r"కొట్టింది", r"కొడుతు",
        r"मारा", r"मारते", r"मारती", r"पीटा", r"पीटते", r"थप्पड़",
    ],
    "id_taken": [
        r"\b(?:aadhaa?r|aadhar|adhar|id\s*card|ration\s*card|passport|phone|mobile|documents?)\b.{0,30}"
        r"\b(?:le\s+liya|le\s+li|rakh\s+liya|rakh\s+li|chheen|cheen|took|taken|kept|teesukunnaru|tiskunnaru|ivvatledu)",
        r"(?:ఆధార్|ఐడీ|ఫోన్|పాస్‌?పోర్ట్).{0,25}(?:తీసుకున్నారు|తీసేసుకున్నారు|ఇవ్వట్లేదు|ఇవ్వడం\s*లేదు|లాక్కున్నారు)",
        r"(?:आधार|पहचान\s*पत्र|फ़ोन|फोन|पासपोर्ट).{0,25}(?:ले\s*लिया|ले\s*ली|रख\s*लिया|रख\s*ली|छीन)",
    ],
    "minor": [
        r"\bminor\b", r"\bnaabalig\b", r"\bnabalig\b", r"\bchild\s+labou?r\b", r"\bbaal\s+majdoor\b",
        r"\b(?:[1-9]|1[0-7])\s*(?:saal|sal)\s+(?:ki|ka)\s+(?:ladki|ladka|bachchi|bachcha|beti|beta)",
        r"\b(?:[1-9]|1[0-7])\s*(?:years?|yrs)\s*old\b",
        r"\b(?:das|gyarah|barah|baarah|terah|chaudah|pandrah|solah|satrah)\s+saal\s+(?:ki|ka)\s+(?:ladki|ladka|bachchi|bachcha|beti|beta)",
        r"नाबालिग", r"बाल\s*मजदूर", r"(?:[1-9]|1[0-7])\s*साल\s*(?:की|का)\s*(?:लड़की|लड़का|बच्ची|बच्चा|बेटी|बेटा)",
        r"(?:[1-9]|1[0-7])\s*(?:ఏళ్ళ|ఏళ్ల|సంవత్సరాల)\s*(?:అమ్మాయి|అబ్బాయి|పిల్ల|పాప|బాబు)", r"బాల\s*కార్మిక",
    ],
    "trafficking": [
        r"\bbech\s+(?:diya|di|dete)\b", r"\bsold\s+me\b", r"\btraffick", r"\bbandhua\b", r"\bbonded\b",
        r"\bdebt\s+bondage\b", r"\bagent\s+ne\s+.{0,20}(?:bech|laaya|chhod)", r"\bvetti\s+chakiri\b",
        r"అమ్మేశారు", r"వెట్టి\s*చాకిరి", r"बेच\s*(?:दिया|दी)", r"बंधुआ",
    ],
    "harassment": [
        r"\bharass", r"\bchhed(?:a|ta|te|khani)\b", r"\bgalat\s+(?:tarah|jagah)\s+(?:se\s+)?chhu", r"\btouch(?:ed|es)?\s+me\b",
        r"छेड़", r"వేధింపు", r"వేధిస్తు",
    ],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in PATTERNS.items()}

CATEGORY_LABEL = {
    "locked_in": "Locked in or not allowed to leave", "violence": "Being hit or beaten",
    "id_taken": "ID or phone taken", "minor": "A child is working", "trafficking": "Sold or trafficked",
    "harassment": "Harassment",
}

LLM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": list(PATTERNS),
    "properties": {k: {"type": "boolean"} for k in PATTERNS},
}
LLM_SYSTEM = ("You check a domestic worker's words for danger. For each key answer true only if she clearly says it "
              "happens to her or to a child working: locked_in (kept locked in / not allowed to leave), violence "
              "(hit, beaten), id_taken (ID, Aadhaar, phone or documents taken and kept), minor (a child under 18 "
              "doing the work), trafficking (sold, bonded, brought by an agent and held), harassment (sexual "
              "harassment). Mentions of wages alone are false. JSON only.")


def keyword_check(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for cat, rxs in _COMPILED.items():
        for rx in rxs:
            m = rx.search(text or "")
            if m:
                hits.setdefault(cat, []).append(m.group(0).strip())
    return hits


def _result(cats: dict[str, list[str]], llm_cats: list[str]) -> dict[str, Any]:
    categories = sorted(set(cats) | set(llm_cats))
    flagged = bool(categories)
    helplines = [h for h in HELPLINES if not flagged or any(c in h["for"] for c in categories) or h["number"] in ("112",)
                 or h["name"].startswith("NDWM")]
    return {
        "flagged": flagged,
        "stop_wage_flow": flagged,
        "quick_exit": flagged,
        "categories": [{"key": c, "label": CATEGORY_LABEL[c], "matches": cats.get(c, []),
                        "via": "keyword" if c in cats else "llm"} for c in categories],
        "helplines": helplines if flagged else HELPLINES,
        "message": ("Your safety comes first. Baaki has paused the wage claim. Call 112 if you are in danger now."
                    if flagged else None),
    }


def check_sync(text: str) -> dict[str, Any]:
    return _result(keyword_check(text), [])


async def check(text: str, use_llm: bool = True) -> dict[str, Any]:
    cats = keyword_check(text)
    llm_cats: list[str] = []
    if use_llm and llm.configured() and len((text or "").strip()) >= 20:
        def validate(o):
            if not isinstance(o, dict) or any(not isinstance(o.get(k), bool) for k in PATTERNS):
                raise ValueError("bad safety json")
            return {"ok": True, **{k: o[k] for k in PATTERNS}}
        try:
            out = await llm.json_call(LLM_SYSTEM, text, LLM_SCHEMA, name="baaki_safety", validate=validate,
                                      max_tokens=200, timeout_s=8.0)
        except Exception as exc:  # never let the safety check break intake
            log.warning("safety llm failed: %s", str(exc)[:120])
            out = None
        if out:
            llm_cats = [k for k in PATTERNS if out.get(k)]
    return _result(cats, llm_cats)


__all__ = ["check", "check_sync", "keyword_check", "HELPLINES"]
