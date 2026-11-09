"""PDFs: the itemised card (Polite, Firm), the bilingual demand letter (Formal) and the legal-aid pack.

Built on app/pdf.py (fpdf2 + uharfbuzz shaping, Noto Sans / Telugu / Devanagari). Content rules from
docs/research/02_law_procedure_telangana.md section 6: facts, the itemised claim and how it is
calculated, a 7-day reply date, a polite next step (Telangana Labour Department, DLSA / NALSA 15100,
India Labourline 1800 833 9020), a signature line and the not-legal-advice line. No multiples,
penalties, threats or promised outcomes; nothing that looks like a government or lawyer letterhead.
The route is the state's, never SAMADHAN (central sphere only).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

from fpdf import FPDF

from . import pdf as pdfmod
from .lang import today_ist
from .messages import (DLSA, GO_CITATION, INDIA_LABOURLINE, NALSA, CaseCtx, Draft, fmt_date, fmt_money,
                       item_label, norm_lang)

INK = (40, 28, 20)
MUTED = (110, 92, 80)
ACCENT = (150, 70, 30)      # warm rust; no blue (UI rule)
RULE = (210, 190, 170)

RATES = {  # G.O.Ms.No.6, Zone-I Hyderabad, basic per month (02_law section 8C)
    "unskilled": 16000, "semi_skilled": 17000, "skilled": 18500, "highly_skilled": 20000,
}

T = {  # fixed strings: employer language first, English always alongside
    "title_formal": {"hi-en": "बकाया वेतन के भुगतान के लिए पत्र", "te-IN": "బాకీ జీతం చెల్లింపు కోసం లేఖ",
                     "en": "Letter requesting payment of unpaid wages"},
    "title_card": {"hi-en": "बकाया वेतन का हिसाब", "te-IN": "బాకీ జీతం లెక్క", "en": "Itemised unpaid wages"},
    "items": {"hi-en": "बकाया का पूरा हिसाब", "te-IN": "బాకీ పూర్తి లెక్క", "en": "Itemised claim"},
    "total": {"hi-en": "कुल बाकी", "te-IN": "మొత్తం బాకీ", "en": "Total due"},
    "paid": {"hi-en": "मिल चुका", "te-IN": "అందినది", "en": "Already received"},
    "balance": {"hi-en": "अभी बाकी", "te-IN": "ఇంకా బాకీ", "en": "Balance due"},
    "pay_by": {"hi-en": "कृपया {d} तक भुगतान करें", "te-IN": "దయచేసి {d} లోపు చెల్లించండి", "en": "Please pay by {d}"},
    "upi": {"hi-en": "UPI से भुगतान", "te-IN": "UPI ద్వారా చెల్లింపు", "en": "Pay by UPI"},
    "info_only": {"hi-en": "सिर्फ़ जानकारी के लिए (कुल में नहीं जोड़ा)", "te-IN": "సమాచారం కోసం మాత్రమే (మొత్తంలో కలపలేదు)",
                  "en": "Shown for information only (not added to the total)"},
    "diary": {"hi-en": "Kaam Diary (काम का रिकॉर्ड)", "te-IN": "పని డైరీ (పని నమోదు)", "en": "Work diary (Kaam Diary)"},
    "sign": {"hi-en": "हस्ताक्षर / अंगूठे का निशान", "te-IN": "సంతకం / వేలిముద్ర", "en": "Signature / thumb impression"},
}

DISCLAIMER = {
    "en": ("Baaki is an information tool, not a lawyer and not a government office. It does not give legal advice. "
           "Amounts are calculated from the Telangana minimum wage order (G.O.Ms.No.6, 2026) and what the worker told us; "
           "part-time minimum-wage figures are estimates. Check with the Labour Department or the free legal aid office "
           f"(DLSA, NALSA helpline {NALSA}) before acting."),
    "hi-en": ("Baaki एक जानकारी देने वाला ऐप है, वकील या सरकारी दफ़्तर नहीं। यह कानूनी सलाह नहीं है। रकम Telangana के "
              "न्यूनतम वेतन आदेश (G.O.Ms.No.6, 2026) और कामगार की बताई बातों से निकाली गई है; part-time के आंकड़े अनुमान हैं।"),
    "te-IN": ("బాకీ ఒక సమాచార యాప్ మాత్రమే, లాయర్ లేదా ప్రభుత్వ కార్యాలయం కాదు. ఇది న్యాయ సలహా కాదు. మొత్తాలు తెలంగాణ "
              "కనీస వేతన ఉత్తర్వు (G.O.Ms.No.6, 2026) మరియు కార్మికులు చెప్పిన వివరాల ఆధారంగా లెక్కించబడ్డాయి; పార్ట్-టైమ్ లెక్కలు అంచనాలు."),
}

ROUTE_EN = [
    "1. Telangana Labour Department, Hyderabad: a wage claim under section 45 of the Code on Wages, 2019, filed by "
    "the worker (Assistant Commissioner of Labour for the area). Online: labour.telangana.gov.in, "
    "'Register New Complaint', category 'Employee Grievances'.",
    f"2. Free legal aid: {DLSA}, Nyaya Seva Sadan, Hyderabad 500002. Women, and people with an annual income below ₹1,00,000, are among those "
    "entitled to free legal aid (TSLSA). "
    f"NALSA helpline {NALSA}. A pre-litigation Lok Adalat has no court fee.",
    f"3. India Labourline {INDIA_LABOURLINE} (toll-free; Hyderabad desk at Montfort Social Institute): "
    "counselling, mediation and case support for informal workers.",
    "Not SAMADHAN: that portal handles central-sphere employers only.",
]


@dataclass
class LetterInput:
    ctx: CaseCtx
    step: str                          # polite | firm | formal | legal_pack
    draft: Optional[Draft] = None      # the message in the employer's language
    draft_en: Optional[Draft] = None   # the same message in English (formal letter)
    upi_link: Optional[str] = None
    statement_translation: Optional[str] = None   # English translation of the worker's own words
    history: list[dict] = field(default_factory=list)   # messages already sent (legal pack)
    today: Optional[dt.date] = None


# --------------------------------------------------------------------------- low-level drawing
def _font_for(pdf: FPDF, text: str, size: float) -> None:
    main = pdfmod.SCRIPT_FONT[pdfmod._script(text or "a")]
    pdf.set_font(main, size=size)
    pdf.set_fallback_fonts([f for f in ("NotoSans", "NotoTelugu", "NotoDeva") if f != main], exact_match=False)


def _para(pdf: FPDF, text: str, size: float = 10.5, color=INK, after: float = 2.0, align: str = "L") -> None:
    if not text:
        return
    _font_for(pdf, text, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, size * 0.55, text, new_x="LMARGIN", new_y="NEXT", align=align)
    pdf.ln(after)


def _heading(pdf: FPDF, text: str, size: float = 13) -> None:
    if pdf.get_y() > pdf.h - 40:
        pdf.add_page()
    pdf.ln(1.5)
    _para(pdf, text, size=size, color=ACCENT, after=1.0)
    y = pdf.get_y()
    pdf.set_draw_color(*RULE)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(2)


def _lines(pdf: FPDF, w: float, text: str, size: float) -> int:
    _font_for(pdf, text, size)
    try:
        return max(1, len(pdf.multi_cell(w, size * 0.5, text, dry_run=True, output="LINES")))
    except Exception:
        return max(1, int(pdf.get_string_width(text) / max(w - 2, 1)) + 1)


def _row(pdf: FPDF, cols: list[tuple[float, str, str]], size: float = 9.5, color=INK, rule: bool = True) -> None:
    lh = size * 0.5
    h = max(_lines(pdf, w, t, size) for w, t, _ in cols) * lh + 1.6
    if pdf.get_y() + h > pdf.h - pdf.b_margin:
        pdf.add_page()
    y0, x = pdf.get_y(), pdf.l_margin
    pdf.set_text_color(*color)
    for w, t, align in cols:
        _font_for(pdf, t, size)
        pdf.set_xy(x, y0 + 0.8)
        pdf.multi_cell(w, lh, t, align=align, new_x="RIGHT", new_y="TOP")
        x += w
    pdf.set_xy(pdf.l_margin, y0 + h)
    if rule:
        pdf.set_draw_color(*RULE)
        pdf.line(pdf.l_margin, y0 + h, pdf.w - pdf.r_margin, y0 + h)


def _bi(lang: str, key: str, **kw) -> str:
    """'employer-language / English' for a fixed string (English only once when lang is en)."""
    a = T[key][lang].format(**kw)
    b = T[key]["en"].format(**kw)
    return a if lang == "en" else f"{a} / {b}"


# --------------------------------------------------------------------------- sections
def _parties(pdf: FPDF, inp: LetterInput, lang: str) -> None:
    c, w, e = inp.ctx.case, inp.ctx.worker, inp.ctx.employer
    today = inp.today or today_ist()
    ref = f"BAAKI-{c.id}-{(c.employer_token or '')[:6].upper()}"
    _para(pdf, f"{fmt_date(today, 'en')}  ·  Ref {ref}", size=9, color=MUTED, after=1)
    who = f"From: {w.name}" + (f", {w.phone}" if w.phone else "") + f", {w.city or 'Hyderabad'}"
    to = f"To: {e.name}" + (f", {e.locality}" if e.locality else "") + ", Hyderabad"
    _para(pdf, who, size=10, after=0.5)
    _para(pdf, to, size=10, after=2)


def _items_table(pdf: FPDF, inp: LetterInput, lang: str) -> None:
    ctx = inp.ctx
    _heading(pdf, _bi(lang, "items"), size=12)
    W = pdf.w - pdf.l_margin - pdf.r_margin
    cw = [8, W - 8 - 38 - 30, 38, 30]
    _row(pdf, [(cw[0], "#", "L"), (cw[1], "Item", "L"), (cw[2], "Due date", "L"), (cw[3], "Amount", "R")],
         size=9, color=MUTED)
    for n, it in enumerate(ctx.included, 1):
        label = item_label(it, lang) if lang == "en" else f"{item_label(it, lang)}\n{item_label(it, 'en')}"
        if it.is_estimate:
            label += "  (estimate)"
        _row(pdf, [(cw[0], str(n), "L"), (cw[1], label, "L"),
                   (cw[2], fmt_date(it.due_date, "en") if it.due_date else "", "L"),
                   (cw[3], fmt_money(it.amount), "R")])
    _row(pdf, [(cw[0], "", "L"), (cw[1], _bi(lang, "total"), "L"), (cw[2], "", "L"),
               (cw[3], fmt_money(ctx.total_due), "R")], size=10.5, color=ACCENT)
    if ctx.paid:
        _row(pdf, [(cw[0], "", "L"), (cw[1], _bi(lang, "paid"), "L"), (cw[2], "", "L"),
                   (cw[3], "- " + fmt_money(ctx.paid), "R")], size=10)
        _row(pdf, [(cw[0], "", "L"), (cw[1], _bi(lang, "balance"), "L"), (cw[2], "", "L"),
                   (cw[3], fmt_money(ctx.balance), "R")], size=10.5, color=ACCENT)
    info = [i for i in ctx.items if not i.included_in_total]
    if info:
        pdf.ln(2)
        _para(pdf, _bi(lang, "info_only"), size=9.5, color=MUTED, after=0.5)
        for it in info:
            est = " (estimate)" if it.is_estimate else ""
            _row(pdf, [(cw[0], "·", "L"), (cw[1] + cw[2], f"{item_label(it, lang)}{est}" + (
                f" / {item_label(it, 'en')}" if lang != "en" else ""), "L"), (cw[3], fmt_money(it.amount), "R")],
                size=9, color=MUTED)
    pdf.ln(2)


def _payment(pdf: FPDF, inp: LetterInput, lang: str) -> None:
    reply_by = inp.draft.reply_by if inp.draft else ((inp.today or today_ist()) + dt.timedelta(days=7)).isoformat()
    _para(pdf, T["pay_by"][lang].format(d=fmt_date(reply_by, lang)), size=11, color=ACCENT, after=0.5)
    if lang != "en":
        _para(pdf, T["pay_by"]["en"].format(d=fmt_date(reply_by, "en")), size=10, after=1)
    vpa = inp.ctx.worker.upi_vpa
    if vpa:
        _para(pdf, f"{_bi(lang, 'upi')}: {vpa}  ·  {fmt_money(inp.ctx.balance)}", size=10, after=0.5)
        if inp.upi_link:
            _para(pdf, inp.upi_link, size=8, color=MUTED, after=1)


def _legal_basis(pdf: FPDF, inp: LetterInput) -> None:
    ctx = inp.ctx
    _heading(pdf, "How this is calculated (legal basis)", size=12)
    cat = (ctx.case.category or ctx.worker.category or "unskilled").replace("-", "_")
    rate = RATES.get(cat)
    lines = [
        f"Minimum wage: {GO_CITATION}. Hyderabad (Zone-I), basic pay"
        + (f": {cat.replace('_', '-')} {fmt_money(rate)} a month ({fmt_money(round(rate / 26 * 2) / 2)} a day = monthly / 26)." if rate else "."),
        "VDA has not been notified after June 2026, so only basic pay is used. Months before June 2026 use G.O.Ms.No.60 (2011 schedule).",
        "Time of payment: Code on Wages, 2019, section 17(1): monthly wages before the end of the 7th day of the next month; "
        "section 17(2): within two working days of removal or dismissal.",
        "Deductions: sections 18 and 20: only authorised deductions, absence cuts in proportion to days absent, "
        "and total deductions never more than 50% of the month's wages.",
        "No penalty, multiple, notice pay, bonus or interest is added to this amount.",
    ]
    srcs = sorted({i.source.strip() for i in ctx.items if i.source and i.source.strip()})
    for s in srcs:
        if s not in " ".join(lines):
            lines.append(f"Source: {s}")
    for ln in lines:
        _para(pdf, "• " + ln, size=9.5, after=0.8)


def _route(pdf: FPDF, lang: str) -> None:
    _heading(pdf, "If this is not resolved: free help" + ({"hi-en": " / मुफ़्त मदद", "te-IN": " / ఉచిత సహాయం"}.get(lang, "")),
             size=12)
    for ln in ROUTE_EN:
        _para(pdf, ln, size=9.5, after=0.8)


def _diary_annex(pdf: FPDF, inp: LetterInput, lang: str) -> None:
    ctx = inp.ctx
    _heading(pdf, f"Annex: {_bi(lang, 'diary')}", size=12)
    entries = ctx.diary
    if not entries:
        _para(pdf, "No diary entries recorded for this employer.", size=9.5, color=MUTED)
        return
    ok, broken_at = True, None
    for i, d in enumerate(entries[1:], 1):
        if d.prev_hash and entries[i - 1].hash and d.prev_hash != entries[i - 1].hash:
            ok, broken_at = False, i + 1
            break
    _para(pdf, f"{len(entries)} entries, each with a timestamp and a SHA-256 hash of the previous entry's hash and its "
               "own fields, so any later change breaks the chain. "
               + ("Chain check: every entry links to the one before it." if ok else f"Chain check: link broken at entry {broken_at}."),
          size=9, color=MUTED, after=1)
    W = pdf.w - pdf.l_margin - pdf.r_margin
    cw = [8, 38, W - 8 - 38 - 46, 46]
    _row(pdf, [(cw[0], "#", "L"), (cw[1], "Time (UTC)", "L"), (cw[2], "Entry", "L"), (cw[3], "Hash (first 16)", "L")],
         size=8.5, color=MUTED)
    for n, d in enumerate(entries[:200], 1):
        _row(pdf, [(cw[0], str(n), "L"), (cw[1], (d.timestamp or "")[:19].replace("T", " "), "L"),
                   (cw[2], (d.text or d.kind)[:140], "L"), (cw[3], (d.hash or "")[:16], "L")], size=8.5)
    if len(entries) > 200:
        _para(pdf, f"... {len(entries) - 200} more entries in the app.", size=8.5, color=MUTED)


def _statement(pdf: FPDF, inp: LetterInput) -> None:
    c = inp.ctx.case
    if not (c.transcript or "").strip():
        return
    wl = norm_lang(c.transcript_lang or inp.ctx.worker.language)
    title = {"te-IN": "కార్మికుల మాటల్లో", "hi-en": "कामगार के अपने शब्दों में", "en": "In the worker's own words"}[wl]
    _heading(pdf, f"{inp.ctx.worker.name}'s statement / {title}", size=12)
    _para(pdf, c.transcript.strip(), size=10.5)
    if wl != "en":
        if inp.statement_translation:
            _para(pdf, "English translation (machine translation, amounts checked against the original):", size=9, color=MUTED, after=0.5)
            _para(pdf, inp.statement_translation, size=10)
        else:
            _para(pdf, "English translation not available; the confirmed facts are in the itemised claim above.",
                  size=9, color=MUTED)


def _signature(pdf: FPDF, inp: LetterInput, lang: str) -> None:
    pdf.ln(4)
    w = inp.ctx.worker
    _para(pdf, "_" * 34, size=10, color=MUTED, after=0)
    _para(pdf, f"{w.name}  ({_bi(lang, 'sign')})", size=10, after=3)


def _disclaimer(pdf: FPDF, lang: str) -> None:
    pdf.ln(2)
    if lang != "en":
        _para(pdf, DISCLAIMER[lang], size=8.5, color=MUTED, after=1)
    _para(pdf, DISCLAIMER["en"], size=8.5, color=MUTED, after=1)


def _header(pdf: FPDF, title_local: str, title_en: str, lang: str, worker: str) -> None:
    _para(pdf, title_local, size=17, color=ACCENT, after=0.5)
    if lang != "en":
        _para(pdf, title_en, size=12.5, color=INK, after=0.5)
    _para(pdf, f"Drafted with the Baaki app at {worker}'s request. Sent by {worker}, not by a lawyer or a government office.",
          size=8.5, color=MUTED, after=2)


# --------------------------------------------------------------------------- documents
def _new(title: str) -> FPDF:
    pdf = pdfmod.new_pdf()
    pdf.set_title(title)
    pdf.set_author("Baaki app (drafting tool)")
    pdf.set_creator("Baaki")
    pdf.add_page()
    return pdf


def render(inp: LetterInput) -> bytes:
    """PDF bytes for one ladder step (or the legal pack)."""
    if inp.step == "legal_pack":
        return render_legal_pack(inp)
    ctx = inp.ctx
    lang = norm_lang(inp.draft.lang if inp.draft else ctx.employer.language)
    formal = inp.step == "formal"
    key = "title_formal" if formal else "title_card"
    pdf = _new(f"Baaki {inp.step} - {ctx.worker.name} to {ctx.employer.name}")
    _header(pdf, T[key][lang], T[key]["en"], lang, ctx.worker.name)
    _parties(pdf, inp, lang)
    if inp.draft:
        _para(pdf, " ".join(inp.draft.display_sentences), size=11, after=2)
    if formal and inp.draft_en and lang != "en":
        _para(pdf, "English:", size=9, color=MUTED, after=0.3)
        _para(pdf, " ".join(inp.draft_en.display_sentences), size=10, after=2)
    _items_table(pdf, inp, lang)
    _payment(pdf, inp, lang)
    if formal:
        _legal_basis(pdf, inp)
        _route(pdf, lang)
        _signature(pdf, inp, lang)
    _disclaimer(pdf, lang)
    if inp.step in ("firm", "formal"):
        pdf.add_page()
        _diary_annex(pdf, inp, lang)
    if formal:
        _statement(pdf, inp)
    return bytes(pdf.output())


def render_legal_pack(inp: LetterInput) -> bytes:
    """Case file for India Labourline / the Telangana Labour Department / DLSA: statement with English
    translation, itemised claim, ladder history, payments and the diary hash chain."""
    ctx = inp.ctx
    c, w, e = ctx.case, ctx.worker, ctx.employer
    pdf = _new(f"Baaki legal aid pack - {w.name}")
    _para(pdf, "Legal aid pack: unpaid wages", size=17, color=ACCENT, after=0.5)
    _para(pdf, f"Prepared with the Baaki app for {w.name}, to take to India Labourline ({INDIA_LABOURLINE}), the Telangana "
               f"Labour Department (Hyderabad) or DLSA Hyderabad / NALSA ({NALSA}). The worker files any claim in their own name.",
          size=9, color=MUTED, after=2)
    _parties(pdf, inp, "en")
    _heading(pdf, "Summary", size=12)
    facts = [
        f"Worker: {w.name} ({w.work_type or c.work_type}, {(c.category or w.category).replace('_', '-')}), {w.city or 'Hyderabad'}.",
        f"Employer: {e.name}" + (f", {e.locality}" if e.locality else "") + ".",
        f"Agreed wage: {fmt_money(c.monthly_wage)} a month; {c.hours_per_day:g} hours a day, {c.days_per_week:g} days a week."
        if c.monthly_wage else "",
        (f"Work period: {c.start_date or '?'} to {c.end_date or 'ongoing'}" + (" (dismissed)." if c.dismissed else ".")),
        f"Balance due: {fmt_money(ctx.balance)} (total {fmt_money(ctx.total_due)}, received {fmt_money(ctx.paid)}).",
    ]
    for f in facts:
        if f:
            _para(pdf, "• " + f, size=10, after=0.6)
    _statement(pdf, inp)
    _items_table(pdf, inp, "en")
    _legal_basis(pdf, inp)
    _heading(pdf, "Messages sent through Baaki", size=12)
    if inp.history:
        for h in inp.history:
            _para(pdf, f"• {h.get('created_at', '')[:10]}  {h.get('step', '')} ({h.get('language', '')}), "
                       f"status {h.get('status', '')}" + (f", voice note ID {h['voice_note_id']}" if h.get("voice_note_id") else ""),
                  size=9.5, after=0.5)
    else:
        _para(pdf, "No messages recorded yet.", size=9.5, color=MUTED)
    pays = [p for p in ctx.payments if p.status == "paid"]
    if pays:
        _heading(pdf, "Payments recorded", size=12)
        for p in pays:
            _para(pdf, f"• {(p.paid_at or p.created_at or '')[:10]}  {fmt_money(p.amount)} by {p.method}", size=9.5, after=0.5)
    _route(pdf, "en")
    _disclaimer(pdf, "en")
    pdf.add_page()
    _diary_annex(pdf, inp, "en")
    return bytes(pdf.output())
