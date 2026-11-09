"""Upload -> Prisma transcript: format conversion, 28 s silence splitting, previous_text, context.

Language presets (form field `lang` on /api/stt), from docs/gnani_api/STT_models_prisma-v3.md:
  te        -> "te-IN,en-IN"        Telugu (English words stay Latin with format=transcribe)
  hinglish  -> "hi-IN,en-IN"        Hindi / Hinglish code-mix
  auto      -> "te-IN,hi-IN,en-IN"  either speaker (default)
  indic-auto, or 1-4 raw codes such as "te-IN,hi-IN", are passed through.
Mode `transcribe` (default) writes numbers as digits and keeps English words Latin, which is what
the wage and date parsers want. `codemix` keeps numbers as words; `transliterate` writes Latin.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from starlette.concurrency import run_in_threadpool

from . import audio, config
from .gnani import STT_LANGS, GnaniClient, get_client

LANG_PRESETS = {
    "te": "te-IN,en-IN",
    "te-IN": "te-IN,en-IN",
    "hinglish": "hi-IN,en-IN",
    "hi-en": "hi-IN,en-IN",
    "auto": "te-IN,hi-IN,en-IN",
}
DEFAULT_LANGS = "auto"
MODES = ("transcribe", "codemix", "verbatim", "transliterate")

# TODO(domain): refine with the researchers' vocabulary once the law/number work lands.
DOMAIN_TOPIC = (
    "A domestic worker in Hyderabad and the employer talk about unpaid or underpaid wages: "
    "the monthly salary, days and months worked, advances, how much was paid and how much is "
    "still owed (baaki), rupee amounts said in thousands (vela, hazaar) and the date of payment. "
    "Speech mixes Telugu, Hindi and English."
)
DOMAIN_KEYTERMS = [
    # Latin
    "salary", "baaki", "advance", "rupees", "hazaar", "vela", "jeetham", "kooli", "pagaar",
    "madam", "sir", "amma", "months", "days", "leave", "paid", "pending", "cooking", "cleaning",
    # Telugu script
    "జీతం", "బాకీ", "అడ్వాన్స్", "రూపాయలు", "వేలు", "నెలలు", "రోజులు", "కూలి", "పని",
    # Devanagari
    "तनख्वाह", "पगार", "बाकी", "एडवांस", "रुपये", "हज़ार", "महीने", "दिन", "काम",
]
LATIN_KEYTERMS = [k for k in DOMAIN_KEYTERMS if k.isascii()]


def parse_langs(lang: str | None) -> str:
    """Validate the `lang` form field: a preset, indic-auto, or a comma list of 1-4 codes."""
    raw = (lang or DEFAULT_LANGS).strip()
    raw = LANG_PRESETS.get(raw, LANG_PRESETS.get(raw.lower(), raw))
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    if codes == ["indic-auto"]:
        return "indic-auto"
    if not 1 <= len(codes) <= 4 or any(c not in STT_LANGS for c in codes) or len(set(codes)) != len(codes):
        raise ValueError("lang must be te | hinglish | auto | indic-auto or 1-4 distinct codes such as te-IN,hi-IN,en-IN")
    return ",".join(codes)


def context_for(mode: str, use_context: bool | None = None) -> tuple[list[str] | None, str | None]:
    if use_context is None:
        use_context = config.stt_use_context()
    if not use_context:
        return None, None
    # transliterate output is Latin: docs say write context in Latin letters to match.
    return (LATIN_KEYTERMS if mode == "transliterate" else DOMAIN_KEYTERMS), DOMAIN_TOPIC


async def transcribe_upload(data: bytes, filename: str, lang: str | None = None, mode: str = "transcribe",
                            client: GnaniClient | None = None, use_context: bool | None = None,
                            model: str = "prisma-v3.0") -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    langs = parse_langs(lang)
    client = client or get_client()
    chunks, total = await run_in_threadpool(audio.prepare_for_stt, data, filename)
    keyterms, topic = context_for(mode, use_context)
    out_chunks, prev, detected, model_seen = [], "", [], model
    for c in chunks:
        r = await client.stt(c["audio"], c["filename"], language_code=langs, fmt=mode, keyterms=keyterms,
                             topic=topic, previous_text=prev or None, model=model)
        text = (r.get("transcript") or "").strip()
        model_seen = r.get("model", model_seen)
        if r.get("detected_language_code"):
            detected.append(r["detected_language_code"])
        out_chunks.append({"start_s": c["start_s"], "end_s": c["end_s"], "transcript": text})
        if text:
            prev = (prev + " " + text).strip()[-600:]
    det = Counter(detected).most_common(1)[0][0] if detected else None
    return {
        "transcript": " ".join(c["transcript"] for c in out_chunks if c["transcript"]),
        "detected_language_code": det,
        "language_code": langs,
        "mode": mode,
        "chunks": out_chunks,
        "duration_s": round(float(total or 0.0), 3),
        "model": model_seen,
    }
