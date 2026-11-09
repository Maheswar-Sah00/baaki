"""Access control and the Gnani credit budget (root cause R4). One mechanism each:

* `BAAKI_PUBLIC=1` switches all of this on. Unset (localhost filming): every request behaves as before
  (only the STT duration cap and name clean-up below apply everywhere).
* Worker keys: `POST /api/onboard` creates a worker and returns its secret key once; only sha256(key) is
  stored (table `workerkey`). `guard` (one app-level dependency, main.py) classifies every route by its path
  template in `ROUTE_RULES`, resolves the worker who owns the request (path ids, query/body `worker_id`, ...)
  and compares `X-Baaki-Key` with `hmac.compare_digest`. Unclassified routes fail closed (404) in public mode.
  Seeded synthetic workers have no key: they are open when `BAAKI_DEMO_OPEN=1` (default) so the demo is viewable.
* Demo reset routes need `X-Admin-Token` == `BAAKI_ADMIN_TOKEN` in public mode (404 otherwise).
* Gnani budget: `take_gnani_budget(kind)` is called from the one chokepoint `GnaniClient._request`:
  daily calls per kind (GNANI_BUDGET_STT / _TTS / _VC) and per client IP (GNANI_BUDGET_PER_IP). Over budget
  -> `GnaniError(429, "budget")`, which every route already turns into a text-only fallback.
  `tts_live_allowed()` makes tts_cache cache-only outside an allowlist of routes (TTS_LIVE_ROUTES).
* Client IP: `client_ip()` trusts proxy headers only when TRUSTED_PROXY=1 (config.trusted_proxy()).
* `RequestContextMiddleware` (pure ASGI): client IP + route for the budget, request id, security headers,
  per-request public base URL behind a trusted proxy.
* `clean_name()` runs on every Employer/Worker insert/update (SQLAlchemy events): names are spoken by Timbre,
  so URLs, e-mails, digits and long strings are stripped.

/api/media/{key} rule (public mode): keys are `c{case_id}/{stamp}_{random}.ext`. Media of a case whose worker
has no key (synthetic demo) is served as before. Media of a keyed (real) worker's case is served only with her
key (header, or the `baaki_key` cookie for GET so <audio src> works), or when the file is a voice note / PDF
already SENT to the employer (the employer page plays it). Anything else is 404. Keys outside `c{n}/` (dues
notes) are random and served as before.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import threading
import unicodedata
import uuid
import weakref
from contextvars import ContextVar
from typing import Any, Optional

from fastapi import HTTPException, Request
from sqlalchemy import event
from sqlmodel import Field, Session, SQLModel, select

from . import config, db

log = logging.getLogger("security")

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
KEY_HEADER = "x-baaki-key"
KEY_COOKIE = "baaki_key"
ADMIN_HEADER = "x-admin-token"


# =========================================================================== worker keys
class WorkerKey(SQLModel, table=True):
    """sha256 of a worker's secret key (the key itself is shown once, never stored)."""
    __tablename__ = "workerkey"
    worker_id: int = Field(primary_key=True, sa_column_kwargs={"autoincrement": False})
    key_hash: str = Field(index=True)
    created_at: str = Field(default_factory=db.now_iso)


_tables_ready: "weakref.WeakSet[Any]" = weakref.WeakSet()


def _ensure_table(s: Session) -> None:
    eng = s.get_bind()
    if eng not in _tables_ready:
        WorkerKey.__table__.create(bind=eng, checkfirst=True)  # type: ignore[attr-defined]
        _tables_ready.add(eng)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def new_key() -> str:
    return "bk_" + secrets.token_urlsafe(24)


def issue_key(s: Session, worker_id: int) -> str:
    """Create (or rotate) the worker's key. Returns the plain key; only its hash is stored."""
    _ensure_table(s)
    key = new_key()
    row = s.get(WorkerKey, worker_id)
    if row is None:
        row = WorkerKey(worker_id=worker_id, key_hash=hash_key(key))
    else:
        row.key_hash, row.created_at = hash_key(key), db.now_iso()
    s.add(row)
    return key


def wipe_keys(s: Session) -> None:
    """Demo reset: worker ids are reused after a wipe, so old keys must never attach to new workers."""
    _ensure_table(s)
    for row in s.exec(select(WorkerKey)).all():
        s.delete(row)


