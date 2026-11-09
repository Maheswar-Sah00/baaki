"""Deterministic language layer (reused from Deposit Wapas).

Money and dates are extracted by fixed rules, never by the LLM, then read back
to the user for a tap-to-confirm. See numbers.py, amounts.py and dates.py.
"""
from .amounts import extract_amounts
from .dates import extract_dates, today_ist
from .numbers import (
    MAX_INR,
    en_words_to_number,
    format_inr,
    hi_words_to_number,
    hinglish_words_to_number,
    inr_to_words,
    number_to_words,
    te_roman_words_to_number,
    te_words_to_number,
    words_to_number,
)

__all__ = [
    "MAX_INR",
    "extract_amounts",
    "extract_dates",
    "today_ist",
    "format_inr",
    "inr_to_words",
    "number_to_words",
    "words_to_number",
    "te_words_to_number",
    "te_roman_words_to_number",
    "hi_words_to_number",
    "hinglish_words_to_number",
    "en_words_to_number",
]
