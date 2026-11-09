"""V04 Be Sharma ji: public employer sandbox (cached audio only, 0 Gnani calls).

  POST /api/sandbox                    new synthetic copy of the seeded Sharma ji case -> sandbox id + employer view
  GET  /api/sandbox                    {active, cap, ttl_s} (ops)
  GET  /api/sandbox/{sid}              Sharma ji's phone: voice note, itemised dues, UPI switched off
  POST /api/sandbox/{sid}/played       Sharma ji played the note
  POST /api/sandbox/{sid}/paid         "Mark as paid" (no real money) -> claim -> "Demo: Lakshmi confirmed" (synthetic)
                                       -> Lakshmi's "Paisa aa gaya!"
  GET  /api/sandbox/{sid}/worker       Lakshmi's phone (polled)
  GET  /api/sandbox/{sid}/audio/note   the cached polite voice note (Ogg/Opus)
  GET  /api/sandbox/{sid}/audio/paid   the cached "Paisa aa gaya" clip (after paying)
  POST /api/sandbox/{sid}/reply        always 403: no live voice reply for public users

Delegates to the real employer logic (routes/employer.py) with the sandbox's private token, then strips
anything a public page must not show (token, case id, UPI, PDF, live reply).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .. import db, sandbox_core as core, security
from ..messages import fmt_money, load_ctx, tts_lang
from . import employer, hisaab

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

NO_STORE = {"Cache-Control": "no-store"}


def client_ip(request: Request) -> str:
    """One client-IP rule for the whole app (security.client_ip; TRUSTED_PROXY decides which headers count)."""
    return security.client_ip(request)


def _err(e: core.SandboxError) -> JSONResponse:
    headers = dict(NO_STORE)
    if e.retry_after is not None:
        headers["Retry-After"] = str(e.retry_after)
    return JSONResponse(status_code=e.status, content=e.as_dict(), headers=headers)


def _token(sid: str) -> str:
    with db.session() as s:
        _, case = core.load(s, sid)
        return case.employer_token


async def employer_view(sid: str) -> dict[str, Any]:
    with db.session() as s:
        row, case = core.load(s, sid)
        token = case.employer_token
        note = core.latest_note(s, case.id)
    page = await employer.employer_page(token)  # the real employer page logic
    has_audio = bool(note and note.audio_path)
    msg = page.get("message") or {}
    return {
        **core.meta(row),
        "status": page["status"],
        "worker": page["worker"],
        "employer": page["employer"],
        "items": page["items"],
        "total_due": page["total_due"],
        "amount_paid": page["amount_paid"],
        "balance": page["balance"],
        "balance_display": page["balance_display"],
        "currency": "INR",
        "message": {"text": msg.get("text"), "language": msg.get("language"), "status": msg.get("status"),
                    "sent_at": msg.get("sent_at")} if msg else None,
        "voice_note": {
            "available": has_audio,
            "audio_url": f"/api/sandbox/{sid}/audio/note" if has_audio else None,
            "label": "Cached voice note (no live AI call)" if has_audio else "Voice note unavailable",
            "reason": None if has_audio else "No cached audio for this note on this server. The text is below.",
        },
        "upi": {"enabled": False, "label": core.UPI_OFF},
        "reply": {"enabled": False, "label": core.REPLY_OFF},
        "badge": page["badge"],
        "played": row.played_at is not None,
        "paid": row.paid_at is not None or page["balance"] <= 0,
        "ai_notice": page["ai_notice"],
    }


def _alert_view(sid: str, m) -> dict[str, Any] | None:
    if m is None:
        return None
    return {"headline": core.PAID_HEADLINE, "headline_en": core.PAID_HEADLINE_EN, "text": m.text,
            "language": m.language, "sent_at": m.sent_at,
            "audio_url": f"/api/sandbox/{sid}/audio/paid" if m.audio_path else None,
            "audio_label": "Cached clip (no live AI call)" if m.audio_path else "Clip unavailable"}


# --------------------------------------------------------------------------- routes
@router.post("")
async def create_sandbox(request: Request):
    try:
        row = await core.create(client_ip(request))
        view = await employer_view(row.id)
    except core.SandboxError as e:
        return _err(e)
    return JSONResponse(status_code=201, content={**view, "ttl_s": core.TTL_S}, headers=NO_STORE)


@router.get("")
async def sandbox_stats() -> dict:
    with db.session() as s:
        return {"active": core.active_count(s), "cap": core.MAX_SANDBOXES, "ttl_s": core.TTL_S,
                "banner": core.BANNER}


@router.get("/{sid}")
async def get_sandbox(sid: str):
    try:
        return JSONResponse(content=await employer_view(sid), headers=NO_STORE)
    except core.SandboxError as e:
        return _err(e)


@router.post("/{sid}/played")
async def played(sid: str):
    try:
        await employer.played(_token(sid))
        with db.session() as s:
            row, _ = core.load(s, sid)
            if row.played_at is None:
                row.played_at = db.now_iso()
                s.add(row)
                s.commit()
            return JSONResponse(content={**core.meta(row), "played": True}, headers=NO_STORE)
    except core.SandboxError as e:
        return _err(e)


@router.post("/{sid}/paid")
async def mark_paid(sid: str):
    """"Mark as paid" in the public demo: the same two steps as the real app, through the same ledger code.
    1. Sharma ji's tap is a CLAIM (employer.pay, alert audio off).
    2. A synthetic "Demo: Lakshmi confirmed" (hisaab.decide_proposal with demo=True) records it, which writes the
       "Paisa aa gaya" alert and the badge. The clip is attached only if exactly that sentence is cached.
    Zero Gnani calls: alert_audio is off and nothing synthesises."""
    try:
        token = _token(sid)
        already, res, decided = False, None, None
        try:  # step 1: the real "I've paid" (no real money moves)
            res = await employer.pay(token, employer.PayIn(method="other", note=core.NO_MONEY_NOTE,
                                                           alert_audio=False))
        except HTTPException as ex:
            if ex.status_code != 409:
                raise
            already = True
        if res is not None:
            try:  # step 2: the demo confirmation, clearly labelled synthetic
                decided = await hisaab.decide_proposal(res["claim"]["id"], "accept", demo=True)
            except HTTPException as ex:
                if ex.status_code not in (404, 409):
                    raise
                already = True
        with db.session() as s:
            row, case = core.load(s, sid)
            alert = core.paid_alert(s, case.id)
            got = decided.get("alert") if decided else None
            if got is not None and alert is not None and not alert.audio_path:
                key = core.paid_clip_key(got["speech"], tts_lang(got["language"]))
                if key:  # exactly this sentence is already cached: attach it
                    alert.audio_path = key
                    s.add(alert)
            if row.paid_at is None and case.balance <= 0:
                row.paid_at = db.now_iso()
                s.add(row)
            s.commit()
            ctx = load_ctx(s, case.id)
            recorded = decided["payment"]["recorded"] if decided and decided.get("payment") else None
            return JSONResponse(content={
                **core.meta(row), "already_paid": already,
                "paid": recorded, "paid_display": fmt_money(recorded) if recorded is not None else None,
                "amount_paid": case.amount_paid, "balance": case.balance,
                "balance_display": fmt_money(case.balance), "fully_paid": case.balance <= 0,
                "status": case.status,
                "badge": employer.badge(ctx) if (ctx is not None and case.balance <= 0) else None,
                "claim": {"said_by": ctx.employer.name if ctx else None, "label": f"{ctx.employer.name} said he paid"
                          if ctx else None} if res is not None else None,
                "confirmation": {"demo": True, "label": core.DEMO_CONFIRMED_LABEL, "synthetic": True}
                if (decided or already) else None,
                "upi": {"enabled": False, "label": core.UPI_OFF}, "note": core.NO_MONEY_NOTE,
                "alert": _alert_view(sid, alert)}, headers=NO_STORE)
    except core.SandboxError as e:
        return _err(e)


@router.get("/{sid}/worker")
async def worker_panel(sid: str):
    try:
        with db.session() as s:
            row, case = core.load(s, sid)
            ctx = load_ctx(s, case.id)
            note = core.latest_note(s, case.id)
            alert = core.paid_alert(s, case.id)
            return JSONResponse(content={
                **core.meta(row),
                "worker": {"name": ctx.worker.name, "language": ctx.worker.language},
                "employer": {"name": ctx.employer.name, "fair_employer": ctx.employer.fair_employer},
                "status": case.status, "total_due": case.total_due, "amount_paid": case.amount_paid,
                "balance": case.balance, "balance_display": fmt_money(case.balance),
                "note_status": note.status if note else None,
                "played": row.played_at is not None,
                "paid": alert is not None,
                "confirmation": {"demo": True, "label": core.DEMO_CONFIRMED_LABEL, "synthetic": True}
                if alert is not None else None,
                "alert": _alert_view(sid, alert),
            }, headers=NO_STORE)
    except core.SandboxError as e:
        return _err(e)


def _audio(key: str | None, what: str) -> Response:
    if not key:
        raise core.SandboxError(404, "no_audio", f"No cached {what} on this server.")
    try:
        data = core.read_audio(key)
    except Exception:
        raise core.SandboxError(404, "no_audio", f"No cached {what} on this server.")
    media = "audio/mpeg" if key.endswith(".mp3") else "audio/ogg"
    return Response(content=data, media_type=media, headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{sid}/audio/note")
async def note_audio(sid: str):
    try:
        with db.session() as s:
            _, case = core.load(s, sid)
            note = core.latest_note(s, case.id)
            return _audio(note.audio_path if note else None, "voice note")
    except core.SandboxError as e:
        return _err(e)


@router.get("/{sid}/audio/paid")
async def paid_audio(sid: str):
    try:
        with db.session() as s:
            _, case = core.load(s, sid)
            alert = core.paid_alert(s, case.id)
            return _audio(alert.audio_path if alert else None, "payment clip")
    except core.SandboxError as e:
        return _err(e)


@router.post("/{sid}/reply")
async def reply_disabled(sid: str):
    try:
        _token(sid)
    except core.SandboxError as e:
        return _err(e)
    return JSONResponse(status_code=403, content={"error": "reply_disabled", "message": core.REPLY_OFF},
                        headers=NO_STORE)
