"""Ledger tables (fix stream F2). New tables only: no column is added to any existing table.

LedgerEntry      one row per money write made through app.ledger.record_payment (who/what wrote it, how much was
                 asked vs recorded, and whether it counts towards a pay-in-parts plan).
LedgerPlan       a pay-in-parts plan: its baseline (the highest Payment id on the case when the plan was made, so
                 only money paid AFTER the plan settles instalments) and the links instalment -> Payment row ->
                 reminder Message row.
FairBadgeGrant   which case turned an employer's Fair Employer badge on, so the ledger only takes back a badge
                 that this case gave.
MessageSnapshot  the balance and total a voice note / letter was made with (stale-amount check, GAP #9).

Every row carries `case_token` (Case.employer_token when written): a demo reset re-creates cases and SQLite may
reuse ids, so a row whose token no longer matches its case is ignored.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


class LedgerEntry(SQLModel, table=True):
    __tablename__ = "ledger_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True)
    case_token: str = ""
    payment_id: int = Field(index=True)
    amount: float                           # what was recorded (capped at the balance)
    requested: float                        # what was said / confirmed; > amount means money beyond the balance
    method: str = "other"
    source: str = "other"                   # employer_claim | hisaab_correction | sandbox_demo | ...
    plan_credit: bool = True                # False: a correction about money given before (re-splits, never settles)
    proposal_id: Optional[int] = None
    recorded_at: str = Field(default_factory=now_iso)


class LedgerPlan(SQLModel, table=True):
    __tablename__ = "ledger_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True)
    case_token: str = ""
    baseline_payment_id: int = 0            # Payment rows with id <= this were paid before the plan
    balance_at_plan: float = 0
    instalments_total: int = 0
    every_days: int = 30
    status: str = "active"                  # active | done | replaced
    links_json: str = "[]"                  # [{"no": 1, "payment_id": 7, "reminder_id": 12}, ...]
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class FairBadgeGrant(SQLModel, table=True):
    __tablename__ = "fair_badge_grant"

    id: Optional[int] = Field(default=None, primary_key=True)
    employer_id: int = Field(index=True)
    case_id: int = Field(index=True)
    case_token: str = ""
    active: bool = True
    granted_at: str = Field(default_factory=now_iso)
    revoked_at: Optional[str] = None


class MessageSnapshot(SQLModel, table=True):
    __tablename__ = "message_snapshot"

    message_id: int = Field(primary_key=True)
    case_id: int = Field(index=True)
    case_token: str = ""
    balance_at_make: float
    total_at_make: float
    made_at: str = Field(default_factory=now_iso)


LEDGER_TABLES = (LedgerEntry, LedgerPlan, FairBadgeGrant, MessageSnapshot)
