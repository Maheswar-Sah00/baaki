"""Transcript -> case facts. The LLM structures; the parsers own every rupee.

Flow:
1. app.meter (deterministic) finds every amount (app.lang.amounts), month / day / hour counts and a first guess
   at what each amount is.
2. If an LLM is configured, app.llm.json_call gets the transcript plus the numbered amount list and returns ONLY
   structure: employer name, work type, hours, months, and a ROLE for each amount id. It never returns a rupee
   value; any id it invents is dropped.
3. Cross-check: counts the LLM gives are compared with the parser counts (the parser wins and a warning is
   recorded); month names it lists must appear in the transcript.
4. LLM_PROVIDER=none, no key, a timeout or invalid JSON -> parser-only facts, so the demo never dies.
Every fact is read back to the worker and confirmed before it is used.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from . import llm
from .lang._text import norm_deva, norm_telu, skel
from .meter import MONTH_NAMES, UNPAID_RE, meter, months_named

log = logging.getLogger("extract")

WORK_TYPES = ["housekeeping", "cooking", "childcare", "eldercare", "other", "unknown"]
ROLES = ["monthly_wage", "deduction", "advance", "paid_per_month", "paid_lump", "stated_total", "owed_lump", "other"]
REASONS = ["sick", "employer_away", "breakage", "fine", "advance", "other", "none"]

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["employer_name", "work_type", "hours_per_day", "days_per_week", "months_unpaid",
                 "unpaid_month_names", "dismissed", "amount_roles", "reasons"],
    "properties": {
        "employer_name": {"type": ["string", "null"]},
        "work_type": {"type": "string", "enum": WORK_TYPES},
        "hours_per_day": {"type": ["number", "null"]},
        "days_per_week": {"type": ["number", "null"]},
        "months_unpaid": {"type": ["integer", "null"]},
        "unpaid_month_names": {"type": "array", "items": {"type": "string"}},
        "dismissed": {"type": "boolean"},
        "amount_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "role", "reason", "days_absent"],
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string", "enum": ROLES},
                    "reason": {"type": "string", "enum": REASONS},
                    "days_absent": {"type": ["number", "null"]},
                },
            },
        },
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = """You structure what a domestic worker in Hyderabad said about wages owed by ONE employer.
The transcript may be Telugu, Hindi, Hinglish or English, in any script. You get a numbered list of the
amounts that were already found by a rule-based parser. NEVER write a rupee amount yourself: only give each
amount id a role. Roles: monthly_wage (her agreed salary per month), deduction (money cut from her pay),
advance (an advance she took), paid_per_month (what the employer actually pays each month when it is less
than agreed or is simply her pay), paid_lump (a one-off payment received), stated_total (a total she said),
owed_lump (a one-off sum owed), other. For a deduction give the reason: sick (her own sickness or leave),
employer_away (the family was away), breakage, fine, advance, other; and days_absent if she said it.
months_unpaid = number of months with no salary at all (null if not said). unpaid_month_names = month names
she said for unpaid months, in English. hours_per_day and days_per_week only if she said them.
employer_name = the name she used for the employer, with honorific (e.g. "Sharma ji", "Reddy garu").
work_type: housekeeping (cleaning, vessels, washing, sweeping), cooking, childcare, eldercare, other, or unknown.
dismissed = true only if she says she was removed or told to stop coming. reasons = short English notes of
why pay was held back, in her words. Give a role for EVERY amount id.
Answer with JSON only, exactly these keys:
{"employer_name": string or null, "work_type": "housekeeping"|"cooking"|"childcare"|"eldercare"|"other"|"unknown",
 "hours_per_day": number or null, "days_per_week": number or null, "months_unpaid": integer or null,
 "unpaid_month_names": [string], "dismissed": boolean,
 "amount_roles": [{"id": "c1", "role": "monthly_wage", "reason": "none", "days_absent": null}],
 "reasons": [string]}"""

_HONORIFIC_LATIN = r"(?:ji|jee|garu|gaaru|garu|madam|madem|mam|maam|sir|saab|sahab|saheb|aunty|uncle|amma|ammagaru|sethji)"
_NAME_LATIN = re.compile(rf"\b([A-Z][a-z]{{2,}}|[a-z]{{3,}})\s+({_HONORIFIC_LATIN})\b")
_NAME_TE = re.compile(r"([ఀ-౿]{2,})\s*(గారు|గారి|గారికి|గారింట్లో|గారిల్లు|గారింటి|మేడమ్|సార్)")
_NAME_DEVA = re.compile(r"([ऀ-ॿ]{2,})\s*(जी|मैडम|साहब|आंटी)(?![ऀ-ॿ])")
_NOT_NAMES = {skel(w) for w in ["haan", "nahi", "accha", "theek", "mera", "meri", "unke", "unki", "wahan", "ammo",
                                "bolo", "suno", "ok", "the", "and", "aur", "baaki", "salary", "kaam"]}

WORK_HINTS = {
    "cooking": ["cook", "cooking", "khana", "khaana", "vanta", "vantalu", "rasoi", "chapati", "roti", "खाना",
                "रसोई", "వంట", "వంటలు"],
    "childcare": ["baby", "bacche", "bachcha", "baccha", "pillalu", "children", "child", "बच्चे", "బాబు", "పిల్లలు",
                  "పిల్లల"],
    "eldercare": ["dadi", "nani", "old", "elder", "patient", "ammamma", "nanamma", "బామ్మ"],
    "housekeeping": ["jhadu", "pocha", "pochha", "bartan", "clean", "cleaning", "maid", "safai", "kaam", "pani",
                     "ginnelu", "batta", "బట్టలు", "గిన్నెలు", "పని", "ఇల్లు", "झाड़ू", "पोछा", "बर्तन", "सफाई",
                     "vessels", "washing", "sweeping"],
}


# --------------------------------------------------------------------------- parser-only pieces
_NEGATED_AFTER = re.compile(r"^\s*[,.]?\s*(?:కాదు|nahi|nahin|not|kaadu|kadu|नहीं|नही)", re.IGNORECASE)


def find_employer_name(text: str) -> str | None:
    """'Sharma ji', 'Reddy garu', 'శర్మ గారు'. A name followed by 'not' ("Reddy garu kaadu, Sharma ji") is skipped."""
    for rx in (_NAME_TE, _NAME_DEVA):
        for m in rx.finditer(text):
            if _NEGATED_AFTER.match(text[m.end():]):
                continue
            return f"{m.group(1)} {m.group(2)}"
    for m in _NAME_LATIN.finditer(text):
        if skel(m.group(1)) in _NOT_NAMES or _NEGATED_AFTER.match(text[m.end():]):
            continue
        name = m.group(1)
        return f"{name[0].upper()}{name[1:]} {m.group(2).lower()}"
    return None


def guess_work_type(text: str) -> str:
    low = text.lower()
    for wt in ("cooking", "childcare", "eldercare", "housekeeping"):
        if any(h in low for h in WORK_HINTS[wt]):
            return wt
    return "housekeeping"


_UNPAID_RE = UNPAID_RE


def _norm_name(s: str) -> str:
    if any("ఀ" <= c <= "౿" for c in s):
        return norm_telu(s)
    if any("ऀ" <= c <= "ॿ" for c in s):
        return norm_deva(s)
    return skel(s)


def facts_from_meter(text: str, m: dict[str, Any]) -> dict[str, Any]:
    """Parser-only facts (no LLM): the meter's own chip facts (the same ones its total comes from) plus the
    employer name and work type. Month names come through the meter's month chip."""
    f = dict(m["facts"])
    unclear = bool(f.get("months_unclear"))
    if f.get("monthly_wage") and not f.get("months_unpaid") and not f.get("paid_per_month") and UNPAID_RE.search(text):
        unclear = True  # "salary nahi mili" with a wage but no months: the read-back asks how many
    return {
        "employer_name": find_employer_name(text),
        "work_type": guess_work_type(text),
        "hours_per_day": f["hours_per_day"],
        "hours_known": bool(f["hours_per_day"]),
        "days_per_week": None,
        "monthly_wage": f["monthly_wage"],
        "paid_per_month": f["paid_per_month"],
        "months_unpaid": f["months_unpaid"],
        "unpaid_month_numbers": f["unpaid_month_numbers"],
        "deductions": f["deductions"],
        "advance_outstanding": f["advance_outstanding"] or 0,
        "owed_lumps": f["owed_lumps"],
        "paid_lumps": f["paid_lumps"],
        "stated_total": f["stated_total"],
        "months_unclear": unclear,
        "dismissed": False,
        "reasons": [],
    }


