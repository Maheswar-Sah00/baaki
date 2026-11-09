"""Haq Raise: ask for a raise to the legal minimum, with a step-up plan. Pure logic (no routes, no DB writes).

Why: Baaki recovers money already owed once. A raise changes her income every month. Lifting Mehta madam's
home from Rs 2,500 to the estimated legal Rs 4,000 (2 h a day) is Rs 18,000 more every year.

Rules:
- Every rupee figure comes from check_core.compute (G.O.Ms.No.6 via app.wages); part-time figures are estimates.
- The request is warm and respectful, in the EMPLOYER's language. It never mentions penalties, and it never
  mentions the law unless she turns the toggle on (judge J1: citing the law in a raise ask reads as a threat).
  With the toggle on there is exactly one gentle line: "the Telangana minimum for this work is about Rs X (estimate)".
- Slots are filled by code. The LLM may only reword the sentences around them; afterwards every amount is
  re-extracted with app.lang (messages.verify_amounts) and must be one of the plan's amounts. Any failure falls
  back to the hand-written templates.
- The spoken AI disclosure goes first (messages.disclosure), added by code, never by the LLM.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
import re
import string
from typing import Any, Optional

from . import calc_inputs, check_core, llm, wages
from .lang import number_to_words
from .messages import (LLM_SCHEMA, disclosure, fmt_money, forbidden_terms, money_words, month_name, name_in,
                       norm_lang, verify_amounts, words_lang)
from .pdf import Block, render_pdf

log = logging.getLogger("raise")

LANGS = ("hi-en", "te-IN", "en")
PLANS = ("full", "step")
DEFAULT_STEP_MONTHS = 6

# Case.work_type (models) -> check_core work type
WORK_MAP = {"housekeeping": "maid", "cleaning": "maid", "maid": "maid", "washing": "maid", "vessels": "maid",
            "sweeping": "maid", "other": "maid", "cooking": "cooking", "cook": "cooking", "childcare": "care",
            "eldercare": "care", "care": "care", "ayah": "care", "caretaker": "care", "both": "both"}

# Words that cite the law. Off by default, so none of them may appear unless she turns the toggle on.
LAW_WORDS = ["minimum", "law", "legal", "g.o", "telangana", "entitled", "government", "labour department",
             "न्यूनतम", "कानून", "क़ानून", "सरकार", "हक़", "हक ",
             "కనీస", "చట్ట", "ప్రభుత్వ", "తెలంగాణ", "హక్కు"]


# --------------------------------------------------------------------------- numbers
def check_work_type(case_work_type: str | None) -> str:
    return WORK_MAP.get((case_work_type or "").strip().lower(), "maid")


def estimate(case_work_type: str | None, hours_per_day: float | None, days_per_week: float, current: float,
             today: dt.date | None = None) -> dict[str, Any]:
    """The legal estimate for this home and the gap, per month and per year (same method as /check).
    Hours not said (None) are never guessed as 8: the estimate says it needs hours (needs_hours=True) and
    carries no legal figure, so nothing is asked for."""
    wt = check_work_type(case_work_type)
    days = float(days_per_week or 6)
    if not hours_per_day:
        cur = wages.money(current or 0)
        chk = check_core.compute(wt, 8, days, float(current or 0), today=today)  # labels and month only
        return {"work_type": wt, "work_label": chk["work_label"], "category": chk["category"], "hours_per_day": None,
                "days_per_week": days, "working_days": float(chk["working_days_per_month"]), "current": cur,
                "legal_estimate": None, "target": None, "is_estimate": True, "gap_monthly": 0.0, "gap_yearly": 0.0,
                "per_day": 0, "needs_hours": True, "how": "Hours not said: estimate needs hours.",
                "source": chk["source"], "source_url": chk["source_url"], "month": chk["month"]}
    hours = float(hours_per_day)
    chk = check_core.compute(wt, hours, days, float(current or 0), today=today)
    legal = float(chk["minimum_monthly"])
    target = float(math.ceil(round(legal, 6)))          # ask in whole rupees, never below the estimate
    cur = wages.money(current or 0)
    gap = wages.money(max(0.0, target - cur))
    dpm = float(chk["working_days_per_month"])
    return {
        "work_type": wt,
        "work_label": chk["work_label"],
        "category": chk["category"],
        "hours_per_day": hours,
        "days_per_week": days,
        "working_days": dpm,
        "current": cur,
        "legal_estimate": legal,
        "target": target,
        "is_estimate": bool(chk["is_estimate"]),
        "gap_monthly": gap,
        "gap_yearly": wages.money(gap * 12),
        "per_day": per_day(gap, dpm),
        "how": chk["how"],
        "source": chk["source"],
        "source_url": chk["source_url"],
        "month": chk["month"],
        "needs_hours": False,
    }


def estimate_for_case(case: Any, today: dt.date | None = None) -> dict[str, Any]:
    """estimate() for a case, reading hours through calc_inputs.case_hours (the DB column defaults to 8)."""
    return estimate(case.work_type, calc_inputs.case_hours(case), case.days_per_week, case.monthly_wage, today)


def per_day(monthly_extra: float, working_days: float) -> int:
    """Cost of a raise per working day, rounded up (Rs 1,500 over 26 days -> Rs 58)."""
    if monthly_extra <= 0 or working_days <= 0:
        return 0
    return int(math.ceil(round(monthly_extra / working_days, 6)))


def step_split(current: float, target: float) -> Optional[float]:
    """The first step of a step-up plan: halfway, rounded down to Rs 100 (2,500 -> 4,000 gives 3,200).
    None when the gap is too small to split (under Rs 200)."""
    gap = float(target) - float(current)
    if gap < 200:
        return None
    first = math.floor((float(current) + gap / 2) / 100) * 100
    if first <= current:
        first = float(current) + 100
    if first >= target:
        return None
    return float(first)


def first_of_next_month(today: dt.date) -> dt.date:
    return wages.add_months(today.replace(day=1), 1)


def plan_numbers(plan: str, current: float, target: float, today: dt.date, *, ask: float | None = None,
                 step1: float | None = None, months: int | None = None, start_month: str | None = None) -> dict[str, Any]:
    """Validate and complete a plan. Raises ValueError with a short reason."""
    if plan not in PLANS:
        raise ValueError(f"plan must be one of {PLANS}")
    current = float(current)
    ask = float(ask if ask is not None else target)
    if ask <= current:
        raise ValueError("the new amount must be more than the current pay")
    if ask > max(3 * float(target), current + 1) and ask > 3 * current:
        raise ValueError("the new amount looks too high; please check it")
    if start_month:
        try:
            start = dt.date(int(start_month[:4]), int(start_month[5:7]), 1)
        except (TypeError, ValueError):
            raise ValueError("start_month must look like 2026-12")
        if start < today.replace(day=1):
            raise ValueError("start_month is in the past")
    else:
        start = first_of_next_month(today)
    out: dict[str, Any] = {"plan": plan, "ask": wages.money(ask), "start": start.isoformat(),
                           "start_month": wages.month_key(start), "step1": None, "months": None,
                           "step_date": None, "step_month": None}
    if plan == "step":
        s1 = float(step1) if step1 is not None else step_split(current, ask)
        if s1 is None:
            raise ValueError("the gap is too small for a step-up; ask for the full amount")
        if not current < s1 < ask:
            raise ValueError("the first step must be between the current pay and the new amount")
        n = int(months if months is not None else DEFAULT_STEP_MONTHS)
        if not 1 <= n <= 12:
            raise ValueError("the step-up must come within 1 to 12 months")
        sd = wages.add_months(start, n)
        out.update(step1=wages.money(s1), months=n, step_date=sd.isoformat(), step_month=wages.month_key(sd))
    return out


def yearly_gain(current: float, new_wage: float) -> float:
    return wages.money(max(0.0, float(new_wage) - float(current)) * 12)


def suggestions(est: dict[str, Any], today: dt.date) -> dict[str, Any]:
    """The two plans shown to her: the full amount now, or a step-up."""
    out: dict[str, Any] = {"full": None, "step": None}
    if est["gap_monthly"] <= 0:
        return out
    out["full"] = plan_numbers("full", est["current"], est["target"], today)
    if step_split(est["current"], est["target"]) is not None:
        out["step"] = plan_numbers("step", est["current"], est["target"], today)
    return out


# --------------------------------------------------------------------------- the message
TEMPLATES: dict[str, list[tuple[Optional[str], str]]] = {
    # (condition, sentence). Conditions: a slot that must be non-empty, or plan:full / plan:step / law.
    "hi-en": [
        (None, "नमस्ते {employer}, मैं {worker}।"),
        ("years", "मुझे आपके घर काम करते हुए {years} साल हो गए हैं, और मुझे यहाँ काम करना अच्छा लगता है।"),
        ("current", "अभी मेरी salary {current} महीना है।"),
        ("plan:full", "मेरी विनती है कि {start} से मेरी salary {ask} महीना कर दी जाए।"),
        ("plan:step", "मेरी विनती है कि {start} से मेरी salary {step1} महीना हो, और {step_month} से {ask}।"),
        ("law", "Telangana में इस काम का न्यूनतम वेतन लगभग {legal} है (अनुमान)।"),
        (None, "आपको ठीक लगे तो हम इस पर बात कर सकते हैं। धन्यवाद।"),
    ],
    "te-IN": [
        (None, "నమస్కారం {employer}, నేను {worker}."),
        ("years", "మీ ఇంట్లో పని చేస్తూ {years} సంవత్సరాలు అయింది, ఇక్కడ పని చేయడం నాకు ఇష్టం."),
        ("current", "ప్రస్తుతం నా జీతం నెలకు {current}."),
        ("plan:full", "{start} నుండి నా జీతం నెలకు {ask} చేయమని కోరుతున్నాను."),
        ("plan:step", "{start} నుండి నా జీతం నెలకు {step1}, {step_month} నుండి {ask} చేయమని కోరుతున్నాను."),
        ("law", "ఈ పనికి తెలంగాణ కనీస వేతనం సుమారు {legal} (అంచనా)."),
        (None, "మీకు వీలైతే దీని గురించి మాట్లాడుకుందాం. ధన్యవాదాలు."),
    ],
    "en": [
        (None, "Hello {employer}, this is {worker}."),
        ("years", "I have worked in your home for {years} years, and I like working here."),
        ("current", "My salary now is {current} a month."),
        ("plan:full", "I would like to request a salary of {ask} a month from {start}."),
        ("plan:step", "I would like to request {step1} a month from {start}, and {ask} from {step_month}."),
        ("law", "The Telangana minimum for this work is about {legal} (estimate)."),
        (None, "If it suits you, we can talk about it. Thank you."),
    ],
}
PERSONAL_LEAD = {"hi-en": "{worker} के अपने शब्द:", "te-IN": "{worker} మాటల్లో:", "en": "In {worker}'s own words:"}

TONE = ("warm, grateful and respectful: a worker who likes the household gently asking for a raise. "
        "Never demanding, never threatening")
LANG_DESC = {
    "hi-en": "Hinglish written in Devanagari script, with common English words (salary, plan) kept in Latin letters",
    "te-IN": "simple spoken Telugu in Telugu script, with common English words (salary) allowed",
    "en": "simple Indian English",
}
_DIGITS = re.compile(r"[0-9०-९౦-౯₹]")


def _placeholders(sentence: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(sentence) if f}


def _fill(sentence: str, slots: dict[str, str]) -> str:
    out = string.Formatter().vformat(sentence, (), slots).strip()
    return out[:1].upper() + out[1:] if out[:1].isascii() else out


def law_terms(text: str) -> list[str]:
    low = f" {(text or '').lower()} "
    return [w for w in LAW_WORDS if w in low]


def _years_text(years: float | None, lang: str) -> tuple[str, str]:
    if not years or years < 1:
        return "", ""
    y = float(years)
    whole = int(y) if abs(y - round(y)) < 0.01 else None
    disp = str(whole) if whole is not None else f"{y:g}"
    speech = number_to_words(whole, words_lang(lang)) if whole is not None else disp
    return disp, speech


def build_slots(*, lang: str, worker: str, employer: str, current: float, legal: float, nums: dict[str, Any],
                years: float | None = None) -> tuple[dict[str, str], dict[str, str], list[float]]:
    lang = norm_lang(lang)
    d: dict[str, str] = {}
    sp: dict[str, str] = {}

    def both(k: str, disp: str, speech: str | None = None) -> None:
        d[k], sp[k] = disp, disp if speech is None else speech

    def money(k: str, v: float | None) -> None:
        both(k, fmt_money(v) if v else "", money_words(v, lang) if v else "")

    both("employer", name_in(employer, lang))
    both("worker", name_in(worker, lang))
    money("current", current)
    money("ask", nums["ask"])
    money("step1", nums.get("step1"))
    money("legal", legal)
    both("start", month_name(nums["start_month"], lang, year=True), month_name(nums["start_month"], lang))
    sm = nums.get("step_month")
    both("step_month", month_name(sm, lang, year=True) if sm else "", month_name(sm, lang) if sm else "")
    y_d, y_s = _years_text(years, lang)
    both("years", y_d, y_s)
    allowed = sorted({round(float(x), 2) for x in (current, nums["ask"], nums.get("step1"), legal,
                                                     math.ceil(legal)) if x})
    return d, sp, allowed


def template_sentences(lang: str, slots: dict[str, str], plan: str, mention_law: bool) -> list[str]:
    out = []
    for cond, s in TEMPLATES[norm_lang(lang)]:
        if cond == "law":
            if not mention_law:
                continue
        elif cond and cond.startswith("plan:"):
            if cond != f"plan:{plan}":
                continue
        elif cond and not slots.get(cond):
            continue
        out.append(s)
    return out


def _required_slots(plan: str, mention_law: bool) -> set[str]:
    req = {"employer", "ask", "start"}
    if plan == "step":
        req |= {"step1", "step_month"}
    if mention_law:
        req.add("legal")
    return req


def llm_validator(allowed_slots: set[str], required: set[str], mention_law: bool):
    def validate(out: Any) -> list[str]:
        sents = out.get("sentences") if isinstance(out, dict) else None
        if not isinstance(sents, list) or not 2 <= len(sents) <= 8:
            raise ValueError("need 2-8 sentences")
        clean, seen = [], set()
        for s in sents:
            if not isinstance(s, str) or not s.strip() or len(s) > 260:
                raise ValueError("bad sentence")
            s = s.strip()
            ph = _placeholders(s)
            if ph - allowed_slots:
                raise ValueError(f"unknown placeholders {ph - allowed_slots}")
            if _DIGITS.search(re.sub(r"\{[a-z_0-9]+\}", "", s)):
                raise ValueError("digits outside placeholders")
            if forbidden_terms(s):
                raise ValueError("forbidden wording")
            if not mention_law and law_terms(s):
                raise ValueError("mentions the law")
            seen |= ph
            clean.append(s)
        if required - seen:
            raise ValueError(f"missing placeholders {required - seen}")
        return clean
    return validate


async def llm_reword(lang: str, template: list[str], slots: dict[str, str], plan: str,
                     mention_law: bool) -> list[str] | None:
    if not llm.configured():
        return None
    used = set().union(*(_placeholders(t) for t in template)) if template else set()
    allowed = {k for k in used if slots.get(k)}
    required = _required_slots(plan, mention_law) & allowed
    law_rule = ("You may keep the one sentence with {legal} exactly once, gently, as information. "
                if mention_law else
                "Never mention the law, the minimum wage, the government or rights. ")
    system = (
        "You polish a short voice-note message from a domestic worker in Hyderabad to the household employer, "
        f"asking for a raise. Write in {LANG_DESC[norm_lang(lang)]}. Tone: {TONE}.\n"
        "Rules: keep the meaning of the draft and do not add facts. Use the {placeholders} exactly as written; "
        "never write any digit, amount, date or number yourself, only placeholders. "
        f"Allowed placeholders: {', '.join('{' + s + '}' for s in sorted(allowed))}. "
        f"Every one of these must appear at least once: {', '.join('{' + s + '}' for s in sorted(required))}. "
        + law_rule +
        "Never threaten; never mention penalties, fines, police, court, lawyers, interest or bonus; never say "
        "'entitled'. Offer to talk. Do not add an AI disclosure (it is added separately). Speak in the first "
        "person as the worker; avoid gendered verb forms. Return JSON {\"sentences\": [...]}, 3 to 7 short "
        "sentences, each under 25 words."
    )
    user = json.dumps({"draft_sentences": template}, ensure_ascii=False)
    try:
        return await llm.json_call(system, user, LLM_SCHEMA, name="raise_message",
                                   validate=llm_validator(allowed, required, mention_law), max_tokens=900)
    except Exception as exc:  # the LLM never breaks the request
        log.warning("raise llm reword failed: %s", str(exc)[:120])
        return None


def check_texts(display: list[str], speech: list[str], lang: str, allowed: list[float], must_have: float,
                mention_law: bool, mask: list[str] | None = None) -> dict[str, Any]:
    ok_d, info_d = verify_amounts(display, lang, allowed, must_have, mask or [])
    ok_s, info_s = verify_amounts(speech, lang, allowed, must_have, mask or [])
    joined = " ".join(display + speech)
    bad = forbidden_terms(joined)
    law = [] if mention_law else law_terms(joined)
    return {"ok": ok_d and ok_s and not bad and not law, "display": info_d, "speech": info_s,
            "forbidden": bad, "law_terms": law}


async def compose(*, lang: str, worker: str, employer: str, current: float, legal: float, nums: dict[str, Any],
                  mention_law: bool = False, years: float | None = None, personal: dict[str, Any] | None = None,
                  use_llm: bool = True, mask: list[str] | None = None) -> dict[str, Any]:
    """The raise request in `lang`. `personal` = {"display": str, "speech": str | None} (already in `lang`)."""
    lang = norm_lang(lang)
    plan = nums["plan"]
    d_slots, s_slots, allowed = build_slots(lang=lang, worker=worker, employer=employer, current=current,
                                            legal=legal, nums=nums, years=years)
    template = template_sentences(lang, d_slots, plan, mention_law)

    def render(sents: list[str]) -> tuple[list[str], list[str]]:
        return [_fill(s, d_slots) for s in sents], [_fill(s, s_slots) for s in sents]

    source, checks = "template", {}
    disp, speech = render(template)
    if use_llm:
        sents = await llm_reword(lang, template, d_slots, plan, mention_law)
        if sents:
            ld, ls = render(sents)
            c = check_texts(ld, ls, lang, allowed, nums["ask"], mention_law, mask)
            if c["ok"]:
                disp, speech, source = ld, ls, "llm"
            else:
                checks["llm_rejected"] = c
    tc = check_texts(disp, speech, lang, allowed, nums["ask"], mention_law, mask)
    if not tc["ok"] and source == "llm":  # belt and braces
        disp, speech = render(template)
        source = "template"
        tc = check_texts(disp, speech, lang, allowed, nums["ask"], mention_law, mask)
    checks.update(tc)

    # her own line goes before the closing thanks, only if it passes the same checks
    personal_info: dict[str, Any] | None = None
    if personal and (personal.get("display") or "").strip():
        p_disp = personal["display"].strip()
        p_speech = (personal.get("speech") or "").strip()
        ok_amt, info = verify_amounts([p_disp] + ([p_speech] if p_speech else []), lang, allowed, None, mask or [])
        bad = forbidden_terms(p_disp + " " + p_speech)
        law = [] if mention_law else law_terms(p_disp + " " + p_speech)
        if ok_amt and not bad and not law:
            disp = disp[:-1] + [p_disp] + disp[-1:]
            if p_speech:
                speech = speech[:-1] + [p_speech] + speech[-1:]
            personal_info = {"included": True, "display": p_disp, "spoken": bool(p_speech)}
        else:
            personal_info = {"included": False, "display": p_disp, "reason": {"amounts": info, "forbidden": bad,
                                                                                 "law_terms": law}}
    disc = disclosure(worker, lang, "stock")
    return {
        "lang": lang,
        "plan": plan,
        "sentences": disp,
        "speech": [disc, *speech],
        "disclosure": disc,
        "text": " ".join([disc, *disp]),
        "body": " ".join(disp),
        "source": source,
        "checks": checks,
        "allowed_amounts": allowed,
        "personal": personal_info,
        "mention_law": mention_law,
    }


# --------------------------------------------------------------------------- the answer
CELEBRATE = {
    "hi-en": ("<excited> Salary बढ़ गई! {employer} ने हाँ कह दिया: {start} से {ask} महीना।",
              "<excited> Salary बढ़ गई! {employer} ने हाँ कह दिया: {start} से {step1}, और {step_month} से {ask}।"),
    "te-IN": ("<excited> జీతం పెంచారు! {employer} ఒప్పుకున్నారు: {start} నుండి నెలకు {ask}.",
              "<excited> జీతం పెంచారు! {employer} ఒప్పుకున్నారు: {start} నుండి {step1}, {step_month} నుండి {ask}."),
    "en": ("<excited> Your salary went up! {employer} said yes: {ask} a month from {start}.",
           "<excited> Your salary went up! {employer} said yes: {step1} from {start}, and {ask} from {step_month}."),
}
CELEBRATE_TITLE = {"hi-en": "Salary बढ़ गई!", "te-IN": "జీతం పెంచారు!", "en": "Your pay went up!"}
CELEBRATE_TITLE_LATIN = {"hi-en": "Salary badh gayi!", "te-IN": "Jeetham penchaaru!", "en": "Your pay went up!"}
YEARLY_LINE = {"hi-en": "हर साल {gain} ज़्यादा।", "te-IN": "ప్రతి సంవత్సరం {gain} ఎక్కువ.", "en": "{gain} more every year."}


def celebration(*, worker_lang: str, employer: str, nums: dict[str, Any], current: float) -> dict[str, Any]:
    """The alert spoken to the worker when the employer accepts (in HER language)."""
    wl = norm_lang(worker_lang)
    step = nums.get("step1") is not None
    tpl = CELEBRATE[wl][1 if step else 0]
    kw_d = {"employer": name_in(employer, wl), "ask": fmt_money(nums["ask"]),
            "step1": fmt_money(nums["step1"]) if step else "", "start": month_name(nums["start_month"], wl, year=True),
            "step_month": month_name(nums["step_month"], wl, year=True) if step else ""}
    kw_s = {**kw_d, "ask": money_words(nums["ask"], wl), "step1": money_words(nums["step1"], wl) if step else "",
            "start": month_name(nums["start_month"], wl),
            "step_month": month_name(nums["step_month"], wl) if step else ""}
    gain = yearly_gain(current, nums["ask"])
    return {
        "title": CELEBRATE_TITLE[wl],
        "title_latin": CELEBRATE_TITLE_LATIN[wl],
        "text": tpl.replace("<excited> ", "").format(**kw_d),
        "speech": tpl.format(**kw_s),
        "yearly_gain": gain,
        "yearly_line": YEARLY_LINE[wl].format(gain=fmt_money(gain)),
        "language": wl,
        "new_wage": nums["step1"] if step else nums["ask"],
        "final_wage": nums["ask"],
    }


# --------------------------------------------------------------------------- the agreement (one page PDF)
AGREEMENT = {
    "en": {
        "title": "Pay agreement",
        "parties": "Between {employer} (employer) and {worker} (worker). Work: {work}, {hours} hours a day, {days} days a week.",
        "before": "Salary until now: {current} a month.",
        "full": "New salary: {ask} a month from {start}.",
        "step": "New salary: {step1} a month from {start}, then {ask} a month from {step_date}.",
        "payday": "Payday: the salary for each month is paid by the 7th of the next month.",
        "agreed": "Agreed on {today} through the Baaki app: the employer pressed \"{button}\" on the request {worker} sent.",
        "sign": "Employer: ____________________        Worker: ____________________",
        "note": "This page records what both agreed. Baaki is an information tool, not a lawyer; this is not legal advice.",
    },
    "hi-en": {
        "title": "वेतन समझौता",
        "parties": "{employer} (employer) और {worker} (worker) के बीच। काम: {work}, रोज़ {hours} घंटे, हफ़्ते में {days} दिन।",
        "before": "अब तक की salary: {current} महीना।",
        "full": "नई salary: {start} से {ask} महीना।",
        "step": "नई salary: {start} से {step1} महीना, फिर {step_date} से {ask} महीना।",
        "payday": "Payday: हर महीने की salary अगले महीने की 7 तारीख तक।",
        "agreed": "{today} को Baaki app पर तय हुआ: {worker} की request पर employer ने \"{button}\" दबाया।",
        "sign": "Employer: ____________________        Worker: ____________________",
        "note": "यह पन्ना दोनों की सहमति का रिकॉर्ड है। Baaki एक जानकारी देने वाला app है, वकील नहीं।",
    },
    "te-IN": {
        "title": "జీతం ఒప్పందం",
        "parties": "{employer} (యజమాని) మరియు {worker} (పనిమనిషి) మధ్య. పని: {work}, రోజుకు {hours} గంటలు, వారానికి {days} రోజులు.",
        "before": "ఇప్పటి వరకు జీతం: నెలకు {current}.",
        "full": "కొత్త జీతం: {start} నుండి నెలకు {ask}.",
        "step": "కొత్త జీతం: {start} నుండి నెలకు {step1}, తర్వాత {step_date} నుండి నెలకు {ask}.",
        "payday": "జీతం రోజు: ప్రతి నెల జీతం తర్వాతి నెల 7వ తేదీ లోపు.",
        "agreed": "{today} న బాకీ యాప్‌లో ఒప్పుకున్నారు: {worker} పంపిన విన్నపానికి యజమాని \"{button}\" నొక్కారు.",
        "sign": "యజమాని: ____________________        పనిమనిషి: ____________________",
        "note": "ఈ పేజీ ఇద్దరి అంగీకారానికి రికార్డు. బాకీ సమాచారం ఇచ్చే యాప్, లాయర్ కాదు.",
    },
}
WORK_LABEL = {
    "maid": {"en": "cleaning", "hi-en": "सफ़ाई", "te-IN": "ఇంటి పని"},
    "cooking": {"en": "cooking", "hi-en": "खाना बनाना", "te-IN": "వంట"},
    "both": {"en": "cooking and cleaning", "hi-en": "खाना और सफ़ाई", "te-IN": "వంట మరియు ఇంటి పని"},
    "care": {"en": "child or elder care", "hi-en": "बच्चों या बुज़ुर्गों की देखभाल", "te-IN": "పిల్లలు లేదా పెద్దల సంరక్షణ"},
}
BUTTON = {"asked": {"en": "Accept", "hi-en": "मंज़ूर", "te-IN": "ఒప్పుకుంటున్నాను"},
          "step": {"en": "Step it up", "hi-en": "धीरे-धीरे बढ़ाएँ", "te-IN": "దశలవారీగా పెంచుతాను"}}


def _date_text(iso: str, lang: str) -> str:
    from .messages import fmt_date
    return fmt_date(iso, lang)


def agreement_blocks(*, worker: str, employer: str, worker_lang: str, employer_lang: str, work_type: str,
                     hours: float, days: float, current: float, nums: dict[str, Any], choice: str,
                     today: dt.date) -> list[Block]:
    langs: list[str] = []
    for lg in (norm_lang(worker_lang), norm_lang(employer_lang), "en"):
        if lg not in langs:
            langs.append(lg)
    blocks: list[Block] = [Block(" · ".join(AGREEMENT[lg]["title"] for lg in langs), size=18, space_after=6)]
    step = nums.get("step1") is not None
    for lg in langs:
        T = AGREEMENT[lg]
        kw = {"employer": name_in(employer, lg), "worker": name_in(worker, lg),
              "work": WORK_LABEL.get(work_type, WORK_LABEL["maid"])[lg], "hours": f"{hours:g}", "days": f"{days:g}",
              "current": fmt_money(current), "ask": fmt_money(nums["ask"]),
              "step1": fmt_money(nums["step1"]) if step else "", "start": _date_text(nums["start"], lg),
              "step_date": _date_text(nums["step_date"], lg) if step else "", "today": _date_text(today.isoformat(), lg),
              "button": BUTTON.get(choice, BUTTON["asked"])[lg]}
        blocks.append(Block(T["title"], size=13, space_after=2))
        for key in ("parties", "before", "step" if step else "full", "payday", "agreed"):
            blocks.append(Block(T[key].format(**kw), size=10.5, space_after=1.5))
        blocks.append(Block("", size=4, space_after=2))
    blocks.append(Block(AGREEMENT["en"]["sign"], size=11, space_after=6))
    blocks.append(Block(AGREEMENT["en"]["note"], size=8.5, space_after=0))
    return blocks


def agreement_pdf(**kw: Any) -> bytes:
    return render_pdf(agreement_blocks(**kw), title="Pay agreement (Baaki)")


# --------------------------------------------------------------------------- payday reminder (.ics)
def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def payday_ics(*, worker: str, nums: dict[str, Any], uid: str, stamp: dt.datetime | None = None) -> str:
    """Monthly reminder for the employer on the 1st (pay by the 7th) at the new wage; a second series from
    the step-up date at the final wage."""
    stamp = stamp or dt.datetime.now(dt.timezone.utc)
    ts = stamp.strftime("%Y%m%dT%H%M%SZ")
    start = dt.date.fromisoformat(nums["start"])
    first_pay = wages.add_months(start, 1)                # pay for the first month at the new wage
    step = nums.get("step1") is not None
    events = []

    def vevent(n: int, amount: float, dfrom: dt.date, until: dt.date | None) -> str:
        rrule = "RRULE:FREQ=MONTHLY;BYMONTHDAY=1"
        if until:
            rrule += f";UNTIL={until.strftime('%Y%m%d')}"
        summary = _ics_escape(f"Pay {worker} {fmt_money(amount).replace('₹', 'Rs ')} (new salary), by the 7th")
        desc = _ics_escape(f"Salary for last month at the new rate agreed on Baaki: {fmt_money(amount).replace('₹', 'Rs ')} a month.")
        return "\r\n".join([
            "BEGIN:VEVENT", f"UID:{uid}-{n}@baaki", f"DTSTAMP:{ts}",
            f"DTSTART;VALUE=DATE:{dfrom.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(dfrom + dt.timedelta(days=1)).strftime('%Y%m%d')}",
            rrule, f"SUMMARY:{summary}", f"DESCRIPTION:{desc}",
            "BEGIN:VALARM", "TRIGGER:PT9H", "ACTION:DISPLAY", f"DESCRIPTION:{summary}", "END:VALARM",
            "END:VEVENT"])

    if step:
        step_pay = wages.add_months(dt.date.fromisoformat(nums["step_date"]), 1)
        events.append(vevent(1, nums["step1"], first_pay, step_pay - dt.timedelta(days=1)))
        events.append(vevent(2, nums["ask"], step_pay, None))
    else:
        events.append(vevent(1, nums["ask"], first_pay, None))
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Baaki//Haq Raise//EN", "CALSCALE:GREGORIAN",
                        *events, "END:VCALENDAR"]) + "\r\n"


__all__ = ["estimate", "step_split", "plan_numbers", "suggestions", "yearly_gain", "per_day", "compose",
           "celebration", "agreement_pdf", "agreement_blocks", "payday_ics", "law_terms", "check_work_type"]
