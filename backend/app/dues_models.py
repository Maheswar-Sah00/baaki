"""Baaki for every promise: tables (new tables only; owned by routes/dues.py).

DuesAccount  one person who owes the user money. kind: vendor (the user sells milk / papers / ironing and a
             customer owes the bill) | chit (chit payout, savings or a hand loan promised back) | other.
DuesItem     one line of what is owed ("October milk ₹1,850") or a payment received (kind="paid").
DuesPromise  one "next week / end of this week / 1st tareekh" the other party said, with the due date resolved
             relative to the day it was said (app.lang.dates). Stored status pending | kept | broken; a pending
             promise whose date has passed with money still owed reads as broken (derived, see dues_core).
DuesLog      the hash chain: every item, payment, promise and status change is appended here, per account.
             hash = sha256(prev_hash | canonical JSON of the entry). Never edited; corrections are new entries.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from .db import now_iso


class DuesAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = "vendor"                      # vendor | chit | other
    title: str = ""                           # "Milk bill", "Chit money"
    party_name: str = ""                      # the person who owes (customer, chit agent, friend)
    party_lang: str = "hi-en"                 # hi-en | te-IN | en: reminders go out in this language
    party_phone: Optional[str] = None         # optional, for a wa.me link straight to them
    owner_name: str = ""                      # the user (the milkman, the chit member)
    owner_lang: str = "hi-en"
    owner_vpa: Optional[str] = None           # the user's UPI id (vendor kind: the reminder carries a UPI link)
    note: str = ""
    demo: bool = False                        # created by POST /api/dues/demo (synthetic)
    created_at: str = Field(default_factory=now_iso)


class DuesItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="duesaccount.id", index=True)
    kind: str = "due"                         # due | paid
    label: str = ""                           # the user's own words, cleaned ("October doodh")
    item_key: Optional[str] = None            # milk | paper | ironing | vegetables | water | chit | loan | savings
    month: Optional[int] = None               # 1-12 when a month was named
    amount: float = 0.0                       # always positive; kind says the sign
    source_text: str = ""                     # the words the amount came from
    said_on: str = ""                         # ISO date
    log_id: Optional[int] = Field(default=None, foreign_key="dueslog.id")
    created_at: str = Field(default_factory=now_iso)


class DuesPromise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="duesaccount.id", index=True)
    said_on: str = ""                         # ISO date the promise was made (relative dates resolve from here)
    due_date: str = ""                        # ISO; for a window ("this week") the window's last day
    range_start: Optional[str] = None
    precision: str = "day"                    # day | week | month
    phrase: str = ""                          # the date words as said ("ఈ వారం", "first week")
    quote: str = ""                           # their own words, quoted back politely in the reminder
    lang: str = "hi-en"                       # language of the quote
    amount: Optional[float] = None            # an amount named in the promise (app.lang), if any
    source: str = "text"                      # text | audio
    status: str = "pending"                   # pending | kept | broken (stored); broken is also derived
    status_at: Optional[str] = None
    log_id: Optional[int] = Field(default=None, foreign_key="dueslog.id")
    created_at: str = Field(default_factory=now_iso)


class DuesLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="duesaccount.id", index=True)
    kind: str = "item"                        # account | item | paid | promise | status
    said_on: str = ""
    text: str = ""
    data_json: str = "{}"
    timestamp: str = Field(default_factory=now_iso)
    prev_hash: str = ""
    hash: str = Field(default="", index=True)


DUES_TABLES = (DuesAccount, DuesItem, DuesPromise, DuesLog)