# --------------------------------------------------------------------------- LLM output validation
def validate_llm(out: Any, chip_ids: set[str]) -> dict[str, Any]:
    """Raise on structurally bad output; return a cleaned dict. Unknown ids / enum values are dropped."""
    if not isinstance(out, dict):
        raise ValueError("not an object")
    clean: dict[str, Any] = {}
    name = out.get("employer_name")
    clean["employer_name"] = name.strip()[:60] if isinstance(name, str) and name.strip() else None
    wt = out.get("work_type")
    clean["work_type"] = wt if wt in WORK_TYPES else "unknown"

    def num(v, lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        return float(v) if lo <= v <= hi else None

    clean["hours_per_day"] = num(out.get("hours_per_day"), 0.5, 16)
    clean["days_per_week"] = num(out.get("days_per_week"), 1, 7)
    mu = out.get("months_unpaid")
    clean["months_unpaid"] = int(mu) if isinstance(mu, int) and not isinstance(mu, bool) and 0 <= mu <= 36 else None
    names = out.get("unpaid_month_names") or []
    clean["unpaid_month_names"] = [str(n)[:20] for n in names if isinstance(n, str)][:36]
    clean["dismissed"] = bool(out.get("dismissed") is True)
    roles = []
    for r in out.get("amount_roles") or []:
        if not isinstance(r, dict) or r.get("id") not in chip_ids or r.get("role") not in ROLES:
            continue
        reason = r.get("reason") if r.get("reason") in REASONS else "other"
        roles.append({"id": r["id"], "role": r["role"], "reason": reason,
                      "days_absent": num(r.get("days_absent"), 0.5, 31)})
    clean["amount_roles"] = roles
    clean["reasons"] = [str(x)[:120] for x in (out.get("reasons") or []) if isinstance(x, str)][:6]
    if "amount_roles" not in out or not isinstance(out.get("amount_roles"), list):
        raise ValueError("amount_roles missing")
    return clean


def _month_number(name: str) -> int | None:
    low = name.strip().lower()
    for n, names in MONTH_NAMES.items():
        if low in names or low[:3] == names[0][:3]:
            return n
    return None


def merge(text: str, m: dict[str, Any], base: dict[str, Any], llm_out: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Parser facts + LLM structure. Rupee values always come from the parser chips."""
    warnings: list[str] = []
    facts = dict(base)
    chips = {c["id"]: c for c in m["chips"] if not c.get("is_count")}
    by_role: dict[str, list[tuple[dict, dict]]] = {}
    for r in llm_out["amount_roles"]:
        by_role.setdefault(r["role"], []).append((r, chips[r["id"]]))

    if by_role.get("monthly_wage"):
        val = by_role["monthly_wage"][-1][1]["value"]
        if base["monthly_wage"] not in (None, val):
            warnings.append(f"monthly wage: words suggest {base['monthly_wage']}, structure suggests {val}; using {val}")
        facts["monthly_wage"] = val
    if by_role.get("paid_per_month"):
        val = by_role["paid_per_month"][-1][1]["value"]
        if facts["monthly_wage"] is None:
            facts["monthly_wage"] = val
        elif val != facts["monthly_wage"]:
            facts["paid_per_month"] = val
    if "deduction" in by_role:
        facts["deductions"] = []
        for r, c in by_role["deduction"]:
            reason = r["reason"] if r["reason"] not in ("none",) else (c.get("reason") or "other")
            days = r["days_absent"] if r["days_absent"] is not None else (m["days"] if reason == "sick" else None)
            if r["days_absent"] is not None and m["days"] is not None and r["days_absent"] != m["days"]:
                warnings.append(f"days absent: structure said {r['days_absent']:g}, words say {m['days']}; using {m['days']}")
                days = m["days"]
            facts["deductions"].append({"amount": c["value"], "reason": reason, "days_absent": days})
    if "advance" in by_role:
        facts["advance_outstanding"] = sum(c["value"] for _, c in by_role["advance"])
    if "owed_lump" in by_role:
        facts["owed_lumps"] = [c["value"] for _, c in by_role["owed_lump"]]
    # a payment she received: the LLM's role wins for chips it named; parser lumps it gave no role stay
    role_of = {r["id"]: r["role"] for r in llm_out["amount_roles"]}
    facts["paid_lumps"] = [c["value"] for cid, c in chips.items()
                           if role_of.get(cid) == "paid_lump"
                           or (cid not in role_of and c["kind"] == "paid" and not (c.get("per_month") or c.get("habitual")))]
    if facts.get("paid_per_month") is not None and facts["paid_per_month"] == facts.get("monthly_wage"):
        facts["paid_per_month"] = None
    if "stated_total" in by_role:
        facts["stated_total"] = by_role["stated_total"][-1][1]["value"]

    # counts: the parser wins; LLM-only month counts must be backed by month names in the transcript
    mu = llm_out["months_unpaid"]
    if m["months_unpaid"] is not None:
        if mu is not None and mu != m["months_unpaid"]:
            warnings.append(f"months unpaid: structure said {mu}, words say {m['months_unpaid']}; using {m['months_unpaid']}")
    else:
        named = months_named(text)
        nums = [n for n in (_month_number(x) for x in llm_out["unpaid_month_names"]) if n is not None]
        backed = [n for n in nums if n in named]
        if backed:
            facts["unpaid_month_numbers"] = sorted(set(backed))
            facts["months_unpaid"] = len(set(backed))
            if mu is not None and mu != len(set(backed)):
                warnings.append(f"months unpaid: structure said {mu}, month names give {len(set(backed))}")
        elif mu is not None:
            facts["months_unpaid"] = mu
            warnings.append("months unpaid came from the structure step only; confirm it in the read-back")

    if m["hours_per_day"] is not None:
        if llm_out["hours_per_day"] is not None and llm_out["hours_per_day"] != m["hours_per_day"]:
            warnings.append(f"hours: structure said {llm_out['hours_per_day']:g}, words say {m['hours_per_day']}")
    elif llm_out["hours_per_day"] is not None:
        facts["hours_per_day"] = llm_out["hours_per_day"]
        warnings.append("hours a day came from the structure step only; confirm it in the read-back")
    if llm_out["days_per_week"] is not None:
        facts["days_per_week"] = llm_out["days_per_week"]
    facts["hours_known"] = bool(facts.get("hours_per_day"))
    if facts.get("months_unpaid"):
        facts["months_unclear"] = False

    name = llm_out["employer_name"]
    if name:
        first = name.split()[0]
        if _norm_name(first) and (_norm_name(first) in _norm_name(text) or first.lower() in text.lower()):
            facts["employer_name"] = name
        elif not facts["employer_name"]:
            facts["employer_name"] = name
            warnings.append("employer name not found word-for-word in the transcript; confirm it")
    if llm_out["work_type"] != "unknown":
        facts["work_type"] = llm_out["work_type"]
    facts["dismissed"] = llm_out["dismissed"]
    facts["reasons"] = llm_out["reasons"]
    return facts, warnings


def _user_prompt(text: str, m: dict[str, Any]) -> str:
    lines = [f"Transcript: {text}", "", "Amounts found by the parser (id: words -> rupees):"]
    for c in m["chips"]:
        if not c.get("is_count"):
            lines.append(f"- {c['id']}: \"{c['text']}\" -> {c['value']}")
    counts = [c for c in m["chips"] if c.get("is_count")]
    if counts:
        lines.append("Counts found: " + "; ".join(f"\"{c['text']}\" = {c['value']} {c['kind']}" for c in counts))
    return "\n".join(lines)


async def extract_facts(text: str, lang: str | None = None, use_llm: bool = True) -> dict[str, Any]:
    """Transcript -> {facts, meter, source, warnings}. Never raises for LLM trouble."""
    m = meter(text, lang)
    base = facts_from_meter(text, m)
    facts, warnings, source = base, [], "parser"
    if use_llm and llm.configured() and text.strip():
        chip_ids = {c["id"] for c in m["chips"] if not c.get("is_count")}
        try:
            out = await llm.json_call(SYSTEM, _user_prompt(text, m), SCHEMA, name="baaki_facts",
                                      validate=lambda o: validate_llm(o, chip_ids), max_tokens=900)
        except Exception as exc:  # defensive: json_call already swallows provider errors
            log.warning("extract llm failed: %s", str(exc)[:120])
            out = None
        if out:
            facts, warnings = merge(text, m, base, out)
            source = "llm+parser"
        else:
            warnings.append("structure step unavailable; facts come from the parser only")
    if facts.get("stated_total") is not None and m["total"] and facts["stated_total"] != m["total"]:
        warnings.append(f"she said a total of {facts['stated_total']}, the items add up to {m['total']}")
    return {"facts": facts, "meter": m, "source": source, "warnings": warnings,
            "llm_provider": llm.LAST_PROVIDER.get("provider") if source != "parser" else None}


__all__ = ["extract_facts", "facts_from_meter", "validate_llm", "merge", "find_employer_name", "SCHEMA"]
