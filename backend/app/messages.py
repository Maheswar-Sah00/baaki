"""The Polite -> Firm -> Formal ladder: message text in the employer's language.

Rules (docs/research/02_law_procedure_telangana.md sections 6 and 8):
- Respectful, never threatening. No penalties, fines, police, jail, multiples, notice pay, bonus,
  interest or promised outcomes. Polite asks; Firm states the amount, the due date and the work log;
  Formal cites G.O.Ms.No.6 and Code on Wages s.17 and names free legal aid (DLSA Hyderabad,
  NALSA 15100, India Labourline 1800 833 9020).
- Every voice note starts with a spoken AI disclosure in the employer's language. The disclosure is
  added here by code, never by the LLM.
- Every amount, name and date is a slot filled from the case. The LLM may only reword the sentences
  around the slots; afterwards every amount in the text is re-extracted with app.lang and must match
  the case. Any failure, or no LLM, falls back to the hand-written templates below.

Each message has two renderings of the same sentences:
- display: what the employer reads (₹13,000, dates with year, helpline numbers);
- speech:  what Timbre speaks (amounts as words, which Timbre and Prisma both handle reliably,
           see 04_gnani_feasibility.md test 3; helpline numbers are left to the letter).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import string
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from sqlmodel import Session, select

from . import config, llm
from .lang import extract_amounts, inr_to_words, number_to_words, today_ist
from .lang import format_inr as _format_inr_int
from .models import Case, CaseItem, DiaryEntry, Employer, Payment, Worker

log = logging.getLogger("messages")

STEPS = ("polite", "firm", "formal")
LANGS = ("hi-en", "te-IN", "en")
REPLY_DAYS = 7

# Helplines and legal-aid route (02_law section 5 / 8D; 03_competitors 2.2). Never SAMADHAN.
NALSA = "15100"
INDIA_LABOURLINE = "1800 833 9020"
DLSA = "DLSA Hyderabad (City Civil Court, Purani Haveli)"
GO_CITATION = "G.O.Ms.No.6, LET&F (Lab-I) Dept, dated 30.05.2026, in force 01.06.2026"
S17 = "Code on Wages, 2019, section 17"


# --------------------------------------------------------------------------- language helpers
def norm_lang(lang: str | None) -> str:
    """Our three message languages: hi-en (Hinglish in Devanagari + English words), te-IN, en."""
    x = (lang or "").strip().lower()
    if x in ("te", "te-in", "telugu"):
        return "te-IN"
    if x in ("hi-en", "hinglish", "hi", "hi-in", "hindi"):
        return "hi-en"
    return "en"


def tts_lang(lang: str) -> str:
    """Timbre language code for a message language."""
    return {"hi-en": "hi-en", "te-IN": "te-IN", "en": "en-IN"}[norm_lang(lang)]


def words_lang(lang: str) -> str:
    """app.lang code for spelling amounts: Hinglish is written in Devanagari (feasibility test 1)."""
    return {"hi-en": "hi", "te-IN": "te", "en": "en"}[norm_lang(lang)]


def parse_lang(lang: str) -> str:
    """app.lang hint used when re-extracting amounts from our own text."""
    return {"hi-en": "hinglish", "te-IN": "te", "en": "en"}[norm_lang(lang)]


MONTHS = {
    "hi-en": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "te-IN": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}
AND = {"hi-en": "और", "te-IN": "మరియు", "en": "and"}

# Synthetic demo names in each script (names are stored in Latin). Unknown names stay Latin.
NAME_SCRIPTS: dict[str, dict[str, str]] = {
    "lakshmi": {"hi-en": "लक्ष्मी", "te-IN": "లక్ష్మి"},
    "rafiq": {"hi-en": "रफ़ीक़", "te-IN": "రఫీక్"},
    "sharma ji": {"hi-en": "शर्मा जी", "te-IN": "శర్మ గారు"},
    "mr sharma": {"hi-en": "शर्मा जी", "te-IN": "శర్మ గారు"},
    "sharma": {"hi-en": "शर्मा जी", "te-IN": "శర్మ గారు"},
    "reddy garu": {"hi-en": "रेड्डी गारु", "te-IN": "రెడ్డి గారు"},
    "reddy": {"hi-en": "रेड्डी गारु", "te-IN": "రెడ్డి గారు"},
    "mehta madam": {"hi-en": "मेहता मैडम", "te-IN": "మెహతా మేడమ్"},
    "mehta": {"hi-en": "मेहता मैडम", "te-IN": "మెహతా మేడమ్"},
    "rao garu": {"hi-en": "राव गारु", "te-IN": "రావు గారు"},
    "rao": {"hi-en": "राव गारु", "te-IN": "రావు గారు"},
}


def name_in(name: str, lang: str) -> str:
    lang = norm_lang(lang)
    if lang == "en":
        return name
    key = re.sub(r"[^a-z ]", "", (name or "").lower()).strip()
    key = re.sub(r"\s+", " ", key)
    return NAME_SCRIPTS.get(key, {}).get(lang, name)


def fmt_money(amount: float) -> str:
    """₹13,000, ₹615.50 or -₹2,000 (Indian grouping)."""
    a = round(float(amount), 2)
    sign, a = ("-", -a) if a < 0 else ("", a)
    whole = int(a)
    paise = int(round((a - whole) * 100))
    if paise == 100:
        whole, paise = whole + 1, 0
    s = _format_inr_int(whole)
    return sign + (f"{s}.{paise:02d}" if paise else s)


def money_words(amount: float, lang: str) -> str:
    """Amount as words for TTS (rounded to whole rupees; part-time paise never get spoken)."""
    return inr_to_words(int(round(float(amount))), words_lang(lang))


def fmt_date(d: dt.date | str | None, lang: str, year: bool = True) -> str:
    if d is None:
        return ""
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    m = MONTHS[norm_lang(lang)][d.month - 1]
    return f"{d.day} {m} {d.year}" if year else f"{d.day} {m}"


def join_list(parts: list[str], lang: str) -> str:
    lang = norm_lang(lang)
    if len(parts) <= 1:
        return "".join(parts)
    if lang == "te-IN":
        return ", ".join(parts)
    return ", ".join(parts[:-1]) + f" {AND[lang]} " + parts[-1]


def month_name(month: str, lang: str, year: bool = False) -> str:
    """'2026-08' -> 'अगस्त' (or 'अगस्त 2026')."""
    try:
        y, m = int(month[:4]), int(month[5:7])
    except (TypeError, ValueError):
        return str(month)
    n = MONTHS[norm_lang(lang)][m - 1]
    return f"{n} {y}" if year else n


# --------------------------------------------------------------------------- the case context
@dataclass
class CaseCtx:
    case: Case
    worker: Worker
    employer: Employer
    items: list[CaseItem]                 # every item
    diary: list[DiaryEntry] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)

    @property
    def included(self) -> list[CaseItem]:
        return [i for i in self.items if i.included_in_total]

    @property
    def employer_lang(self) -> str:
        return norm_lang(self.employer.language)

    @property
    def worker_lang(self) -> str:
        return norm_lang(self.worker.language)

    @property
    def total_due(self) -> float:
        return round(float(self.case.total_due or 0), 2)

    @property
    def paid(self) -> float:
        return round(float(self.case.amount_paid or 0), 2)

    @property
    def balance(self) -> float:
        return max(0.0, round(self.total_due - self.paid, 2))

    def unpaid_months(self) -> list[str]:
        """Months with no pay at all ("my salary for October has not been paid")."""
        part = set(self.part_unpaid_months())
        return sorted({i.month for i in self.included if i.kind == "unpaid_wage" and i.month} - part)

    def part_unpaid_months(self) -> list[str]:
        """Months paid in part, or part of a month she said: "part of my October salary is still due"."""
        return sorted({i.month for i in self.included if i.kind == "unpaid_wage" and i.month and is_part_item(i)})

    def sum_kind(self, kind: str) -> float:
        return round(sum(float(i.amount) for i in self.included if i.kind == kind), 2)

    def first_due(self) -> Optional[str]:
        """Earliest wage due date (s.17), from unpaid-wage lines (else any line)."""
        ds = sorted(i.due_date for i in self.included if i.due_date and i.kind == "unpaid_wage") or             sorted(i.due_date for i in self.included if i.due_date)
        return ds[0] if ds else None

    def checkins(self) -> list[DiaryEntry]:
        return [d for d in self.diary if d.kind == "checkin"]


def load_ctx(s: Session, case_id: int) -> CaseCtx | None:
    case = s.get(Case, case_id)
    if case is None:
        return None
    return _ctx_for(s, case)


def load_ctx_by_token(s: Session, token: str) -> CaseCtx | None:
    case = s.exec(select(Case).where(Case.employer_token == token)).first()
    if case is None:
        return None
    return _ctx_for(s, case)


def _ctx_for(s: Session, case: Case) -> CaseCtx:
    worker = s.get(Worker, case.worker_id)
    employer = s.get(Employer, case.employer_id)
    items = list(s.exec(select(CaseItem).where(CaseItem.case_id == case.id).order_by(CaseItem.id)))
    diary = list(s.exec(select(DiaryEntry).where(DiaryEntry.case_id == case.id).order_by(DiaryEntry.id)))
    if not diary:  # check-ins logged against the worker + employer before the case existed
        diary = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == case.worker_id,
                                                     DiaryEntry.employer_id == case.employer_id)
                            .order_by(DiaryEntry.id)))
    pays = list(s.exec(select(Payment).where(Payment.case_id == case.id).order_by(Payment.id)))
    return CaseCtx(case, worker, employer, items, diary, pays)


# --------------------------------------------------------------------------- item labels
ITEM_LABELS = {
    "unpaid_wage": {"hi-en": "{m} की salary", "te-IN": "{m} జీతం", "en": "Unpaid wages, {m}"},
    "illegal_deduction": {"hi-en": "salary से काटी गई रकम (वापस)", "te-IN": "జీతంలో కోత (తిరిగి ఇవ్వాల్సింది)",
                          "en": "Deduction to be returned"},
    "final_settlement": {"hi-en": "आख़िरी हिसाब (काम के आख़िरी दिन तक)", "te-IN": "చివరి లెక్క (చివరి పని రోజు వరకు)",
                         "en": "Final settlement (wages up to the last day)"},
    "min_wage_shortfall": {"hi-en": "न्यूनतम वेतन से कमी (अनुमान)", "te-IN": "కనీస వేతనం కంటే తక్కువ (అంచనా)",
                           "en": "Minimum-wage shortfall (estimate)"},
    "advance_recovery": {"hi-en": "पहले लिया advance (घटाया गया)", "te-IN": "ముందు తీసుకున్న అడ్వాన్స్ (తీసివేశాం)",
                         "en": "Advance still to be recovered (subtracted)"},
    "paid_received": {"hi-en": "पहले मिल चुके (घटाए गए)", "te-IN": "ముందే అందినది (తీసివేశాం)",
                      "en": "Already received from the employer (subtracted)"},
}
PART_UNPAID = {"hi-en": "{m} की बची हुई salary", "te-IN": "{m} మిగిలిన జీతం", "en": "Unpaid part of wages, {m}"}


def is_part_item(item: Any) -> bool:
    """An unpaid-wage line for only part of a month (part-paid, or "dhai mahine")."""
    label = (getattr(item, "label", None) or "").lower()
    return label.startswith("part") or " of a month" in label


def item_label(item: CaseItem, lang: str) -> str:
    lang = norm_lang(lang)
    tpl = ITEM_LABELS.get(item.kind, {}).get(lang)
    if item.kind == "unpaid_wage" and is_part_item(item):
        tpl = PART_UNPAID[lang]
    if not tpl:
        return item.label
    m = month_name(item.month, lang, year=True) if item.month else ""
    if "{m}" in tpl:
        return tpl.format(m=m) if m else (item.label or tpl.replace("{m}", "").strip(" ,"))
    return f"{tpl}, {m}" if m else tpl


# --------------------------------------------------------------------------- disclosure
DISCLOSURE = {
    ("hi-en", "clone"): "यह एक AI वॉइस संदेश है। इसे {worker} की अनुमति से, उनकी आवाज़ में, Baaki ऐप ने बनाया है।",
    ("hi-en", "stock"): "यह एक AI वॉइस संदेश है। इसे {worker} की अनुमति से, उनकी ओर से, Baaki ऐप ने बनाया है।",
    ("te-IN", "clone"): "ఇది AI వాయిస్ సందేశం. {worker} అనుమతితో, వారి గొంతులో, బాకీ యాప్ దీన్ని తయారు చేసింది.",
    ("te-IN", "stock"): "ఇది AI వాయిస్ సందేశం. {worker} అనుమతితో, వారి తరఫున, బాకీ యాప్ దీన్ని తయారు చేసింది.",
    ("en", "clone"): "This is an AI voice message, made by the Baaki app in {worker}'s own voice, with {worker}'s permission.",
    ("en", "stock"): "This is an AI voice message, made by the Baaki app on behalf of {worker}, with {worker}'s permission.",
}


def disclosure(worker_name: str, lang: str, voice_mode: str = "stock") -> str:
    lang = norm_lang(lang)
    mode = "clone" if voice_mode == "clone" else "stock"
    return DISCLOSURE[(lang, mode)].format(worker=name_in(worker_name, lang))


# --------------------------------------------------------------------------- templates
# Each entry: (condition, sentence). A condition names a slot that must be non-empty (or None);
# "@speech" marks a sentence that is only spoken (the written text already shows what it points to).
# Slots: employer worker total monthly months_n months_list cut shortfall paid first_due reply_by
#        diary_days law legal_aid
TEMPLATES: dict[str, dict[str, list[tuple[Optional[str], str]]]] = {
    "polite": {
        "hi-en": [
            ("months_list", "नमस्ते {employer}, मेरी {months_list} की salary अभी तक नहीं मिली है, {monthly} हर महीने के हिसाब से।"),
            ("part_only", "नमस्ते {employer}, मेरी {part_list} की salary का कुछ हिस्सा अभी बाकी है।"),
            ("part_also", "{part_list} की salary का कुछ हिस्सा भी बाकी है।"),
            ("cut", "salary की कटौती में से {cut} भी वापस बनते हैं।"),
            ("shortfall", "इसमें न्यूनतम वेतन से कमी का अनुमान, {shortfall}, भी जोड़ा है।"),
            ("paid", "{paid} मिल चुके हैं, उसके लिए धन्यवाद।"),
            (None, "कुल मिलाकर {total} बाकी हैं।"),
            (None, "हो सके तो {reply_by} तक दे दीजिए, payment का link इस message के साथ है। धन्यवाद।"),
        ],
        "te-IN": [
            ("months_list", "నమస్కారం {employer}, నా {months_list} నెలల జీతం ఇంకా రాలేదు; నా జీతం నెలకు {monthly}."),
            ("part_only", "నమస్కారం {employer}, నా {part_list} జీతంలో కొంత భాగం ఇంకా రావాలి."),
            ("part_also", "{part_list} జీతంలో కొంత భాగం కూడా ఇంకా రావాలి."),
            ("cut", "జీతంలో చేసిన కోతలో {cut} కూడా తిరిగి రావాలి."),
            ("shortfall", "కనీస వేతనం కంటే తక్కువ అయిన అంచనా మొత్తం {shortfall} కూడా ఇందులో ఉంది."),
            ("paid", "{paid} అందింది, ధన్యవాదాలు."),
            (None, "మొత్తం {total} బాకీ ఉంది."),
            (None, "వీలైతే {reply_by} లోపు ఇవ్వండి, చెల్లించే లింక్ ఈ మెసేజ్‌తో ఉంది. ధన్యవాదాలు."),
        ],
        "en": [
            ("months_list", "Hello {employer}, my salary for {months_list} has not been paid yet, at {monthly} a month."),
            ("part_only", "Hello {employer}, part of my salary for {part_list} is still due."),
            ("part_also", "Part of my salary for {part_list} is also still due."),
            ("cut", "{cut} of the cut from my salary is also to be returned."),
            ("shortfall", "It also includes an estimated minimum-wage shortfall of {shortfall}."),
            ("paid", "I have received {paid}, thank you for that."),
            (None, "In total, {total} is still due."),
            (None, "If possible, please pay it by {reply_by}; the payment link is with this message. Thank you."),
        ],
    },
    "firm": {
        "hi-en": [
            (None, "नमस्ते {employer}, यह मेरे पिछले संदेश की याद दिलाने के लिए है।"),
            ("months_list", "मेरी {months_list} की salary अभी तक नहीं मिली है।"),
            ("part_list", "{part_list} की salary का कुछ हिस्सा अभी बाकी है।"),
            ("first_due", "हर महीने की salary अगले महीने की सात तारीख तक दी जाती है, इसलिए पहली salary {first_due} तक मिलनी थी।"),
            ("cut", "salary की कटौती में से {cut} अभी लौटाने बाकी हैं।"),
            ("paid", "{paid} मिल चुके हैं।"),
            (None, "कुल बाकी रकम {total} है।"),
            ("diary_days", "मेरी Kaam Diary में {diary_days} दिन के काम की entry है, जो इस message के साथ है।"),
            (None, "कृपया {reply_by} तक payment कर दीजिए; एक साथ मुश्किल हो तो link पर किस्तों का plan चुन सकते हैं। धन्यवाद।"),
        ],
        "te-IN": [
            (None, "నమస్కారం {employer}, ఇది నా ముందు మెసేజ్ గురించి గుర్తు చేయడానికి."),
            ("months_list", "నా {months_list} జీతం ఇంకా అందలేదు."),
            ("part_list", "{part_list} జీతంలో కొంత భాగం ఇంకా రావాలి."),
            ("first_due", "ప్రతి నెల జీతం తర్వాతి నెల ఏడవ తేదీ లోపు ఇవ్వాలి, కాబట్టి మొదటి జీతం {first_due} లోపు రావాల్సింది."),
            ("cut", "జీతం కోతలో {cut} ఇంకా తిరిగి రావాల్సి ఉంది."),
            ("paid", "{paid} అందింది."),
            (None, "మొత్తం బాకీ {total}."),
            ("diary_days", "నా పని డైరీలో {diary_days} రోజుల పని నమోదు ఉంది, అది ఈ మెసేజ్‌తో జతచేశాను."),
            (None, "దయచేసి {reply_by} లోపు చెల్లించండి; ఒకేసారి కష్టమైతే లింక్‌లో వాయిదాల ప్లాన్ ఎంచుకోవచ్చు. ధన్యవాదాలు."),
        ],
        "en": [
            (None, "Hello {employer}, this is a reminder about my earlier message."),
            ("months_list", "My salary for {months_list} has still not been paid."),
            ("part_list", "Part of my salary for {part_list} is still due."),
            ("first_due", "Monthly wages are due by the seventh of the next month, so the first of these was due by {first_due}."),
            ("cut", "{cut} of the cut from my salary is still to be returned."),
            ("paid", "I have received {paid}."),
            (None, "The total still due is {total}."),
            ("diary_days", "My work diary has {diary_days} days of work recorded, and it is attached to this message."),
            (None, "Please pay by {reply_by}. If one payment is difficult, you can choose instalments on the link. Thank you."),
        ],
    },
    "formal": {
        "hi-en": [
            (None, "नमस्ते {employer}, यह {worker} की ओर से बाकी salary के बारे में एक औपचारिक पत्र है।"),
            (None, "{law} के अनुसार, महीने की salary अगले महीने की सात तारीख तक दी जानी चाहिए।"),
            (None, "मेरी कुल बाकी रकम {total} है, और पूरा हिसाब साथ के पत्र में है।"),
            (None, "कृपया {reply_by} तक भुगतान कर दीजिए, या जवाब दीजिए।"),
            (None, "अगर बात नहीं बनी, तो मैं Telangana Labour Department और मुफ़्त कानूनी सहायता ({legal_aid}) से सलाह लूँगी।"),
            ("@speech", "इनके नंबर साथ के पत्र में हैं।"),
            (None, "मैं बात करके हल निकालना चाहती हूँ। धन्यवाद।"),
        ],
        "te-IN": [
            (None, "నమస్కారం {employer}, ఇది {worker} బాకీ జీతం గురించి అధికారిక లేఖ."),
            (None, "{law} ప్రకారం, నెల జీతం తర్వాతి నెల ఏడవ తేదీ లోపు చెల్లించాలి."),
            (None, "నా మొత్తం బాకీ {total}, పూర్తి లెక్క జతచేసిన లేఖలో ఉంది."),
            (None, "దయచేసి {reply_by} లోపు చెల్లించండి, లేదా సమాధానం ఇవ్వండి."),
            (None, "పరిష్కారం కాకపోతే, తెలంగాణ కార్మిక శాఖ, ఉచిత న్యాయ సహాయ సంస్థల ({legal_aid}) నుండి సలహా తీసుకుంటాను."),
            ("@speech", "వీటి నంబర్లు జతచేసిన లేఖలో ఉన్నాయి."),
            (None, "మాట్లాడి పరిష్కరించుకోవాలని కోరుకుంటున్నాను. ధన్యవాదాలు."),
        ],
        "en": [
            (None, "Hello {employer}, this is a formal letter from {worker} about unpaid wages."),
            (None, "Under {law}, monthly wages are to be paid by the seventh of the next month."),
            (None, "The total still due is {total}, and the full calculation is in the attached letter."),
            (None, "Please pay by {reply_by}, or reply to this message."),
            (None, "If this is not resolved, I will seek advice from the Telangana Labour Department and free legal aid ({legal_aid})."),
            ("@speech", "Their numbers are in the attached letter."),
            (None, "I would like to settle this by talking. Thank you."),
        ],
    },
}

# Gendered first-person verbs only appear in the Hinglish formal template; a male worker gets these.
_MASC = {"सलाह लूँगी": "सलाह लूँगा", "चाहती हूँ": "चाहता हूँ"}
MALE_NAMES = {"rafiq", "raju", "ramesh", "suresh", "imran", "salim"}

LAW = {
    "hi-en": ("Telangana का G.O.Ms.No.6 (30.05.2026) और Code on Wages, 2019 की धारा 17",
              "Telangana का minimum wage order, G.O. नंबर छह, और Code on Wages की धारा सत्रह"),
    "te-IN": ("తెలంగాణ G.O.Ms.No.6 (30.05.2026) మరియు కోడ్ ఆన్ వేజెస్, 2019 సెక్షన్ 17",
              "తెలంగాణ కనీస వేతన ఉత్తర్వు, G.O. నంబర్ ఆరు, మరియు కోడ్ ఆన్ వేజెస్ సెక్షన్ పదిహేడు"),
    "en": ("Telangana G.O.Ms.No.6 (30.05.2026) and the Code on Wages, 2019, section 17",
           "the Telangana minimum wage order G.O. number six and the Code on Wages, section seventeen"),
}
LEGAL_AID = {
    "hi-en": (f"DLSA Hyderabad, NALSA helpline {NALSA} और India Labourline {INDIA_LABOURLINE}",
              "DLSA Hyderabad, NALSA helpline और India Labourline"),
    "te-IN": (f"DLSA హైదరాబాద్, NALSA హెల్ప్‌లైన్ {NALSA}, India Labourline {INDIA_LABOURLINE}",
              "DLSA హైదరాబాద్, NALSA హెల్ప్‌లైన్, India Labourline"),
    "en": (f"DLSA Hyderabad, the NALSA helpline {NALSA} and India Labourline {INDIA_LABOURLINE}",
           "DLSA Hyderabad, the NALSA helpline and India Labourline"),
}

FORBIDDEN = [
    # threats, penalties, multiples, promised outcomes, claims no law gives a household worker
    "penalt", "jail", "prison", "police", " fir ", "fir.", "prosecut", "fine of", "10x", "ten times", "3x",
    "guarantee", "you will lose", "legal action", "lawyer", "advocate", "court case", "notice pay", "bonus",
    "gratuity", "interest", "illegal", "shame", "compensation",
    "जुर्माना", "दंड", "जेल", "पुलिस", "गुना", "मुकदमा", "ब्याज", "बोनस", "गैरकानूनी", "मुआवज़ा", "वकील",
    "జరిమానా", "జైలు", "పోలీస", "రెట్లు", "కేసు", "వడ్డీ", "బోనస్", "చట్టవిరుద్ధ", "పరిహారం", "లాయర్",
]
_MASK_LITERALS = [INDIA_LABOURLINE, NALSA, "G.O.Ms.No.6", "30.05.2026", "01.06.2026", "2019"]


@dataclass
class Draft:
    step: str
    lang: str
    display_sentences: list[str]
    speech_sentences: list[str]
    disclosure_display: str
    disclosure_speech: str
    source: str                         # "template" | "llm"
    slots_display: dict[str, str]
    slots_speech: dict[str, str]
    allowed_amounts: list[float]
    reply_by: str
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Display text with the disclosure first (what the employer reads)."""
        return " ".join([self.disclosure_display, *self.display_sentences])

    @property
    def speech(self) -> list[str]:
        """Sentences for the voice note, disclosure first (one Timbre call each)."""
        return [self.disclosure_speech, *self.speech_sentences]

    def slots_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.slots_display, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def is_male(name: str) -> bool:
    return (name or "").strip().lower().split(" ")[0] in MALE_NAMES


