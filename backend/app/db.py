"""Database engine and sessions: SQLite (backend/data/app.db, gitignored, or DATABASE_URL=sqlite:///...).

Only SQLite is supported and tested (no Postgres driver is installed).

* Table registry: every module that defines a table is listed in MODEL_MODULES (OPTIONAL_MODEL_MODULES for
  modules other streams may add). `register_models()` imports them all, so `SQLModel.metadata` knows every
  table before create_all (init_db) and before a demo reset (`all_tables()`, children last-to-first).
* SQLite runs with NullPool (a connection per session, no 5+10 pool to exhaust while a request awaits Gnani),
  WAL journal and busy_timeout, so concurrent requests queue on the file lock instead of failing.
* Long awaits (STT, translation, TTS) must not hold a session: read what you need in one short session,
  close it, do the slow work, then write in another short session (`db.run(fn)` / `db.session()`).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import logging
import weakref
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from sqlalchemy import Engine, Table, event, text
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import Session, SQLModel, create_engine

from . import config

DB_PATH = config.DATA_DIR / "app.db"

_engine: Engine | None = None
_initialised: "weakref.WeakSet[Engine]" = weakref.WeakSet()
log = logging.getLogger("db")
T = TypeVar("T")

# Every module that defines a SQLModel table (table=True). Add new table modules here.
MODEL_MODULES = ("models", "dues_models", "exit_kit", "hisaab_models", "inbox_models", "raise_models",
                 "sandbox_models")
# Modules other fix streams may add with their own tables (snapshots, worker keys, budget, onboarding):
# imported when present, skipped when not.
OPTIONAL_MODEL_MODULES = ("ledger", "ledger_models", "security", "security_models", "consent_flow", "voice_profile",
                          "budget", "routes.onboard")
SQLITE_BUSY_TIMEOUT_MS = 5000


def register_models() -> None:
    """Import every table module so SQLModel.metadata holds every table."""
    for name in MODEL_MODULES:
        importlib.import_module(f"{__package__}.{name}")
    for name in OPTIONAL_MODEL_MODULES:
        try:
            importlib.import_module(f"{__package__}.{name}")
        except ModuleNotFoundError as e:
            if e.name and not e.name.endswith(name.split(".")[-1]):
                raise  # the module exists but one of its imports is missing: a real error


def all_tables() -> list[Table]:
    """Every registered table, parents first (reverse it to delete children first)."""
    register_models()
    return list(SQLModel.metadata.sorted_tables)


def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    """Per connection: wait on the file lock instead of failing. (WAL is a property of the file, set once.)"""
    cur = dbapi_conn.cursor()
    try:
        cur.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cur.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; one fsync per checkpoint, not per commit
    finally:
        cur.close()


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        memory = url in ("sqlite://", "sqlite:///:memory:") or "mode=memory" in url
        if memory:  # one shared connection, or every session would see an empty database
            return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000},
                            poolclass=NullPool)
        event.listen(eng, "connect", _sqlite_pragmas)
        with eng.connect() as c:  # persistent: readers never block the writer, the writer never blocks readers
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
        return eng
    if url.startswith("postgres://"):  # Supabase/Heroku style
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True)  # untested: needs a driver (none installed)


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
    register_models()
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


def run(fn: Callable[[Session], T], commit: bool = True) -> T:
    """One short unit of work: open a session, run fn(s), commit (unless commit=False), close.

    Use it around the slow part of a request instead of holding a session across `await`:
        ctx = db.run(lambda s: load_what_i_need(s), commit=False)   # read, session closed
        result = await slow_gnani_call(ctx)                          # no connection held
        return db.run(lambda s: write_result(s, result))             # short write
    Return plain values (or model objects; sessions use expire_on_commit=False, so loaded fields stay readable).
    """
    with session() as s:
        out = fn(s)
        if commit:
            s.commit()
        return out


def wipe_all(s: Session) -> list[str]:
    """Delete every row of every registered table (children first) and reset SQLite id counters, so a new
    case 1 never inherits an old case 1's replies, promises or exit kits. Returns the tables wiped.
    The caller commits."""
    from sqlalchemy import inspect

    tables = all_tables()
    conn = s.connection()
    existing = set(inspect(conn).get_table_names())
    wiped = []
    for t in reversed(tables):  # children first (SQLite FKs are off, but keep the order honest)
        if t.name in existing:
            s.execute(t.delete())
            wiped.append(t.name)
    if conn.dialect.name == "sqlite" and conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")).first():
        s.execute(text("DELETE FROM sqlite_sequence"))  # AUTOINCREMENT tables (none today; future-proof)
    return wiped


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    """UTC timestamp string, stored verbatim."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
