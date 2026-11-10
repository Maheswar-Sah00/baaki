"""Haq Raise: tables (new tables only; owned by routes/raise_.py).

RaiseAsk    one raise request for one home (Case). It has its own employer token (/raise/e/{token}), separate
            from the case's /e/{token} link, so the dues page and the raise page never mix.
            status: draft (composed, not shared) | sent (she shared it) | played | accepted | stepped | talk
RaiseEvent  the timeline: composed, sent, played, accepted, stepped, talk (employer voice reply + translation),
            celebration (the alert spoken to the worker). Never edited.

`case_token` snapshots Case.employer_token: POST /api/demo/reset wipes and re-creates the cases (SQLite may reuse
ids), so a raise whose snapshot no longer matches its case is stale and is ignored.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso
from .models import new_token


class RaiseAsk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True)
    worker_id: int = Field(index=True)
    employer_id: int = Field(index=True)
    case_token: str = ""                       # Case.employer_token when created (staleness check)
    token: str = Field(default_factory=new_token, index=True, unique=True)   # employer raise link
    status: str = "draft"                      # draft | sent | played | accepted | stepped | talk
    # the numbers (from check_core.compute, never typed by an LLM)
    current_wage: float = 0
    legal_estimate: float = 0
    is_estimate: bool = True
    work_type: str = "maid"                    # check_core work type
    hours_per_day: float = 2
    days_per_week: float = 6
    working_days: float = 26
    # the plan she picked
    plan: str = "step"                         # full | step
    ask_amount: float = 0                      # the target wage
    step1_amount: Optional[float] = None       # step plan: the first wage
    step_months: int = 6                       # step plan: months until the target
    start_month: str = ""                      # "2026-12"
    step_month: Optional[str] = None           # "2027-06"
    mention_law: bool = False                  # off by default (reads as a threat)
    years_worked: Optional[float] = None
    personal_text: str = ""                    # her own words (worker language), optional
    personal_lang: str = ""
    # the message (employer language)
    message_lang: str = "hi-en"
    message_text: str = ""                     # display text, disclosure first
    message_json: str = "{}"                   # sentences, speech, checks, source
    audio_key: Optional[str] = None
    voice_note_id: Optional[str] = None
    # the answer
    choice: Optional[str] = None               # asked | step
    new_wage: Optional[float] = None           # wage from new_wage_from
    new_wage_from: Optional[str] = None        # ISO date (1st of the month)
    step_up_to: Optional[float] = None
    step_up_from: Optional[str] = None         # ISO date
    answered_at: Optional[str] = None
    agreement_key: Optional[str] = None        # PDF
    demo: bool = False
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class RaiseEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    raise_id: int = Field(index=True)
    kind: str = "composed"                     # composed | sent | played | accepted | stepped | talk | celebration
    direction: str = "system"                  # to_employer | from_employer | to_worker | system
    language: str = ""
    text: str = ""
    text_worker_lang: Optional[str] = None
    audio_key: Optional[str] = None
    original_audio_key: Optional[str] = None
    data_json: str = "{}"
    created_at: str = Field(default_factory=now_iso)


RAISE_TABLES = (RaiseAsk, RaiseEvent)