def build_slots(ctx: CaseCtx, lang: str, today: dt.date | None = None) -> tuple[dict[str, str], dict[str, str], list[float], str]:
    """(display slots, speech slots, allowed amounts, reply_by ISO) from the case data."""
    lang = norm_lang(lang)
    today = today or today_ist()
    reply_by = today + dt.timedelta(days=REPLY_DAYS)
    months = ctx.unpaid_months()
    month_names = [month_name(m, lang) for m in months]
    part_names = [month_name(m, lang) for m in ctx.part_unpaid_months()]
    cut = ctx.sum_kind("illegal_deduction")
    shortfall = ctx.sum_kind("min_wage_shortfall")
    first_due = ctx.first_due()
    n_days = len(ctx.checkins())
    worker = name_in(ctx.worker.name, lang)
    employer = name_in(ctx.employer.name, lang)
    monthly = float(ctx.case.monthly_wage or 0)

    def both(key: str, disp: str, speech: str | None = None) -> None:
        d[key] = disp
        sp[key] = disp if speech is None else speech

    d: dict[str, str] = {}
    sp: dict[str, str] = {}
    both("employer", employer)
    both("worker", worker)
    both("total", fmt_money(ctx.balance), money_words(ctx.balance, lang))
    both("monthly", fmt_money(monthly) if monthly else "", money_words(monthly, lang) if monthly else "")
    both("months_n", str(len(months)) if months else "", number_to_words(len(months), words_lang(lang)) if months else "")
    both("months_list", join_list(month_names, lang))
    both("part_list", join_list(part_names, lang))
    both("part_only", d["part_list"] if not month_names else "")
    both("part_also", d["part_list"] if month_names else "")
    both("cut", fmt_money(cut) if cut else "", money_words(cut, lang) if cut else "")
    both("shortfall", fmt_money(shortfall) if shortfall else "", money_words(shortfall, lang) if shortfall else "")
    both("paid", fmt_money(ctx.paid) if ctx.paid else "", money_words(ctx.paid, lang) if ctx.paid else "")
    both("first_due", fmt_date(first_due, lang) if first_due else "", fmt_date(first_due, lang, year=False) if first_due else "")
    both("reply_by", fmt_date(reply_by, lang), fmt_date(reply_by, lang, year=False))
    both("diary_days", str(n_days) if n_days else "", number_to_words(n_days, words_lang(lang)) if n_days else "")
    both("law", LAW[lang][0], LAW[lang][1])
    both("legal_aid", LEGAL_AID[lang][0], LEGAL_AID[lang][1])
    allowed = sorted({round(x, 2) for x in [ctx.balance, ctx.total_due, monthly, cut, shortfall, ctx.paid,
                                            *[abs(float(i.amount)) for i in ctx.items]] if x})
    return d, sp, allowed, reply_by.isoformat()


