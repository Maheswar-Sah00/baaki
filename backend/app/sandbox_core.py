"""V04 Be Sharma ji: public employer sandbox. Zero Gnani calls, ever.

A viewer becomes "Sharma ji" in a fresh synthetic copy of the seeded story: hears Lakshmi's polite voice
note, sees the itemised baaki (Rs 12,692 in the seeded story), taps "Mark as paid", and Lakshmi's panel
shows "Paisa aa gaya!" with its cached clip.

How the copy is made (no Gnani, no LLM):
* The seeded Sharma ji case is rebuilt once per process by running `seed.seed()` on a throwaway in-memory
  database, so the copy always matches the real seed. Each sandbox gets its own Worker, Employer, Case and
  CaseItems (new rows); the real demo rows are never read or written.
* The polite note's text comes from the deterministic template (`messages.compose(use_llm=False)`). Its
  audio is assembled only from sentences already in the TTS cache (seed_cache/tts or data/tts_cache), in
  order, starting with the AI disclosure. A sentence that is not cached (the reply-by date changes daily)
  is left out of the audio and stays in the text. No disclosure clip = "voice note unavailable".
* "Mark as paid" goes through the real flow: the employer's tap is a claim (routes/employer.pay, alert audio off),
  then a synthetic confirmation labelled "Demo: Lakshmi confirmed" accepts it through the same ledger code
  (routes/hisaab.decide_proposal, demo=True). The "Paisa aa gaya" clip is attached only if the exact alert
  sentence is already cached.
* No database session is held across an await: rows are written in one short transaction, the note text and
  its cached audio are prepared with the session closed, then the message is written in a second short one.

Guards: per-IP creation limit (in memory), 1 hour expiry, a cap of MAX_SANDBOXES (oldest evicted),
cleanup of expired rows, no UPI, no live voice reply, no employer token in any response, no voice clone.
"""
from __future__ import annotations

import collections
import datetime as dt
import functools
import hashlib
import json
import logging
import secrets
import threading
import time
from typing import Any

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, delete, func, select
from starlette.concurrency import run_in_threadpool

from . import config, db, ledger, messages, seed, storage, tts_cache, voice_note
from .hisaab_models import HisaabClaim, HisaabProposal
from .ledger_models import FairBadgeGrant, LedgerEntry, LedgerPlan, MessageSnapshot
from .models import Case, CaseItem, DiaryEntry, Employer, Message, Payment, Worker
from .sandbox_models import SandboxSession

log = logging.getLogger("sandbox")

BANNER = "Synthetic demo. Lakshmi is fictional."
UPI_OFF = "Demo: UPI is switched off"
REPLY_OFF = "Voice reply is switched off in the public demo."
PAID_HEADLINE = "Paisa aa gaya!"
PAID_HEADLINE_EN = "The money has arrived."
NO_MONEY_NOTE = "Sandbox demo: no real money moved"
DEMO_CONFIRMED_LABEL = "Demo: Lakshmi confirmed (synthetic)"

TTL_S = 3600                 # a sandbox lives one hour
MAX_SANDBOXES = 300          # total cap; the oldest is evicted to make room
RATE_MAX = 6                 # creations per IP ...
RATE_WINDOW_S = 600          # ... per 10 minutes
# No proxy header and a loopback peer means every visitor shares one bucket (the Next /api rewrite adds no
# X-Forwarded-For of its own), so that bucket gets a larger allowance; MAX_SANDBOXES still bounds the rows.
RATE_MAX_SHARED = 60
SHARED_IPS = {"127.0.0.1", "::1", "localhost", "unknown"}

_hits: dict[str, collections.deque] = {}
_hits_lock = threading.Lock()
_note_cache: dict[str, dict[str, Any]] = {}   # clip-set hash -> {"key", "duration_s"}


