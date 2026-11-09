"""Baaki tables (SQLModel). Owned by the case engine; other modules import from here.

Keep table and field names stable: the messages / employer / voice-profile modules read them.
Money is stored in whole rupees as float (part-time estimates can have paise). JSON blobs are stored
as TEXT (`*_json`) so SQLite and Postgres behave the same.

Languages: "te-IN" (Telugu), "hi-en" (Hinglish), "hi-IN" (Hindi), "en-IN" (English).
"""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


def new_token() -> str:
    """Unguessable employer-page token (used in /e/{token})."""
    return secrets.token_urlsafe(12)


class Worker(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    language: str = "te-IN"            # the worker's own language for read-back and alerts
    phone: Optional[str] = None
    city: str = "Hyderabad"
    category: str = "unskilled"        # unskilled | semi_skilled | skilled | highly_skilled
    work_type: str = "housekeeping"    # housekeeping | cooking | childcare | eldercare | other
    upi_vpa: Optional[str] = None      # where the employer pays (UPI deep link `pa`)
    created_at: str = Field(default_factory=now_iso)


class Employer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    language: str = "hi-en"            # language the employer is written to / spoken to in
    phone: Optional[str] = None
    locality: Optional[str] = None
    fair_employer: bool = False        # Fair Employer badge (turned on when paid in full / Kaam Patta)
    kaam_patta_signed: bool = False    # signed the work agreement
    created_at: str = Field(default_factory=now_iso)


class Case(SQLModel, table=True):
    """One worker's claim against one employer."""
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    employer_id: int = Field(foreign_key="employer.id", index=True)
    status: str = "draft"              # draft | confirmed | sent | plan | paid | closed
    work_type: str = "housekeeping"
    category: str = "unskilled"
    monthly_wage: float = 0            # agreed wage per month (₹)
    hours_per_day: float = 8
    days_per_week: float = 6
    start_date: Optional[str] = None   # ISO date
    end_date: Optional[str] = None     # ISO date of dismissal / leaving, if any
    dismissed: bool = False
    months_unpaid: float = 0
    transcript: str = ""               # the worker's own words (as transcribed)
    transcript_lang: str = "te-IN"
    facts_json: str = "{}"             # extracted facts as confirmed by the worker
    calc_json: str = "{}"              # app.wages output snapshot (dues, shortfall, due dates, sources)
    total_due: float = 0               # contractual baaki: unpaid wages + illegal cuts (₹)
    shortfall_estimate: float = 0      # Haq Check: minimum-wage shortfall (always an estimate)
    amount_paid: float = 0             # paid back through Baaki so far
    employer_token: str = Field(default_factory=new_token, index=True, unique=True)
    readback_confirmed: bool = False
    confirmed_at: Optional[str] = None
    safety_json: str = "{}"            # app.safety result at intake
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    # helpers (not columns)
    def facts(self) -> dict[str, Any]:
        return json.loads(self.facts_json or "{}")

    def calc(self) -> dict[str, Any]:
        return json.loads(self.calc_json or "{}")

    @property
    def balance(self) -> float:
        return max(0.0, round(self.total_due - self.amount_paid, 2))


class CaseItem(SQLModel, table=True):
    """One line of the itemised baaki."""
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    kind: str                          # unpaid_wage | illegal_deduction | final_settlement | min_wage_shortfall
    label: str                         # e.g. "Unpaid wages: Aug 2026"
    month: Optional[str] = None        # "2026-08"
    amount: float = 0
    is_estimate: bool = False          # True for every minimum-wage figure
    included_in_total: bool = True     # shortfall lines are shown but not added to the contractual total
    due_date: Optional[str] = None     # section 17 due date (ISO)
    source: str = ""                   # citation string
    created_at: str = Field(default_factory=now_iso)


class Message(SQLModel, table=True):
    """A Polite / Firm / Formal step sent to the employer, or a system alert to the worker."""
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    step: str = "polite"               # polite | firm | formal | reply | paid_alert | reminder
    direction: str = "to_employer"     # to_employer | to_worker | from_employer
    language: str = "hi-en"
    text: str = ""
    text_worker_lang: Optional[str] = None   # translation shown to the worker
    audio_path: Optional[str] = None
    pdf_path: Optional[str] = None
    voice_note_id: Optional[str] = None      # uuid written into the OGG metadata
    status: str = "draft"              # draft | sent | played | replied
    created_at: str = Field(default_factory=now_iso)
    sent_at: Optional[str] = None


class Payment(SQLModel, table=True):
    """A payment (or a planned instalment) from the employer."""
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="case.id", index=True)
    amount: float
    method: str = "upi"                # upi | cash | bank | other
    status: str = "paid"               # paid | planned
    due_date: Optional[str] = None     # for planned instalments
    instalment_no: Optional[int] = None
    instalments_total: Optional[int] = None
    note: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class DiaryEntry(SQLModel, table=True):
    """Voice check-in ("worked today"), hash-chained: hash = sha256(prev_hash | canonical fields)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    employer_id: Optional[int] = Field(default=None, foreign_key="employer.id", index=True)
    case_id: Optional[int] = Field(default=None, foreign_key="case.id", index=True)
    timestamp: str = Field(default_factory=now_iso)
    kind: str = "checkin"              # checkin | absence | payment | note
    text: str = ""
    audio_sha256: Optional[str] = None
    prev_hash: str = ""
    hash: str = ""


class VoiceProfile(SQLModel, table=True):
    """Opt-in voice embedding (never the audio). One active profile per worker."""
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    consent: bool = False
    consent_at: Optional[str] = None
    embedding_json: str = "[]"
    model: Optional[str] = None
    duration_s: Optional[float] = None
    created_at: str = Field(default_factory=now_iso)


ALL_TABLES = (Worker, Employer, Case, CaseItem, Message, Payment, DiaryEntry, VoiceProfile)