def _fill(sentence: str, slots: dict[str, str]) -> str:
    out = string.Formatter().vformat(sentence, (), slots).strip()
    return out[:1].upper() + out[1:] if out[:1].isascii() else out


def _placeholders(sentence: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(sentence) if f}


def template_sentences(step: str, lang: str, slots: dict[str, str], male: bool = False,
                       speech_only: bool = False) -> list[str]:
    """The hand-written template for this step, with sentences whose condition slot is empty dropped.
    speech_only=True returns only the "@speech" lines (appended to the spoken note)."""
    out = []
    for cond, s in TEMPLATES[step][norm_lang(lang)]:
        if (cond == "@speech") != speech_only:
            continue
        if cond and cond != "@speech" and not slots.get(cond):
            continue
        if male and norm_lang(lang) == "hi-en":
            for f, m in _MASC.items():
                s = s.replace(f, m)
        out.append(s)
    return out


# --------------------------------------------------------------------------- verification
def _mask(text: str, extra: Iterable[str] = ()) -> str:
    for lit in [*_MASK_LITERALS, *[e for e in extra if e]]:
        text = text.replace(lit, " ")
    return text


def amounts_in(text: str, lang: str, extra_mask: Iterable[str] = ()) -> list[float]:
    return [float(a["amount_inr"]) for a in extract_amounts(_mask(text, extra_mask), parse_lang(lang))]


