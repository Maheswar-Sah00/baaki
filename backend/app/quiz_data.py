"""V08 Fair or Not?: the five myth cards for employers. Pure data + pure functions, no I/O, nothing stored.

Every claim is checked against docs/research/02_law_procedure_telangana.md section 8 A and the source texts in
docs/research/sources/ (CodeOnWages2019.txt, TG_GOMs6_2026.txt). Every rupee figure is derived from app.wages, so
the quiz can never drift from the calculator. Tone rules: "the Code says", information not advice, no penalties,
no multipliers, no outcomes promised. Part-time figures are labelled as estimates.

Languages: "en", "hi-en" (Hinglish: Devanagari with English words, like app.messages) and "te" (Telugu).
"""
from __future__ import annotations

import re
from typing import Any

from . import wages
from .check_core import SOURCE_URL as GO6_URL

LANGS = ("en", "hi-en", "te")
DEFAULT_LANG = "en"
CHOICES = ("fair", "not_fair")
CODE_URL = "https://egazette.gov.in/WriteReadData/2019/210356.pdf"  # Gazette of India, Act 29 of 2019

DISCLAIMER = {
    "en": "General information from the Code on Wages, 2019 and G.O.Ms.No.6 (Telangana), not legal advice.",
    "hi-en": "Code on Wages, 2019 और G.O.Ms.No.6 (Telangana) से general जानकारी, legal advice नहीं।",
    "te": "Code on Wages, 2019 మరియు G.O.Ms.No.6 (తెలంగాణ) నుండి సాధారణ సమాచారం, న్యాయ సలహా కాదు.",
}
DISCLAIMER_EN = DISCLAIMER["en"]

LABELS = {
    "en": {"fair": "Fair", "not_fair": "Not fair", "right": "You got it", "wrong": "Not quite",
           "title": "Fair or Not?", "intro": "Five things employers often believe about paying house help. "
           "Tap Fair or Not fair, then see what the Code on Wages says.",
           "estimate": "Estimate"},
    "hi-en": {"fair": "Fair", "not_fair": "Not fair", "right": "सही जवाब", "wrong": "नहीं, असल में",
              "title": "Fair or Not?", "intro": "घर के काम वालों की salary पर पाँच आम बातें। Fair या Not fair "
              "चुनिए, फिर देखिए Code on Wages क्या कहता है।",
              "estimate": "अनुमान"},
    "te": {"fair": "న్యాయం", "not_fair": "న్యాయం కాదు", "right": "సరైన జవాబు", "wrong": "కాదు, నిజానికి",
           "title": "Fair or Not?", "intro": "ఇంటి పనివారి జీతం గురించి యజమానులు తరచూ నమ్మే ఐదు విషయాలు. "
           "న్యాయం లేదా న్యాయం కాదు ఎంచుకోండి, తర్వాత Code on Wages ఏమి చెబుతుందో చూడండి.",
           "estimate": "అంచనా"},
}

# --------------------------------------------------------------------------- numbers (all from app.wages)
_MONTH = "2026-11"  # any month on or after 1 Jun 2026 uses G.O.Ms.No.6
MONTHLY = wages.GO6_MONTHLY["unskilled"]                 # 16,000: full-time maid, Zone-I (Hyderabad)
PER_DAY = wages.per_day_rate("unskilled")                # 615.50 = 16,000 / 26 (G.O. para 5(1))
HALF_DAY = wages.money(PER_DAY / 2)                      # 307.75
LATE_CUT = wages.money(MONTHLY * 15 / (26 * 8 * 60))     # 15 min of a 26 x 8 h month, in proportion (s.20(2))
ADVANCE = 10000.0                                        # synthetic example
HALF_MONTH = wages.money(MONTHLY * 0.5)                  # s.18(3): all deductions <= 50% of the month's wages
AGREED = 9000.0                                          # synthetic example (same as the demo case)
LOW_PAY = 10000.0                                        # synthetic example
_PT = wages.minimum_wage(_MONTH, "unskilled", hours_per_day=2, days_per_week=6)
PART_TIME_2H = float(_PT.amount)                         # 4,000, an estimate (the order lists no part-time rate)
assert _PT.is_estimate and not wages.minimum_wage(_MONTH, "unskilled").is_estimate


def inr(x: float) -> str:
    """Rs 16,000 -> ₹16,000 (Indian grouping from wages.fmt_inr)."""
    return wages.fmt_inr(x).replace("Rs ", "₹")