class SandboxError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.retry_after is not None:
            out["retry_after_s"] = self.retry_after
        return out


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ip_hash(ip: str) -> str:
    return hashlib.sha256(f"baaki-sandbox|{ip}".encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- rate limit
def check_rate(iph: str, limit: int | None = None) -> None:
    """Raise 429 if this IP created `limit` (RATE_MAX) sandboxes in the last RATE_WINDOW_S s; else count one."""
    limit = RATE_MAX if limit is None else limit
    now = _now()
    with _hits_lock:
        q = _hits.setdefault(iph, collections.deque())
        while q and q[0] <= now - RATE_WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            raise SandboxError(429, "rate_limited", "Too many demos from this network. Try again in a few minutes.",
                               retry_after=max(1, int(q[0] + RATE_WINDOW_S - now) + 1))
        q.append(now)
        if len(_hits) > 5000:  # keep the dict small
            for k in [k for k, v in _hits.items() if not v or v[-1] <= now - RATE_WINDOW_S]:
                _hits.pop(k, None)


def reset_limits() -> None:
    with _hits_lock:
        _hits.clear()


# --------------------------------------------------------------------------- template (the seeded case)
@functools.lru_cache(maxsize=1)
def template() -> dict[str, Any]:
    """The seeded Sharma ji case, built by the real seed on a throwaway in-memory database."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    try:
        SQLModel.metadata.create_all(eng)
        with Session(eng, expire_on_commit=False) as s:
            ids = seed.seed(s)
            c = s.get(Case, ids["cases"]["sharma"])
            w = s.get(Worker, c.worker_id)
            e = s.get(Employer, c.employer_id)
            items = list(s.exec(select(CaseItem).where(CaseItem.case_id == c.id).order_by(CaseItem.id)))
            skip_case = {"id", "worker_id", "employer_id", "employer_token", "created_at", "updated_at",
                         "confirmed_at", "amount_paid", "status"}
            return {
                "worker": {k: getattr(w, k) for k in ("name", "language", "city", "category", "work_type")},
                "employer": {k: getattr(e, k) for k in ("name", "language", "locality")},
                "case": {k: v for k, v in c.model_dump().items() if k not in skip_case},
                "items": [{k: v for k, v in i.model_dump().items() if k not in ("id", "case_id", "created_at")}
                          for i in items],
            }
    finally:
        eng.dispose()


# --------------------------------------------------------------------------- cached audio only
def _manifest_voices(lang: str) -> list[str]:
    try:
        m = json.loads((config.SEED_CACHE_DIR / "demo_manifest.json").read_text(encoding="utf-8"))
        return [c["voice"] for c in m.get("clips", []) if c.get("lang") == lang and c.get("voice")]
    except Exception:
        return []


def cached_clip(text: str, lang: str):
    """Path of an already-cached Timbre clip for exactly this sentence, or None. Never synthesises."""
    voices = [tts_cache.default_voice(lang), *_manifest_voices(lang)]
    for v in dict.fromkeys(voices):
        p = tts_cache.lookup(tts_cache.cache_key(text.strip(), lang, v))
        if p is not None:
            return p
    return None


def _stored(key: str) -> bool:
    st = storage.get_storage()
    try:
        p = st.local_path(key)
        if p is not None:
            return True
        st.get(key)
        return True
    except Exception:
        return False


async def polite_note_audio(speech: list[str], lang: str) -> dict[str, Any]:
    """Assemble the voice note from cached sentences only. Returns
    {"available", "key", "duration_s", "spoken", "skipped", "reason"}."""
    found = [(i, s, cached_clip(s, lang)) for i, s in enumerate(speech)]
    spoken = [(i, s, p) for i, s, p in found if p is not None]
    skipped = [s for _, s, p in found if p is None]
    base = {"spoken": [s for _, s, _ in spoken], "skipped": skipped}
    if not found or found[0][2] is None:
        return {**base, "available": False, "key": None, "duration_s": None,
                "reason": "No cached audio for the AI disclosure on this server, so the voice note is unavailable. "
                          "The text is below."}
    if len(spoken) < 2:
        return {**base, "available": False, "key": None, "duration_s": None,
                "reason": "No cached audio for this note on this server. The text is below."}
    h = hashlib.sha256("|".join(p.stem for _, _, p in spoken).encode()).hexdigest()[:20]
    hit = _note_cache.get(h)
    if hit and _stored(hit["key"]):
        return {**base, "available": True, "key": hit["key"], "duration_s": hit["duration_s"], "reason": None}
    clips = [(await run_in_threadpool(p.read_bytes), p.suffix.lstrip(".")) for _, _, p in spoken]
    note_id = f"sandbox-{h}"
    tags = {"COMMENT": voice_note.ai_comment(note_id, "Lakshmi (fictional)", "stock", "sandbox demo voice note"),
            "ID": note_id, "TITLE": "Baaki sandbox demo voice note", "ARTIST": "Baaki app (AI voice)"}
    try:
        data, dur = await run_in_threadpool(voice_note.assemble, clips, tags)
    except Exception as ex:  # ffmpeg missing or a bad file: degrade, never call Gnani
        log.warning("sandbox note assembly failed: %s", str(ex)[:120])
        return {**base, "available": False, "key": None, "duration_s": None,
                "reason": "The cached voice note could not be prepared on this server. The text is below."}
    key = storage.get_storage().put(f"sandbox/polite_{h}.ogg", data)
    _note_cache[h] = {"key": key, "duration_s": round(dur, 3)}
    return {**base, "available": True, "key": key, "duration_s": round(dur, 3), "reason": None}


def paid_clip_key(speech: str, lang: str) -> str | None:
    """Storage key of the cached "Paisa aa gaya" clip for exactly this alert sentence, or None."""
    p = cached_clip(speech, lang)
    if p is None:
        return None
    key = f"sandbox/paid_{p.stem[:24]}.{p.suffix.lstrip('.')}"
    if not _stored(key):
        storage.get_storage().put(key, p.read_bytes())
    return key


def read_audio(key: str) -> bytes:
    return storage.get_storage().get(key)


# --------------------------------------------------------------------------- lifecycle
def _delete_case_rows(s: Session, row: SandboxSession) -> None:
    """Delete the sandbox's own rows, but only if the case still carries this sandbox's token
    (after a demo reset the ids may belong to someone else: then only the sandbox row goes)."""
    case = s.get(Case, row.case_id)
    if case is not None and case.employer_token == row.case_token:
        for t in (Message, Payment, CaseItem, DiaryEntry, HisaabClaim, HisaabProposal, LedgerEntry, LedgerPlan,
                  FairBadgeGrant, MessageSnapshot):
            s.exec(delete(t).where(t.case_id == case.id))  # type: ignore[call-overload]
        worker_id, employer_id = case.worker_id, case.employer_id
        s.delete(case)
        s.flush()
        others = s.exec(select(func.count()).select_from(Case).where(Case.worker_id == worker_id)).one()
        if not others and worker_id == row.worker_id:
            w = s.get(Worker, worker_id)
            if w is not None:
                s.delete(w)
        others = s.exec(select(func.count()).select_from(Case).where(Case.employer_id == employer_id)).one()
        if not others and employer_id == row.employer_id:
            e = s.get(Employer, employer_id)
            if e is not None:
                s.delete(e)
    s.delete(row)


def cleanup(s: Session, now: float | None = None) -> int:
    """Remove expired sandboxes and their rows. Returns how many were removed."""
    now = _now() if now is None else now
    rows = list(s.exec(select(SandboxSession).where(SandboxSession.expires_ts <= now)))
    for row in rows:
        _delete_case_rows(s, row)
    if rows:
        s.commit()
    return len(rows)


def _evict_for_room(s: Session) -> int:
    n = s.exec(select(func.count()).select_from(SandboxSession)).one()
    evicted = 0
    if n >= MAX_SANDBOXES:
        for row in s.exec(select(SandboxSession).order_by(SandboxSession.created_ts)
                          .limit(n - MAX_SANDBOXES + 1)):
            _delete_case_rows(s, row)
            evicted += 1
        s.commit()
    return evicted


def active_count(s: Session) -> int:
    return s.exec(select(func.count()).select_from(SandboxSession).where(SandboxSession.expires_ts > _now())).one()


async def create(ip: str) -> SandboxSession:
    iph = ip_hash(ip)
    check_rate(iph, RATE_MAX_SHARED if ip in SHARED_IPS else RATE_MAX)
    tpl = template()
    with db.session() as s:   # 1. short write: the sandbox's own rows
        SandboxSession.metadata.create_all(s.get_bind(), tables=[SandboxSession.__table__])  # type: ignore[attr-defined]
        cleanup(s)
        _evict_for_room(s)
        if s.exec(select(func.count()).select_from(Worker)).one() == 0:
            # Empty database: build the real demo story first, so the sandbox worker never takes
            # the ids the app uses for the real Lakshmi (1) and Rafiq (2).
            seed.seed(s)
        w = Worker(**tpl["worker"], phone=None, upi_vpa=None)
        e = Employer(**tpl["employer"], fair_employer=False, kaam_patta_signed=False)
        s.add(w)
        s.add(e)
        s.flush()
        now_iso = db.now_iso()
        c = Case(**tpl["case"], worker_id=w.id, employer_id=e.id, status="sent", amount_paid=0,
                 confirmed_at=now_iso)
        s.add(c)
        s.flush()
        for it in tpl["items"]:
            s.add(CaseItem(**it, case_id=c.id))
        ts = _now()
        row = SandboxSession(id=secrets.token_urlsafe(12), case_id=c.id, case_token=c.employer_token,
                             worker_id=w.id, employer_id=e.id, ip_hash=iph, created_ts=ts, expires_ts=ts + TTL_S)
        s.add(row)
        s.commit()
        s.refresh(row)
        ctx = messages.load_ctx(s, c.id)   # loaded eagerly; usable after the session closes
    # 2. no session open: template text (no LLM) and audio from cached clips only (ffmpeg, no Gnani)
    try:
        draft = await messages.compose(ctx, "polite", use_llm=False)
        note = await polite_note_audio(draft.speech, messages.tts_lang(draft.lang))
    except Exception:
        with db.session() as s:   # do not leave a half-made sandbox behind
            r = s.get(SandboxSession, row.id)
            if r is not None:
                _delete_case_rows(s, r)
                s.commit()
        raise
    with db.session() as s:   # 3. short write: the note she "sent"
        m = Message(case_id=row.case_id, step="polite", direction="to_employer", language=draft.lang,
                    text=draft.text, audio_path=note["key"], status="sent", sent_at=now_iso)
        s.add(m)
        s.flush()
        case = s.get(Case, row.case_id)
        if case is not None:
            ledger.snapshot_message(s, m, case)
        s.commit()
    return row


def load(s: Session, sid: str) -> tuple[SandboxSession, Case]:
    """The live sandbox and its case, or SandboxError 404 / 410."""
    if not sid or len(sid) > 64:
        raise SandboxError(404, "not_found", "This demo link was not found. Start a new one.")
    row = s.get(SandboxSession, sid)
    if row is None:
        raise SandboxError(404, "not_found", "This demo link was not found. Start a new one.")
    case = s.get(Case, row.case_id)
    if row.expires_ts <= _now() or case is None or case.employer_token != row.case_token:
        raise SandboxError(410, "expired", "This demo has expired. Start a new one.")
    return row, case


def latest_note(s: Session, case_id: int) -> Message | None:
    return s.exec(select(Message).where(Message.case_id == case_id, Message.direction == "to_employer",
                                        Message.step == "polite").order_by(Message.id.desc())).first()


def paid_alert(s: Session, case_id: int) -> Message | None:
    return s.exec(select(Message).where(Message.case_id == case_id, Message.step == "paid_alert")
                  .order_by(Message.id.desc())).first()


def meta(row: SandboxSession) -> dict[str, Any]:
    return {"sandbox_id": row.id, "banner": BANNER, "synthetic": True, "expires_at": _iso(row.expires_ts),
            "expires_in_s": max(0, int(row.expires_ts - _now()))}