def verify_amounts(texts: list[str], lang: str, allowed: list[float], must_have: float | None,
                   extra_mask: Iterable[str] = ()) -> tuple[bool, dict[str, Any]]:
    """Every amount in every text must be a case amount; the balance must appear at least once.

    Amounts are compared in whole rupees (part-time estimates have paise; speech rounds them)."""
    allowed_r = {int(round(a)) for a in allowed}
    found: list[float] = []
    for t in texts:
        found += amounts_in(t, lang, extra_mask)
    found_r = [int(round(f)) for f in found]
    bad = sorted({f for f in found_r if f not in allowed_r})
    has_total = must_have is None or int(round(must_have)) in found_r
    return (not bad and has_total), {"amounts_found": found_r, "unexpected": bad, "has_total": has_total}


def forbidden_terms(text: str) -> list[str]:
    low = f" {text.lower()} "
    return [w for w in FORBIDDEN if w in low]


# --------------------------------------------------------------------------- LLM rewording
LANG_DESC = {
    "hi-en": "Hinglish written in Devanagari script, with common English words (salary, payment, link, message, plan) "
             "kept in Latin letters, as people in Hyderabad speak",
    "te-IN": "simple spoken Telugu in Telugu script, with common English words (salary, payment, link) allowed",
    "en": "simple Indian English",
}
TONE = {
    "polite": "warm and polite: a gentle first request",
    "firm": "clear and firm but respectful: a reminder that states the amount, when it was due and that the work log is attached",
    "formal": "formal and respectful: cites the law slot, asks for payment or a reply, and names the free legal-aid slot as the next step",
}
LLM_SCHEMA = {
    "type": "object",
    "properties": {"sentences": {"type": "array", "items": {"type": "string"}}},
    "required": ["sentences"],
    "additionalProperties": False,
}
_DIGITS = re.compile(r"[0-9०-९౦-౯₹]")


