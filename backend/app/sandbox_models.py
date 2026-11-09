"""V04 Be Sharma ji: one row per public employer sandbox (its own table; no columns added elsewhere).

Each sandbox owns a synthetic Worker ("Lakshmi"), Employer ("Sharma ji"), Case and its items, copied from
the seeded story. `case_token` is the copied case's employer token: it is used only to check that the case
row still belongs to this sandbox (ids are recycled after /api/demo/reset) and is never sent to a browser.
No foreign keys on purpose: a demo reset wipes the core tables, and this table must not block that.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


class SandboxSession(SQLModel, table=True):
    __tablename__ = "sandbox_session"

    id: str = Field(primary_key=True)          # public sandbox id (unguessable, ~16 chars)
    case_id: int = Field(index=True)
    case_token: str                            # never exposed
    worker_id: int
    employer_id: int
    ip_hash: str = ""                          # sha256 prefix, never the raw IP
    created_ts: float = Field(index=True)
    expires_ts: float = Field(index=True)
    created_at: str = Field(default_factory=now_iso)
    played_at: Optional[str] = None
    paid_at: Optional[str] = None
