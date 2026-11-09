"""Share to Baaki + Promise Keeper tables (W04 + G16 + W05). Owned by routes/inbox.py.

InboxCard     one employer reply that the worker forwarded / uploaded / pasted (WhatsApp voice note or text).
              Hash-chained by appending a DiaryEntry(kind="evidence") through routes.cases.add_diary_entry,
              so the card sits in the worker's existing diary chain and the legal-pack annex.
InboxPromise  a promise found in that reply: amount (app.lang, never the LLM) + due date (app.lang.dates).
              Stored status: pending | kept | broken. "passed" is derived (the day after due_date, unpaid).
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


class InboxCard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    employer_id: int = Field(foreign_key="employer.id", index=True)
    source: str = "audio"                    # audio | text
    language_code: str = "hi-en"             # hi-en | te-IN | en (the employer's words)
    stt_language_code: Optional[str] = None  # what Prisma was asked for (e.g. hi-IN,en-IN)
    detected_language_code: Optional[str] = None
    stt_mode: Optional[str] = None
    transcript: str = ""
    translation: str = ""
    translation_lang: str = "te-IN"
    translation_source: str = "template"     # llm | template | same_language
    amounts_json: str = "[]"                 # amounts heard (app.lang)
    said_on: str = ""                        # ISO date the employer said it (relative dates resolve from here)
    original_audio_path: Optional[str] = None
    audio_path: Optional[str] = None         # Timbre read-out in the worker's language
    content_sha256: str = Field(default="", index=True)   # sha256 of the audio bytes (or the text)
    diary_entry_id: Optional[int] = Field(default=None, foreign_key="diaryentry.id")
    prev_hash: str = ""
    hash: str = ""
    created_at: str = Field(default_factory=now_iso)


class InboxPromise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="inboxcard.id", index=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    amount: Optional[float] = None           # None = no amount said (or "the rest")
    is_rest: bool = False                    # "baaki agle mahine": the rest of the dues
    due_date: str = ""                       # ISO; for a window ("agle hafte") the window's last day
    range_start: Optional[str] = None
    precision: str = "day"                   # day | week | month
    phrase: str = ""                         # the date words as said ("agle hafte")
    quote: str = ""                          # the employer's own clause, quoted in the reminder
    confidence: float = 0.5
    confirmed: bool = False                  # the worker heard the read-back and tapped "yes"
    edited: bool = False                     # she corrected the date or the amount
    status: str = "pending"                  # pending | kept | broken (stored); passed is derived
    status_at: Optional[str] = None
    reminded_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


INBOX_TABLES = (InboxCard, InboxPromise)