def _llm_validator(allowed_slots: set[str], required: set[str]):
    def validate(out: Any) -> list[str]:
        sents = out.get("sentences") if isinstance(out, dict) else None
        if not isinstance(sents, list) or not 2 <= len(sents) <= 9:
            raise ValueError("need 2-9 sentences")
        clean, seen = [], set()
        for s in sents:
            if not isinstance(s, str) or not s.strip() or len(s) > 260:
                raise ValueError("bad sentence")
            s = s.strip()
            ph = _placeholders(s)
            if ph - allowed_slots:
                raise ValueError(f"unknown placeholders {ph - allowed_slots}")
            if _DIGITS.search(re.sub(r"\{[a-z_]+\}", "", s)):
                raise ValueError("digits outside placeholders")
            if forbidden_terms(s):
                raise ValueError("forbidden wording")
            seen |= ph
            clean.append(s)
        if required - seen:
            raise ValueError(f"missing placeholders {required - seen}")
        return clean
    return validate


async def llm_reword(step: str, lang: str, template: list[str], slots: dict[str, str]) -> list[str] | None:
    if not llm.configured():
        return None
    # Only the slots this step's template uses: a Polite note may never pick up the law or legal-aid slots.
    used = set().union(*(_placeholders(t) for t in template)) if template else set()
    allowed_slots = {k for k in used if slots.get(k)}
    required = ({"total", "reply_by", "employer"} | ({"law", "legal_aid"} if step == "formal" else set())) & allowed_slots
    system = (
        "You polish a short voice-note message from a domestic worker in Hyderabad to the household employer "
        f"who owes her wages. Write in {LANG_DESC[norm_lang(lang)]}. Tone: {TONE[step]}.\n"
        "Rules: keep the meaning of the draft and do not add facts. Use the {placeholders} exactly as written; "
        "never write any digit, amount, date, number or phone number yourself, only placeholders. "
        f"Allowed placeholders: {', '.join('{' + s + '}' for s in sorted(allowed_slots))}. "
        f"Every one of these must appear at least once: {', '.join('{' + s + '}' for s in sorted(required))}. "
        "Never threaten. Never mention penalties, fines, police, jail, court, lawyers, compensation, interest, "
        "bonus or any multiple of the amount, and never promise a legal outcome. Do not add an AI disclosure "
        "(it is added separately). Speak in the first person as the worker; avoid gendered verb forms. "
        "Return JSON {\"sentences\": [...]}, 3 to 8 short sentences, one per item, each under 25 words."
    )
    user = json.dumps({"step": step, "draft_sentences": template}, ensure_ascii=False)
    try:
        return await llm.json_call(system, user, LLM_SCHEMA, name="ladder_message",
                                   validate=_llm_validator(allowed_slots, required), max_tokens=900)
    except Exception as exc:  # never let the LLM break the ladder
        log.warning("llm reword failed: %s", str(exc)[:120])
        return None