NUMBERS: dict[str, float] = {
    "m": MONTHLY, "per_day": PER_DAY, "half_day": HALF_DAY, "late_cut": LATE_CUT, "adv": ADVANCE,
    "half": HALF_MONTH, "agreed": AGREED, "low": LOW_PAY, "pt": PART_TIME_2H,
}
_FMT = {k: inr(v) for k, v in NUMBERS.items()}

S60_SOURCE = ("Code on Wages, 2019, s.60: a contract or agreement by which an employee gives up any amount due "
              "under the Code is null and void in so far as it removes or reduces that amount. s.5: no employer "
              "shall pay any employee less than the notified minimum rate of wages.")

# --------------------------------------------------------------------------- the five cards
# answer = what the Code says about the statement on the card ("fair" = in line with it).
CARDS: list[dict[str, Any]] = [
    {
        "id": "late",
        "answer": "not_fair",
        "section": "Code on Wages, 2019, s.20(2)",
        "source": wages.SRC_S20,
        "source_url": CODE_URL,
        "is_estimate": False,
        "text": {
            "en": {
                "myth": "She came 15 minutes late. You cut half a day's pay.",
                "rule": "The Code says a cut for absence can only be in proportion to the time missed.",
                "detail": "15 minutes is 1/32 of an 8-hour day. On a full-time {m} wage that comes to about "
                          "{late_cut}, not the {half_day} of half a day.",
            },
            "hi-en": {
                "myth": "वो 15 मिनट late आई। आपने आधे दिन की salary काट ली।",
                "rule": "Code कहता है: absence की cutting सिर्फ़ उतनी ही हो सकती है, जितना time miss हुआ।",
                "detail": "8 घंटे के दिन में 15 मिनट 1/32 हिस्सा है। {m} की full-time salary पर ये लगभग "
                          "{late_cut} बनता है, आधे दिन के {half_day} नहीं।",
            },
            "te": {
                "myth": "ఆమె 15 నిమిషాలు ఆలస్యంగా వచ్చింది. మీరు సగం రోజు జీతం కట్ చేశారు.",
                "rule": "కోడ్ ప్రకారం: గైర్హాజరు కోత, పని చేయని సమయానికి అనుపాతంలో మాత్రమే ఉండాలి.",
                "detail": "8 గంటల రోజులో 15 నిమిషాలు 1/32 భాగం. {m} పూర్తి సమయం జీతంపై అది సుమారు {late_cut}, "
                          "సగం రోజు {half_day} కాదు.",
            },
        },
    },
    {
        "id": "payday",
        "answer": "fair",
        "section": "Code on Wages, 2019, s.17(1)(iv) and s.17(2)",
        "source": wages.SRC_S17_1 + " " + wages.SRC_S17_2,
        "source_url": CODE_URL,
        "is_estimate": False,
        "text": {
            "en": {
                "myth": "You pay October's salary on 5 November.",
                "rule": "The Code says monthly wages are due before the 7th day of the next month is over, "
                        "so the 5th is on time.",
                "detail": "If she leaves or is removed, the Code says her wages are due within two working days "
                          "(s.17(2)).",
            },
            "hi-en": {
                "myth": "आप October की salary 5 November को देते हैं।",
                "rule": "Code कहता है: monthly salary अगले महीने की 7 तारीख़ ख़त्म होने से पहले देनी है। "
                        "तो 5 तारीख़ time पर है।",
                "detail": "अगर वो काम छोड़े या उसे हटाया जाए, तो Code कहता है उसकी salary दो working days में "
                          "देनी है (s.17(2))।",
            },
            "te": {
                "myth": "మీరు అక్టోబర్ జీతం నవంబర్ 5న ఇస్తారు.",
                "rule": "కోడ్ ప్రకారం: నెల జీతం తర్వాతి నెల 7వ తేదీ ముగిసేలోపు ఇవ్వాలి. కాబట్టి 5వ తేదీ సమయానికే.",
                "detail": "ఆమె పని మానేసినా, ఆమెను తీసేసినా, జీతం రెండు పని దినాల్లో ఇవ్వాలని కోడ్ చెబుతుంది "
                          "(s.17(2)).",
            },
        },
    },
    {
        "id": "advance",
        "answer": "not_fair",
        "section": "Code on Wages, 2019, s.18(2)(f) and s.18(3)",
        "source": wages.SRC_S18 + " s.18(2)(f): recovery of an advance is an authorised deduction.",
        "source_url": CODE_URL,
        "is_estimate": False,
        "text": {
            "en": {
                "myth": "She took a {adv} advance. You take all of it back from one month's {m} salary.",
                "rule": "The Code allows recovering an advance, but all cuts in one month together cannot go "
                        "above half of that month's wages.",
                "detail": "Half of {m} is {half}. The rest of the advance can come out of later months.",
            },
            "hi-en": {
                "myth": "उसने {adv} advance लिया। आप एक ही महीने की {m} salary से पूरा वापस काट लेते हैं।",
                "rule": "Code advance की recovery allow करता है, पर एक महीने की सारी cutting मिलाकर उस महीने की "
                        "salary के आधे से ज़्यादा नहीं हो सकती।",
                "detail": "{m} का आधा {half} है। बाक़ी advance अगले महीनों में कट सकता है।",
            },
            "te": {
                "myth": "ఆమె {adv} అడ్వాన్స్ తీసుకుంది. మీరు ఒకే నెల {m} జీతం నుండి మొత్తం తిరిగి కట్ చేస్తారు.",
                "rule": "అడ్వాన్స్ తిరిగి తీసుకోవడానికి కోడ్ అనుమతిస్తుంది, కానీ ఒక నెలలో అన్ని కోతలు కలిపి ఆ నెల "
                        "జీతంలో సగానికి మించకూడదు.",
                "detail": "{m}లో సగం {half}. మిగిలిన అడ్వాన్స్ తర్వాతి నెలల్లో తీసుకోవచ్చు.",
            },
        },
    },
    {
        "id": "agreed",
        "answer": "not_fair",
        "section": "Code on Wages, 2019, s.60 (with s.5)",
        "source": S60_SOURCE,
        "source_url": CODE_URL,
        "is_estimate": False,
        "text": {
            "en": {
                "myth": "She agreed to {agreed} a month for full-time work, below the minimum. "
                        "Since she agreed, it's settled.",
                "rule": "The Code says an agreement to take less than what the Code makes due is void, as far as "
                        "it cuts that amount.",
                "detail": "Section 5 says no employer pays less than the minimum wage. Her yes does not change the "
                          "minimum: for a full-time maid in Hyderabad it is {m} a month.",
            },
            "hi-en": {
                "myth": "Full-time काम के लिए वो {agreed} महीना पर मान गई, minimum से कम। वो मान गई, तो बात पक्की।",
                "rule": "Code कहता है: Code के हिसाब से बनने वाले पैसे को कम करने वाला agreement उतने हिस्से में "
                        "void है।",
                "detail": "Section 5 कहता है कोई employer minimum wage से कम नहीं देगा। उसकी 'हाँ' से minimum नहीं "
                          "बदलता: Hyderabad में full-time maid के लिए ये {m} महीना है।",
            },
            "te": {
                "myth": "పూర్తి సమయం పనికి నెలకు {agreed}కి ఆమె ఒప్పుకుంది, కనీస వేతనం కంటే తక్కువ. ఆమె ఒప్పుకుంది "
                        "కాబట్టి అది సరే.",
                "rule": "కోడ్ ప్రకారం: కోడ్ ఇచ్చే మొత్తాన్ని తగ్గించే ఒప్పందం, ఆ మేరకు చెల్లదు.",
                "detail": "కనీస వేతనం కంటే తక్కువ ఏ యజమానీ ఇవ్వకూడదని సెక్షన్ 5 చెబుతుంది. ఆమె 'సరే' అన్నా కనీస "
                          "వేతనం మారదు: హైదరాబాద్‌లో పూర్తి సమయం పనిమనిషికి అది నెలకు {m}.",
            },
        },
    },
    {
        "id": "minimum",
        "answer": "not_fair",
        "section": "G.O.Ms.No.6 (Telangana), 30.05.2026, Table 1, Zone-I",
        "source": wages.minimum_wage(_MONTH, "unskilled").source + " " + wages.SRC_ESTIMATE,
        "source_url": GO6_URL,
        "is_estimate": True,  # the part-time line in the detail is Baaki's estimate
        "text": {
            "en": {
                "myth": "You pay a full-time maid in Hyderabad (8 hours, 6 days a week) {low} a month. "
                        "That meets the minimum.",
                "rule": "Telangana's minimum for a full-time maid in Hyderabad is {m} a month basic, from "
                        "1 June 2026.",
                "detail": "That is {per_day} a day (monthly ÷ 26). For 2 hours a day, 6 days a week, Baaki "
                          "estimates about {pt} a month; the order lists no part-time rate, so that figure is an "
                          "estimate. VDA is extra when notified.",
            },
            "hi-en": {
                "myth": "Hyderabad में full-time maid (8 घंटे, हफ़्ते में 6 दिन) को आप {low} महीना देते हैं। "
                        "ये minimum पूरा करता है।",
                "rule": "Hyderabad में full-time maid के लिए Telangana का minimum, 1 June 2026 से, {m} महीना "
                        "basic है।",
                "detail": "यानी {per_day} रोज़ (महीना ÷ 26)। रोज़ 2 घंटे, हफ़्ते में 6 दिन के लिए Baaki का अनुमान "
                          "लगभग {pt} महीना है; order में part-time rate नहीं है, इसलिए ये estimate है। VDA notify "
                          "होने पर अलग से।",
            },
            "te": {
                "myth": "హైదరాబాద్‌లో పూర్తి సమయం పనిమనిషికి (8 గంటలు, వారానికి 6 రోజులు) మీరు నెలకు {low} "
                        "ఇస్తారు. అది కనీస వేతనానికి సరిపోతుంది.",
                "rule": "హైదరాబాద్‌లో పూర్తి సమయం పనిమనిషికి తెలంగాణ కనీస వేతనం 1 జూన్ 2026 నుండి నెలకు {m} "
                        "బేసిక్.",
                "detail": "అంటే రోజుకు {per_day} (నెల ÷ 26). రోజుకు 2 గంటలు, వారానికి 6 రోజులకు Baaki అంచనా "
                          "సుమారు నెలకు {pt}; ఉత్తర్వులో పార్ట్-టైమ్ రేటు లేదు, కాబట్టి ఇది అంచనా మాత్రమే. VDA "
                          "ప్రకటించినప్పుడు అదనం.",
            },
        },
    },
]
CARD_IDS = tuple(c["id"] for c in CARDS)
_BY_ID = {c["id"]: c for c in CARDS}

