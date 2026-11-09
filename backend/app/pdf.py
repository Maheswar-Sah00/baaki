"""PDF plumbing: fpdf2 + uharfbuzz text shaping with Noto fonts (Latin, Telugu, Devanagari).

Why fpdf2: in the Deposit Wapas test (04_tech_feasibility.md section 7, 8 Nov 2026) fpdf2 2.9 with
shaping rendered Telugu conjuncts like Chromium and copied Telugu text back at 0.97, against 0.48 for
ReportLab. Fonts are in backend/fonts (SIL Open Font License).

Only plumbing: the letter layout and content are TODO (they wait for the law research).
"""
from __future__ import annotations

from dataclasses import dataclass

from fpdf import FPDF

from . import config

FONTS = {
    "NotoSans": "NotoSans-Regular.ttf",
    "NotoTelugu": "NotoSansTelugu-Regular.ttf",
    "NotoDeva": "NotoSansDevanagari-Regular.ttf",
}


def _script(text: str) -> str:
    """'te' | 'hi' | 'latin', by the first Indic letter in the text."""
    for ch in text:
        if "ఀ" <= ch <= "౿":
            return "te"
        if "ऀ" <= ch <= "ॿ":
            return "hi"
    return "latin"


SCRIPT_FONT = {"te": "NotoTelugu", "hi": "NotoDeva", "latin": "NotoSans"}


@dataclass
class Block:
    text: str
    size: float = 12
    space_after: float = 3


def new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    for name, file in FONTS.items():
        pdf.add_font(name, fname=str(config.FONTS_DIR / file))
    pdf.set_text_shaping(True)
    pdf.set_font("NotoSans", size=12)
    return pdf


def write_block(pdf: FPDF, b: Block) -> None:
    """One paragraph. The main font follows the script; Latin words and digits inside Telugu or
    Hindi text fall back to Noto Sans (and the other way round)."""
    main = SCRIPT_FONT[_script(b.text)]
    others = [f for f in ("NotoSans", "NotoTelugu", "NotoDeva") if f != main]
    pdf.set_font(main, size=b.size)
    pdf.set_fallback_fonts(others, exact_match=False)
    pdf.multi_cell(0, b.size * 0.55, b.text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(b.space_after)


def render_pdf(blocks: list[Block | str], title: str | None = None) -> bytes:
    pdf = new_pdf()
    if title:
        pdf.set_title(title)
    pdf.add_page()
    for b in blocks:
        write_block(pdf, b if isinstance(b, Block) else Block(b))
    return bytes(pdf.output())