def _key_row(s: Session, worker_id: int) -> Optional[WorkerKey]:
    """The worker's key row, or None for a keyless (synthetic demo) worker. A key older than the worker row
    belongs to a wiped worker whose id was reused: it is ignored."""
    from .models import Worker

    _ensure_table(s)
    row = s.get(WorkerKey, worker_id)
    if row is None:
        return None
    w = s.get(Worker, worker_id)
    if w is None or (w.created_at and row.created_at < w.created_at):
        return None
    return row


def is_demo_worker(s: Session, worker_id: int) -> bool:
    return _key_row(s, worker_id) is None


def _key_matches(row: WorkerKey, key: str | None) -> bool:
    return bool(key) and hmac.compare_digest(row.key_hash, hash_key(key or ""))


def _any_worker_for_key(s: Session, key: str | None) -> Optional[int]:
    if not key:
        return None
    _ensure_table(s)
    h = hash_key(key)
    row = s.exec(select(WorkerKey).where(WorkerKey.key_hash == h)).first()
    if row is None or not hmac.compare_digest(row.key_hash, h) or _key_row(s, row.worker_id) is None:
        return None
    return row.worker_id


# =========================================================================== names that get spoken
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+|\b[\w.-]+\.(?:com|in|org|net|io|ly|me|co|xyz|app|dev|link|info|biz|site|online|top|gl)\b\S*")
_EMAIL_RE = re.compile(r"\S+@\S+")
MAX_NAME_CHARS = 40
_NAME_PUNCT = " .'-" + chr(0x200C) + chr(0x200D)  # ZWNJ/ZWJ shape Telugu and Devanagari names


def clean_name(name: str | None, fallback: str = "") -> str:
    """A short spoken name: no URLs, e-mails, UPI ids or digits; letters (any script), spaces, . ' - only;
    at most 40 characters. "Sharma ji" stays "Sharma ji"."""
    if not name:
        return fallback if name is None else name
    s = _URL_RE.sub(" ", str(name))
    s = _EMAIL_RE.sub(" ", s)
    keep = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("L", "M") or ch in _NAME_PUNCT:
            keep.append(ch)
        else:
            keep.append(" ")
    s = re.sub(r"\s+", " ", "".join(keep)).strip(" .-'")
    if len(s) > MAX_NAME_CHARS:
        s = s[:MAX_NAME_CHARS].rsplit(" ", 1)[0].strip() or s[:MAX_NAME_CHARS]
    return s or fallback or "Employer"


def _clean_name_listener(_mapper, _conn, target) -> None:
    name = getattr(target, "name", None)
    if isinstance(name, str) and name:
        cleaned = clean_name(name, "Employer" if type(target).__name__ == "Employer" else "Worker")
        if cleaned != name:
            target.name = cleaned


def install_name_guard() -> None:
    from .models import Employer, Worker

    for model in (Employer, Worker):
        for ev in ("before_insert", "before_update"):
            if not event.contains(model, ev, _clean_name_listener):
                event.listen(model, ev, _clean_name_listener)


install_name_guard()


# =========================================================================== client IP + request context
_REQ: ContextVar[Optional[dict]] = ContextVar("baaki_request", default=None)


def _valid_ip(v: str) -> str | None:
    v = v.strip()
    if not v:
        return None
    try:
        return str(ipaddress.ip_address(v))
    except ValueError:
        return None


def client_ip_from(headers: Any, peer: str | None) -> str:
    """The one client-IP rule (see config.trusted_proxy())."""
    mode = config.trusted_proxy()
    peer = peer or "unknown"
    if mode == "legacy":  # localhost, as before: Cloudflare tunnel header, first XFF hop, X-Real-IP, peer
        for value in (headers.get("cf-connecting-ip", ""), headers.get("x-forwarded-for", "").split(",")[0],
                      headers.get("x-real-ip", "")):
            if value.strip():
                return value.strip()
        return peer
    if mode == "1":
        cf = _valid_ip(headers.get("cf-connecting-ip", ""))
        if cf:
            return cf
        hops = [h for h in (x.strip() for x in headers.get("x-forwarded-for", "").split(",")) if h]
        n = config.trusted_proxy_hops()
        if len(hops) >= n:
            ip = _valid_ip(hops[-n])
            if ip:
                return ip
    return peer


