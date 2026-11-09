"""One clock for Baaki: "today" is the calendar day in Hyderabad (IST, UTC+05:30).

Every route, the seed and the calculators should ask `clock.today()`, never `date.today()` (server-local)
or a UTC day. For filming, `BAAKI_TODAY=2026-11-09` pins the day (ISO date; read on every call, so a test
can monkeypatch the env). `lang.today_ist` is kept as the parser-side name for the same day.
"""
from __future__ import annotations

import datetime as dt
import os

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _override() -> dt.date | None:
    raw = os.environ.get("BAAKI_TODAY", "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None  # a malformed override never breaks the app; the real day is used


def today() -> dt.date:
    """The day in IST (or BAAKI_TODAY when set)."""
    return _override() or dt.datetime.now(IST).date()


def now() -> dt.datetime:
    """Aware IST datetime; with BAAKI_TODAY set, that day at the current IST time of day."""
    real = dt.datetime.now(IST)
    o = _override()
    return real if o is None else dt.datetime.combine(o, real.timetz())


__all__ = ["today", "now", "IST"]
