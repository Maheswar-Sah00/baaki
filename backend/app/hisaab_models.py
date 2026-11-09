"""V09 Hisaab Milao: the employer's proposed corrections (a new table; no column is added to any existing table).

HisaabProposal  one correction the employer proposed ("Maine October mein do hazaar cash diye the").
                status: proposed (waiting for her) | accepted (she agreed: a normal Payment row was created) |
                rejected (she disagrees: shown as "disputed", no money change). Never auto-accepted.

`case_token` snapshots Case.employer_token: POST /api/demo/reset wipes and re-creates the cases (SQLite may reuse
ids), so a proposal whose snapshot no longer matches its case is stale and is ignored.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


class HisaabProposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True)
    case_token: str = ""                     # Case.employer_token when created (staleness check)
    worker_id: int = Field(index=True)
    employer_id: int = Field(index=True)
    said_by: str = "employer"                # always the employer: Baaki verifies nothing (s.59)
    amount: float                            # rupees, from app.lang (spoken) or the employer's typed number
    amount_source: str = "spoken"            # spoken | typed
    kind: str = "other"                      # cash | upi | advance | other | said_paid (F2: "I've paid" claim)
    month: Optional[str] = None              # "2026-10" when he named a month
    transcript: str = ""                     # his words (Prisma transcript or typed text)
    source: str = "text"                     # voice | text
    language: str = "hi-en"                  # the employer's language
    stt_json: str = "{}"                     # Prisma settings used (lang codes, mode, duration)
    employer_audio_key: Optional[str] = None # his original clip in storage (kept as the record)
    worker_text: str = ""                    # read-back shown to her, in her language
    worker_speech: str = ""                  # the same with Timbre tags (<slow> on the amount), amount as words
    worker_lang: str = "te-IN"
    readback_tts_key: Optional[str] = None   # tts_cache key of the read-back audio
    status: str = "proposed"                 # proposed | accepted | rejected
    payment_id: Optional[int] = None         # the Payment row created on accept
    balance_before: Optional[float] = None   # balance when she decided
    balance_after: Optional[float] = None
    decided_at: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class HisaabClaim(SQLModel, table=True):
    """F2 trust fix: the employer's "I've paid" is a claim, stored as a HisaabProposal with kind "said_paid"
    plus this row (how he says he paid). Only her confirmation (decide accept) records money; a reject leaves the
    claim "disputed" and changes nothing. Its own table: no column is added to hisaab_proposal."""
    __tablename__ = "hisaab_claim"

    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: int = Field(index=True, unique=True)
    case_id: int = Field(index=True)
    case_token: str = ""
    method: str = "upi"                      # upi | cash | bank | other
    note: Optional[str] = None
    source: str = "employer_page"            # employer_page | sandbox
    alert_audio: bool = True                 # make the "Paisa aa gaya" Timbre clip when she confirms
    demo: bool = False                       # sandbox: confirmed automatically, labelled "Demo: Lakshmi confirmed"
    alert_message_id: Optional[int] = None   # the paid_alert Message written on confirmation
    created_at: str = Field(default_factory=now_iso)