# --------------------------------------------------------------------------- score lines
SCORE_LINES = {
    "en": {"top": "Spot on. You know the rules better than most.",
           "mid": "Close. A couple of rules surprise most employers.",
           "low": "Most employers miss these. Now you know.",
           "share": "I scored {score}/{total} on Fair or Not?, a 40-second quiz on what the Code on Wages says "
                    "about paying house help in Hyderabad. Try it:",
           "check": "Check what you pay in 30 seconds"},
    "hi-en": {"top": "बिल्कुल सही। आप rules ज़्यादातर लोगों से बेहतर जानते हैं।",
              "mid": "क़रीब। कुछ rules ज़्यादातर employers को चौंकाते हैं।",
              "low": "ज़्यादातर employers ये miss करते हैं। अब आप जानते हैं।",
              "share": "Fair or Not? में मेरा score {score}/{total}: Hyderabad में घर के काम वालों की salary पर "
                       "Code on Wages क्या कहता है, 40 second का quiz। आप भी try कीजिए:",
              "check": "30 second में अपनी salary check कीजिए"},
    "te": {"top": "అద్భుతం. చాలా మంది కంటే మీకు నియమాలు బాగా తెలుసు.",
           "mid": "దగ్గరగా ఉన్నారు. కొన్ని నియమాలు చాలా మంది యజమానులను ఆశ్చర్యపరుస్తాయి.",
           "low": "చాలా మంది యజమానులు ఇవి మిస్ అవుతారు. ఇప్పుడు మీకు తెలుసు.",
           "share": "Fair or Not?లో నా స్కోర్ {score}/{total}: హైదరాబాద్‌లో ఇంటి పనివారి జీతం గురించి Code on "
                    "Wages ఏమి చెబుతుందో 40 సెకన్ల క్విజ్. మీరూ ప్రయత్నించండి:",
           "check": "30 సెకన్లలో మీ జీతం చెక్ చేయండి"},
}