# --------------------------------------------------------------------------- entry point
async def compose(ctx: CaseCtx, step: str, *, voice_mode: str = "stock", use_llm: bool = True,
                  lang: str | None = None, today: dt.date | None = None) -> Draft:
    """Write one ladder step for this case in the employer's language (or `lang`)."""
    if step not in STEPS:
        raise ValueError(f"step must be one of {STEPS}")
    lang = norm_lang(lang or ctx.employer.language)
    d_slots, s_slots, allowed, reply_by = build_slots(ctx, lang, today)
    male = is_male(ctx.worker.name)
    template = template_sentences(step, lang, d_slots, male=male)
    spoken_extra = [_fill(x, s_slots) for x in template_sentences(step, lang, d_slots, male=male, speech_only=True)]
    disc = disclosure(ctx.worker.name, lang, voice_mode)
    mask = [ctx.worker.phone or "", ctx.employer.phone or "", ctx.worker.upi_vpa or ""]

    def render(sents: list[str]) -> tuple[list[str], list[str]]:
        return [_fill(s, d_slots) for s in sents], [_fill(s, s_slots) for s in sents]

    def check(disp: list[str], speech: list[str]) -> dict[str, Any]:
        ok_d, info_d = verify_amounts(disp, lang, allowed, ctx.balance or None, mask)
        ok_s, info_s = verify_amounts(speech, lang, allowed, ctx.balance or None, mask)
        bad_words = forbidden_terms(" ".join(disp + speech))
        return {"ok": ok_d and ok_s and not bad_words, "display": info_d, "speech": info_s,
                "forbidden": bad_words}

    source, checks = "template", {}
    disp, speech = render(template)
    if use_llm:
        sents = await llm_reword(step, lang, template, d_slots)
        if sents:
            ld, ls = render(sents)
            c = check(ld, ls)
            if c["ok"]:
                disp, speech, source, checks = ld, ls, "llm", c
            else:
                checks = {"llm_rejected": c}
    tc = check(disp, speech)
    checks = {**checks, **tc}
    if not tc["ok"] and source == "llm":  # belt and braces: should never happen
        disp, speech = render(template)
        source, checks = "template", {**check(disp, speech), "llm_rejected": tc}
    if spoken_extra:  # e.g. "their numbers are in the letter": spoken before the closing thanks
        speech = speech[:-1] + spoken_extra + speech[-1:] if len(speech) > 1 else speech + spoken_extra
    return Draft(step=step, lang=lang, display_sentences=disp, speech_sentences=speech,
                 disclosure_display=disc, disclosure_speech=disc, source=source,
                 slots_display=d_slots, slots_speech=s_slots, allowed_amounts=allowed,
                 reply_by=reply_by, checks=checks)


# --------------------------------------------------------------------------- small shared bits
def upi_link(vpa: str | None, name: str, amount: float) -> str | None:
    """upi://pay?pa=<vpa>&pn=<name>&am=<amount>&cu=INR&tn=Baaki"""
    if not vpa:
        return None
    from urllib.parse import quote

    a = round(float(amount), 2)
    am = str(int(a)) if a == int(a) else f"{a:.2f}"
    return f"upi://pay?pa={quote(vpa, safe='@.')}&pn={quote(name)}&am={am}&cu=INR&tn=Baaki"


def employer_url(token: str) -> str:
    return f"{config.public_base_url()}/e/{token}"


_ABBR = re.compile(r"(?:\b(?:No|Ms|Rs|Dr|Mr|Mrs|St|s|G|O|vs|etc)\.)$", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """Split text for one-sentence-per-call TTS (keeps G.O.Ms.No.6, Rs. and s.17 together)."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    out, buf = [], ""
    for piece in re.split(r"(?<=[।?!.])\s+", text):
        buf = f"{buf} {piece}".strip() if buf else piece
        if piece.endswith(".") and _ABBR.search(piece):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out