def client_ip(request: Request) -> str:
    return client_ip_from(request.headers, request.client.host if request.client else None)


def current_ip() -> str:
    ctx = _REQ.get()
    return (ctx or {}).get("ip") or "local"


def current_route() -> str | None:
    ctx = _REQ.get()
    return (ctx or {}).get("route")


_HOST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}(:\d{1,5})?$")

API_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"permissions-policy", b"microphone=(self), camera=(), geolocation=()"),
]


def _request_base(headers: Any) -> str | None:
    if config.trusted_proxy() != "1":
        return None
    host = (headers.get("x-forwarded-host", "") or headers.get("host", "")).split(",")[0].strip()
    if not host or not _HOST_RE.match(host):
        return None
    proto = (headers.get("x-forwarded-proto", "") or "https").split(",")[0].strip().lower()
    proto = proto if proto in ("http", "https") else "https"
    return f"{proto}://{host}"


class RequestContextMiddleware:
    """Pure ASGI: sets the request context (client IP for the budget, request id, public base URL) and adds
    the API security headers and X-Request-ID to every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        from starlette.datastructures import Headers

        headers = Headers(scope=scope)
        peer = (scope.get("client") or (None, None))[0]
        rid_in = headers.get("x-request-id", "")
        rid = rid_in if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", rid_in or "") else uuid.uuid4().hex[:16]
        scope["baaki_request_id"] = rid
        _REQ.set({"ip": client_ip_from(headers, peer), "route": None, "request_id": rid})
        config.REQUEST_BASE_URL.set(_request_base(headers))

        async def send_wrapped(message):
            if message["type"] == "http.response.start":
                raw = list(message.get("headers") or [])
                present = {k.lower() for k, _ in raw}
                for k, v in API_SECURITY_HEADERS:
                    if k not in present:
                        raw.append((k, v))
                if b"x-request-id" not in present:
                    raw.append((b"x-request-id", rid.encode()))
                message["headers"] = raw
            await send(message)

        await self.app(scope, receive, send_wrapped)


def request_id() -> str | None:
    return (_REQ.get() or {}).get("request_id")


# =========================================================================== Gnani budget
def _ist_today() -> dt.date:
    return dt.datetime.now(IST).date()


class GnaniBudget:
    """Daily (IST) Gnani calls per kind and per client IP, in memory. Only enforced in public mode."""

    KINDS = {"stt": "stt", "tts": "tts", "vc_embed": "vc", "vc_tts": "vc"}

    def __init__(self):
        self._lock = threading.Lock()
        self._day: dt.date | None = None
        self.used: dict[str, int] = {}
        self.per_ip: dict[str, int] = {}

    def _roll(self) -> None:
        today = _ist_today()
        if self._day != today:
            self._day, self.used, self.per_ip = today, {}, {}

    def take(self, kind: str) -> None:
        if not config.baaki_public():
            return
        bucket = self.KINDS.get(kind, kind)
        limit = config.gnani_budget(bucket)
        ip_limit = config.gnani_budget_per_ip()
        ip = current_ip()
        with self._lock:
            self._roll()
            if limit is not None and self.used.get(bucket, 0) >= limit:
                raise _budget_error(f"Today's {bucket.upper()} budget for this demo is used up.")
            if ip_limit is not None and self.per_ip.get(ip, 0) >= ip_limit:
                raise _budget_error("This visitor's voice budget for today is used up.")
            self.used[bucket] = self.used.get(bucket, 0) + 1
            self.per_ip[ip] = self.per_ip.get(ip, 0) + 1

    def remaining(self) -> dict[str, Any]:
        if not config.baaki_public():
            return {"enforced": False}
        with self._lock:
            self._roll()
            out: dict[str, Any] = {"enforced": True}
            for b in ("stt", "tts", "vc"):
                lim = config.gnani_budget(b) or 0
                out[b] = max(0, lim - self.used.get(b, 0))
            out["per_ip_limit"] = config.gnani_budget_per_ip()
            return out

    def reset(self) -> None:
        with self._lock:
            self._day, self.used, self.per_ip = None, {}, {}


BUDGET = GnaniBudget()


def _budget_error(message: str):
    from .gnani import GnaniError

    return GnaniError(429, "budget", message + " Showing text instead.")


def take_gnani_budget(kind: str) -> None:
    """Called once per Gnani request from GnaniClient._request (the single chokepoint)."""
    BUDGET.take(kind)  # GNANI_BUDGET_VC defaults to 0: no cloned speech on a public deploy


def tts_live_allowed() -> bool:
    """tts_cache: may this request synthesise NEW audio? Always on localhost; in public mode only for the
    allowlisted routes (TTS_LIVE_ROUTES), cache hits elsewhere."""
    if not config.baaki_public():
        return True
    allowed = config.tts_live_routes()
    return "*" in allowed or (current_route() or "") in allowed


def cache_only_error():
    return _budget_error("New audio is not made on this page of the public demo.")


def cloning_enabled() -> bool:
    return not config.baaki_public()


# =========================================================================== route rules
PUBLIC, ADMIN, MEDIA, ANY, OFF = "public", "admin", "media", "any", "off"


class W:
    """A worker route: the owner is resolved from path ids, query `worker_id`/`case_id` and (body=True) the
    JSON or form body. `kinds` overrides what an id name points at (promise_id differs per feature)."""

    def __init__(self, body: bool = False, **kinds: str):
        self.body = body
        self.kinds = kinds

    def __repr__(self) -> str:  # pragma: no cover
        return f"W(body={self.body}, {self.kinds})"


DEFAULT_KINDS = {"worker_id": "worker", "case_id": "case", "message_id": "message", "exit_id": "exit",
                 "proposal_id": "hisaab", "account_id": "dues_account"}
QUERY_BODY_NAMES = ("worker_id", "case_id")

# Whole families that are public by design (employer-token pages, anonymous tools, cached audio).
PUBLIC_PREFIXES = ("/api/e/", "/api/raise/e/", "/api/hisaab/e/", "/api/check", "/api/quiz", "/api/proof",
                   "/api/sandbox")

ROUTE_RULES: dict[str, Any] = {
    "/health": PUBLIC, "/api/health": PUBLIC, "/api/voices": PUBLIC, "/api/onboard": PUBLIC,
    "/api/stt": OFF, "/api/tts": OFF,                     # raw Gnani passthroughs: never on a public deploy
    "/api/demo/reset": ADMIN, "/api/raise/demo": ADMIN, "/api/dues/demo": ADMIN,
    # cases / workers / diary
    "/api/cases/listen": ANY, "/api/cases/meter": ANY, "/api/cases/extract": ANY,
    "/api/cases": W(body=True),
    "/api/cases/{case_id}": W(), "/api/cases/{case_id}/readback": W(), "/api/cases/{case_id}/confirm": W(),
    "/api/cases/{case_id}/undo-retell": W(), "/api/cases/{case_id}/reminders": W(),
    "/api/workers/{worker_id}/dashboard": W(), "/api/workers/{worker_id}": W(),
    "/api/workers/{worker_id}/match-home": W(),
    "/api/diary": W(body=True),
    # letters
    "/api/cases/{case_id}/messages/{step}": W(), "/api/cases/{case_id}/messages": W(),
    "/api/messages/{message_id}/sent": W(), "/api/cases/{case_id}/legal-pack": W(),
    "/api/media/{key:path}": MEDIA,
    # verify
    "/api/verify/messages/{message_id}": W(),
    # exit
    "/api/exit/checklist": PUBLIC, "/api/exit/audio/{name}": PUBLIC,
    "/api/exit": W(body=True), "/api/exit/{exit_id}": W(),
    # inbox
    "/api/inbox/{case_id}": W(),
    "/api/inbox/promises/{promise_id}/remind": W(promise_id="inbox_promise"),
    "/api/inbox/promises/{promise_id}/status": W(promise_id="inbox_promise"),
    # dues ("Baaki for every promise"): owner through DuesOwner; an account with no owner -> any key / demo
    "/api/dues/parse": ANY, "/api/dues": W(body=True),
    "/api/dues/{account_id}": W(), "/api/dues/{account_id}/items": W(), "/api/dues/{account_id}/paid": W(),
    "/api/dues/{account_id}/promises": W(), "/api/dues/{account_id}/remind": W(),
    "/api/dues/{account_id}/pack.pdf": W(),
    "/api/dues/promises/{promise_id}/status": W(promise_id="dues_promise"),
    # raise (worker side)
    "/api/raise/summary": W(), "/api/raise/case/{case_id}": W(), "/api/raise/case/{case_id}/compose": W(),
    "/api/raise/case/{case_id}/sent": W(),
    # consent + voice profile
    "/api/consent": W(), "/api/consent/prompt": W(body=True), "/api/consent/match": W(body=True),
    "/api/consent/attempt": W(body=True), "/api/consent/withdraw": W(body=True),
    "/api/consent/audio/{name}": PUBLIC,
    "/api/voice-profile": W(body=True),
    # story, hisaab (worker side)
    "/api/story/{case_id}": W(),
    "/api/hisaab/case/{case_id}": W(), "/api/hisaab/{proposal_id}/audio": W(),
    "/api/hisaab/{proposal_id}/decide": W(),
}


def rule_for(template: str) -> Any:
    if template in ROUTE_RULES:
        return ROUTE_RULES[template]
    if any(template.startswith(p) for p in PUBLIC_PREFIXES):
        return PUBLIC
    return None


# --------------------------------------------------------------------------- owner resolution
_ANY_OWNER = -1  # the entity exists but has no worker (a dues account without a DuesOwner row)


def _as_int(v: Any) -> Optional[int]:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _owner(s: Session, kind: str, ident: int) -> Optional[int]:
    """Worker id that owns the entity, None if it does not exist, _ANY_OWNER if it has no worker."""
    from .models import Case, Message, Worker

    def case_owner(cid: int | None) -> Optional[int]:
        c = s.get(Case, cid) if cid is not None else None
        return c.worker_id if c else None

    if kind == "worker":
        return ident if s.get(Worker, ident) is not None else None
    if kind == "case":
        return case_owner(ident)
    if kind == "message":
        m = s.get(Message, ident)
        return case_owner(m.case_id) if m else None
    if kind == "exit":
        from .exit_kit import ExitKit
        e = s.get(ExitKit, ident)
        return e.worker_id if e else None
    if kind == "hisaab":
        from .hisaab_models import HisaabProposal
        p = s.get(HisaabProposal, ident)
        return p.worker_id if p else None
    if kind == "inbox_promise":
        from .inbox_models import InboxPromise
        p = s.get(InboxPromise, ident)
        return case_owner(p.case_id) if p else None
    if kind in ("dues_account", "dues_promise"):
        from . import dues_models as dm
        aid = ident
        if kind == "dues_promise":
            p = s.get(dm.DuesPromise, ident)
            if p is None:
                return None
            aid = p.account_id
        acc = s.get(dm.DuesAccount, aid)
        if acc is None:
            return None
        owner_model = getattr(dm, "DuesOwner", None)  # F4: accounts belong to a worker through DuesOwner
        row = s.get(owner_model, aid) if owner_model is not None else None
        wid = row.worker_id if row is not None else getattr(acc, "worker_id", None)
        return int(wid) if wid else _ANY_OWNER
    raise ValueError(f"unknown owner kind {kind}")


async def _body_fields(request: Request) -> dict[str, Any]:
    ctype = request.headers.get("content-type", "")
    try:
        if "application/json" in ctype:
            raw = await request.body()
            data = json.loads(raw) if raw else {}
            return data if isinstance(data, dict) else {}
        if "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
            form = await request.form()  # cached by Starlette: the route reads the same parsed form
            return {k: v for k, v in form.items() if isinstance(v, str)}
    except Exception:  # malformed body: the route's own validation answers
        return {}
    return {}


def _presented_key(request: Request) -> str | None:
    key = request.headers.get(KEY_HEADER)
    if not key and request.method in ("GET", "HEAD"):  # <audio src>, PDF links: cookie, read-only requests
        key = request.cookies.get(KEY_COOKIE)
    return (key or "").strip() or None


def _deny(status: int, code: str, message: str):
    raise HTTPException(status, {"error": code, "message": message})


def _check_owner(s: Session, worker_id: int, key: str | None) -> None:
    row = _key_row(s, worker_id)
    if row is None:  # synthetic demo worker
        if config.demo_open():
            return
        _deny(401, "key_required", "This worker's data needs her key.")
    if not key:
        _deny(401, "key_required", "Send the worker key (X-Baaki-Key).")
    if not _key_matches(row, key):
        _deny(403, "wrong_key", "This key does not open this worker's data.")


def _check_any(s: Session, key: str | None) -> None:
    if _any_worker_for_key(s, key) is not None or config.demo_open():
        return
    _deny(401, "key_required", "Send a worker key (X-Baaki-Key).")


def _check_admin(request: Request) -> None:
    want = config.admin_token()
    got = request.headers.get(ADMIN_HEADER, "")
    if not want or not got or not hmac.compare_digest(want.encode(), got.encode()):
        raise HTTPException(404, "Not Found")


_MEDIA_CASE_RE = re.compile(r"^c(\d+)/")


def _check_media(s: Session, request: Request) -> None:
    from .models import Message

    key = str(request.path_params.get("key", ""))
    m = _MEDIA_CASE_RE.match(key)
    if not m:
        return  # not tied to a case (dues notes): random key, served as before
    owner = _owner(s, "case", int(m.group(1)))
    if owner is None or _key_row(s, owner) is None:
        return  # missing case (route 404s) or synthetic demo worker
    row = _key_row(s, owner)
    if row is not None and _key_matches(row, _presented_key(request)):
        return
    sent = s.exec(select(Message).where(Message.case_id == int(m.group(1)),
                                        Message.direction == "to_employer",
                                        Message.status != "draft",
                                        (Message.audio_path == key) | (Message.pdf_path == key))).first()
    if sent is not None:
        return  # the employer may play what was sent to him
    raise HTTPException(404, "not found")


async def guard(request: Request) -> None:
    """The one app-level dependency (main.py). Records the route for the budget; in public mode, enforces
    ROUTE_RULES."""
    route = request.scope.get("route")
    template = getattr(route, "path", None) or request.url.path
    ctx = _REQ.get()
    if ctx is None:
        ctx = {"ip": client_ip(request), "route": None, "request_id": None}
        _REQ.set(ctx)
    ctx["route"] = template
    if not config.baaki_public():
        return
    rule = rule_for(template)
    if rule is None:
        log.warning("public mode: route %s is not classified in security.ROUTE_RULES (denied)", template)
        raise HTTPException(404, "Not Found")
    if rule == PUBLIC:
        return
    if rule == OFF:
        raise HTTPException(404, "Not Found")
    if rule == ADMIN:
        _check_admin(request)
        return
    key = _presented_key(request)
    with db.session() as s:
        if rule == MEDIA:
            _check_media(s, request)
            return
        if rule == ANY:
            _check_any(s, key)
            return
        assert isinstance(rule, W)
        found: list[tuple[str, int]] = []
        for name, value in request.path_params.items():
            kind = rule.kinds.get(name) or DEFAULT_KINDS.get(name)
            ident = _as_int(value)
            if kind and ident is not None:
                found.append((kind, ident))
        extra: dict[str, Any] = dict(request.query_params)
        if rule.body:
            extra.update(await _body_fields(request))
        for name in QUERY_BODY_NAMES:
            if name in extra and name not in request.path_params:
                ident = _as_int(extra[name])
                if ident is not None:
                    found.append((DEFAULT_KINDS[name], ident))
        owners = {o for o in (_owner(s, k, i) for k, i in found) if o is not None and o != _ANY_OWNER}
        if len(owners) > 1:
            _deny(403, "mixed_workers", "These ids belong to different workers.")
        if owners:
            _check_owner(s, owners.pop(), key)
        else:  # nothing owned (the route 404s on a missing id) or an entity without a worker
            _check_any(s, key)


# =========================================================================== onboarding limit
class _DailyCounter:
    def __init__(self):
        self._lock = threading.Lock()
        self._day: dt.date | None = None
        self._n: dict[str, int] = {}

    def take(self, who: str, limit: int | None) -> bool:
        if limit is None:
            return True
        with self._lock:
            today = _ist_today()
            if self._day != today:
                self._day, self._n = today, {}
            if self._n.get(who, 0) >= limit:
                return False
            self._n[who] = self._n.get(who, 0) + 1
            return True

    def reset(self) -> None:
        with self._lock:
            self._day, self._n = None, {}


ONBOARD_LIMIT = _DailyCounter()