# --------------------------------------------------------------------------- functions
def norm_lang(lang: str | None) -> str:
    x = (lang or "").strip().lower()
    if x in ("hi-en", "hinglish", "hi", "hi-in", "hindi"):
        return "hi-en"
    if x in ("te", "te-in", "telugu"):
        return "te"
    return DEFAULT_LANG


def _fill(s: str) -> str:
    return s.format(**_FMT)


def card_text(card_id: str, lang: str) -> dict[str, str]:
    t = _BY_ID[card_id]["text"][norm_lang(lang)]
    return {k: _fill(v) for k, v in t.items()}


def public_card(card: dict[str, Any], lang: str, n: int) -> dict[str, Any]:
    """The card as shown before answering: the statement only, no answer."""
    lang = norm_lang(lang)
    return {"id": card["id"], "n": n, "myth": card_text(card["id"], lang)["myth"],
            "section": card["section"], "disclaimer": DISCLAIMER[lang]}


def deck(lang: str | None) -> dict[str, Any]:
    lang = norm_lang(lang)
    lab = LABELS[lang]
    return {
        "lang": lang, "langs": list(LANGS), "title": lab["title"], "intro": lab["intro"],
        "choices": [{"id": "fair", "label": lab["fair"]}, {"id": "not_fair", "label": lab["not_fair"]}],
        "total": len(CARDS),
        "cards": [public_card(c, lang, i + 1) for i, c in enumerate(CARDS)],
        "disclaimer": DISCLAIMER[lang], "disclaimer_en": DISCLAIMER_EN,
        "check_url": "/check",
    }


