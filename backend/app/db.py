"""Database engine and sessions: SQLite (backend/data/app.db, gitignored) or DATABASE_URL (Postgres).

Table models live in app/models.py; init_db() imports them so SQLModel registers every table
before create_all.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import weakref
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import config

DB_PATH = config.DATA_DIR / "app.db"

_engine: Engine | None = None
_initialised: "weakref.WeakSet[Engine]" = weakref.WeakSet()


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    if url.startswith("postgres://"):  # Supabase/Heroku style
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True)  # needs a driver, e.g. psycopg (not installed yet)


def get_engine(url: str | None = None) -> Engine:
    """Explicit url (tests) > DATABASE_URL (Postgres in production) > local SQLite."""
    global _engine
    if url is not None:
        return _make_engine(url)
    if _engine is None:
        env_url = config.database_url()
        if env_url:
            _engine = _make_engine(env_url)
        else:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            _engine = _make_engine(f"sqlite:///{DB_PATH.as_posix()}")
    return _engine


def init_db(engine: Engine | None = None) -> Engine:
    eng = engine or get_engine()
    from . import models  # noqa: F401  (registers every table)
    SQLModel.metadata.create_all(eng)
    _initialised.add(eng)
    return eng


def set_engine(engine: Engine | None) -> None:
    """Swap the process engine (tests use a fresh in-memory database per test)."""
    global _engine
    _engine = engine


def session() -> Session:
    """A session on the process engine; tables are created on first use."""
    eng = get_engine()
    if eng not in _initialised:
        init_db(eng)
    return Session(eng, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: `s: Session = Depends(db.get_session)`."""
    with session() as s:
        yield s


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    """UTC timestamp string, stored verbatim."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