def reveal(card_id: str, choice: str | None, lang: str | None) -> dict[str, Any]:
    """The answer for one card. choice may be None (just reveal)."""
    if card_id not in _BY_ID:
        raise KeyError(card_id)
    lang = norm_lang(lang)
    card = _BY_ID[card_id]
    lab = LABELS[lang]
    t = card_text(card_id, lang)
    correct = None if choice is None else (choice == card["answer"])
    return {
        "id": card_id,
        "n": CARD_IDS.index(card_id) + 1,
        "myth": t["myth"],
        "choice": choice,
        "answer": card["answer"],
        "answer_label": lab[card["answer"]],
        "correct": correct,
        "feedback": None if correct is None else lab["right" if correct else "wrong"],
        "rule": t["rule"],
        "detail": t["detail"],
        "section": card["section"],
        "source": card["source"],
        "source_url": card["source_url"],
        "is_estimate": card["is_estimate"],
        "disclaimer": DISCLAIMER[lang],
        "disclaimer_en": DISCLAIMER_EN,
    }


def narration_text(card_id: str, lang: str = "hi-en") -> str:
    """What the optional narration says for a card: the verdict, then the rule (no amounts beyond the card's)."""
    lang = norm_lang(lang)
    card = _BY_ID[card_id]
    text = f"{LABELS[lang][card['answer']]}. {card_text(card_id, lang)['rule']}"
    word = {"en": "rupees", "hi-en": "रुपये", "te": "రూపాయలు"}[lang]
    return re.sub(r"₹([\d,.]+)", lambda m: f"{m.group(1)} {word}", text)  # speak "16,000 रुपये", not the sign


def score(answers: dict[str, str], lang: str | None) -> dict[str, Any]:
    lang = norm_lang(lang)
    results = [reveal(cid, answers.get(cid), lang) for cid in CARD_IDS]
    got = sum(1 for r in results if r["correct"])
    total = len(CARDS)
    lines = SCORE_LINES[lang]
    band = "top" if got == total else "mid" if got >= total - 2 else "low"
    return {
        "lang": lang, "score": got, "total": total, "answered": sum(1 for r in results if r["choice"]),
        "headline": f"{got}/{total}", "message": lines[band],
        "share_text": lines["share"].format(score=got, total=total),
        "check_url": "/check", "check_label": lines["check"],
        "results": results, "disclaimer": DISCLAIMER[lang], "disclaimer_en": DISCLAIMER_EN,
    }


def all_strings() -> list[str]:
    """Every user-facing string in every language (for the wording tests)."""
    out: list[str] = list(DISCLAIMER.values())
    for lab in LABELS.values():
        out += list(lab.values())
    for lines in SCORE_LINES.values():
        out += list(lines.values())
    for c in CARDS:
        out += [c["section"], c["source"]]
        for lang in LANGS:
            out += list(card_text(c["id"], lang).values())
    return out
