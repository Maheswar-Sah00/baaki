"""V09 Hisaab Milao: the employer proposes a correction by voice (or typing); the worker accepts or rejects.
F2: the employer page's "I've paid" is also a proposal here (kind "said_paid"), so she confirms money too.

  POST /api/hisaab/e/{token}        employer: multipart `audio` (Hinglish/Telugu clip) and/or `text`, optional
                                    `amount`, `month` (2026-10), `kind` (cash|upi|advance|other) -> proposal
  GET  /api/hisaab/e/{token}        employer: his proposals and their statuses + the balance (no case id)
  GET  /api/hisaab/case/{case_id}   worker: pending and decided proposals + the balance
  GET  /api/hisaab/{id}/audio       worker: the read-back in her language (Timbre via tts_cache)
  POST /api/hisaab/{id}/decide      worker: {"decision": "accept" | "reject"} -> updated balance

Rules: proposals live in their own tables (no new columns); never auto-accepted (the public sandbox's demo
confirmation is labelled "Demo: Lakshmi confirmed", synthetic). On accept the money goes through
app.ledger.record_payment + reconcile (the only writer of Payment rows and Case.amount_paid). A correction ("I gave
2,000 in October") is money from before, so it never settles a planned instalment; it re-splits the plan. A
"said_paid" claim she confirms is new money: it settles instalments, and only then the "Paisa aa gaya" alert and
the Fair Employer badge appear. On reject the proposal stays visible as "disputed" and no money moves.

Worker-only: with BAAKI_PUBLIC=1, app/security.py (F3) guards `/api/hisaab/{proposal_id}/decide`, `/audio` and
`/case/{case_id}` with the worker key of the proposal's case owner (ROUTE_RULES, owner kind "hisaab"), so the
employer page cannot decide his own claim. Employer responses here never carry `case_id` or the payment id.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import audio, db, ledger, tts_cache
from ..gnani import GnaniError
from ..hisaab_core import (CLAIM_KIND, CLAIM_STATUS_EMPLOYER, CLAIM_STATUS_WORKER, DISPLAY_STATE, KINDS, METHOD_OF,
                           NO_AMOUNT, STATUS_EMPLOYER, STATUS_WORKER, chip, claim_chip, claim_diary_text, claim_note,
                           diary_text, parse_correction, parse_typed_amount, payment_note, readback, status_text,
                           valid_month)
from ..hisaab_models import HisaabClaim, HisaabProposal
from ..messages import CaseCtx, fmt_money, load_ctx, load_ctx_by_token, month_name, norm_lang, tts_lang
from ..stt_service import transcribe_upload
from .cases import add_diary_entry
from .employer import ACCEPTED_AUDIO, MAX_UPLOAD_BYTES, STT_FOR, badge, send_paid_alert
from .letters import gnani_error_dict, media_url, store

log = logging.getLogger("hisaab")
router = APIRouter(prefix="/api/hisaab", tags=["hisaab"])

MAX_TEXT = 500


# --------------------------------------------------------------------------- helpers
def _ctx_by_token(s: Session, token: str) -> CaseCtx:
    ctx = load_ctx_by_token(s, token)
    if ctx is None:
        raise HTTPException(404, "link not found")
    return ctx


def _ctx_by_case(s: Session, case_id: int) -> CaseCtx:
    ctx = load_ctx(s, case_id)
    if ctx is None:
        raise HTTPException(404, "case not found")
    return ctx


def _proposals(s: Session, ctx: CaseCtx) -> list[HisaabProposal]:
    return list(s.exec(select(HisaabProposal).where(HisaabProposal.case_id == ctx.case.id,
                                                    HisaabProposal.case_token == ctx.case.employer_token)
                       .order_by(HisaabProposal.id.desc())))  # type: ignore[union-attr]


def _claim(s: Session, p: HisaabProposal) -> Optional[HisaabClaim]:
    if p.kind != CLAIM_KIND:
        return None
    return s.exec(select(HisaabClaim).where(HisaabClaim.proposal_id == p.id)).first()


def _proposal_ctx(s: Session, proposal_id: int) -> tuple[HisaabProposal, CaseCtx]:
    p = s.get(HisaabProposal, proposal_id)
    ctx = load_ctx(s, p.case_id) if p else None
    if p is None or ctx is None or p.case_token != ctx.case.employer_token:  # stale after a demo reset
        raise HTTPException(404, "proposal not found")
    return p, ctx


def _audio_url(p: HisaabProposal) -> str:
    return f"/api/hisaab/{p.id}/audio"


def proposal_view(p: HisaabProposal, ctx: CaseCtx, claim: Optional[HisaabClaim] = None, *,
                  for_employer: bool = False) -> dict[str, Any]:
    e, w = ctx.employer, ctx.worker
    is_claim = p.kind == CLAIM_KIND
    method = claim.method if claim else METHOD_OF.get(p.kind, "other")
    st_emp = CLAIM_STATUS_EMPLOYER if is_claim else STATUS_EMPLOYER
    st_wkr = CLAIM_STATUS_WORKER if is_claim else STATUS_WORKER
    out = {
        "id": p.id, "case_id": p.case_id, "status": p.status, "display_state": DISPLAY_STATE[p.status],
        "type": "payment_claim" if is_claim else "correction", "method": method if is_claim else None,
        "demo": bool(claim and claim.demo),
        "said_by": p.said_by, "said_by_name": e.name,
        "said_by_label": f"said paid by the employer ({e.name})" if is_claim else f"said by the employer ({e.name})",
        "amount": p.amount, "amount_display": fmt_money(p.amount), "signed_display": "−" + fmt_money(p.amount),
        "amount_source": p.amount_source, "kind": p.kind,
        "month": p.month, "month_label": month_name(p.month, "en", year=True) if p.month else None,
        "transcript": p.transcript, "source": p.source, "language": p.language,
        "chip": claim_chip(p.amount, method, e.name) if is_claim else chip(p.amount, p.kind, p.month, e.name),
        "readback": {"text": p.worker_text, "speech": p.worker_speech, "language": p.worker_lang,
                     "audio_url": _audio_url(p)},
        "employer_audio_url": media_url(p.employer_audio_key),
        "exceeds_balance": p.status == "proposed" and p.amount > ctx.balance + 0.5,
        "payment_id": p.payment_id, "balance_before": p.balance_before, "balance_after": p.balance_after,
        "status_text_employer": status_text(st_emp, p.status, ctx.employer_lang, w.name),
        "status_text_worker": status_text(st_wkr, p.status, ctx.worker_lang, w.name),
        "created_at": p.created_at, "decided_at": p.decided_at,
    }
    if for_employer:   # his pages are keyed by the token; never hand him the worker's case id
        out.pop("case_id", None)
        out.pop("payment_id", None)
    return out


def _money(s: Session, ctx: CaseCtx) -> dict[str, Any]:
    mv = ledger.money_view(s, ctx.case)
    return {"total_due": ctx.total_due, "amount_paid": ctx.paid, "balance": ctx.balance,
            "balance_display": fmt_money(ctx.balance), "overpaid": mv["overpaid"], "case_status": ctx.case.status}


def _summary(s: Session, ctx: CaseCtx, *, for_employer: bool = False) -> dict[str, Any]:
    ps = _proposals(s, ctx)
    views = [proposal_view(p, ctx, _claim(s, p), for_employer=for_employer) for p in ps]
    out = {
        "case_id": ctx.case.id,
        "worker": {"name": ctx.worker.name, "language": ctx.worker_lang},
        "employer": {"name": ctx.employer.name, "language": ctx.employer_lang},
        **_money(s, ctx),
        "proposals": views,
        "pending": sum(1 for p in ps if p.status == "proposed"),
        "pending_claims": sum(1 for p in ps if p.status == "proposed" and p.kind == CLAIM_KIND),
        "disputed_total": round(sum(p.amount for p in ps if p.status == "rejected"), 2),
        "notice": "Corrections and payments are said by the employer. Baaki does not verify them; the worker decides.",
    }
    if for_employer:
        out.pop("case_id", None)
    return out


async def _readback_audio(p: HisaabProposal) -> tuple[Optional[tts_cache.Entry], Optional[dict]]:
    """One Timbre call (cached by text): the read-back in her language with <slow> on the amount."""
    try:
        entry = await tts_cache.synth(p.worker_speech, tts_lang(p.worker_lang))
        return entry, None
    except (GnaniError, audio.AudioError, ValueError) as ex:
        return None, gnani_error_dict(ex)


# --------------------------------------------------------------------------- employer side
@router.post("/e/{token}")
async def propose(token: str, audio_file: Optional[UploadFile] = File(None, alias="audio"),
                  text: str = Form(""), amount: Optional[str] = Form(None), month: Optional[str] = Form(None),
                  kind: Optional[str] = Form(None), lang: Optional[str] = Form(None),
                  readback_audio: bool = Form(True)) -> dict:
    """The employer says (or types) what he remembers. Returns a PROPOSED correction; nothing changes until the
    worker accepts it."""
    if kind is not None and kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {KINDS}")
    try:
        month_typed = valid_month(month)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(text or "") > MAX_TEXT:
        raise HTTPException(400, f"text longer than {MAX_TEXT} characters")
    typed_amount = parse_typed_amount(amount)
    if amount not in (None, "") and typed_amount is None:
        raise HTTPException(400, {"error": "bad_amount", "message": "amount must be a number of rupees"})

    data, ext = None, None
    if audio_file is not None and (audio_file.filename or audio_file.content_type):
        name = audio_file.filename or "hisaab"
        ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
        if ext not in ACCEPTED_AUDIO:
            raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
        data = await audio_file.read()
        if not data:
            raise HTTPException(400, "empty audio")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "audio larger than 25 MB")
    if data is None and not (text or "").strip() and typed_amount is None:
        raise HTTPException(400, {"error": "empty", "message": "record a voice note or type what you remember"})

    with db.session() as s:   # read only; closed before Prisma
        ctx = _ctx_by_token(s, token)
        src = norm_lang(lang or ctx.employer.language)
        if ctx.balance <= 0:
            raise HTTPException(409, {"error": "nothing_due", "message": "nothing is owed on this account"})
        case_id, case_token = ctx.case.id, ctx.case.employer_token
    stt_info: dict[str, Any] = {}
    transcript = (text or "").strip()
    if data is not None:
        codes, mode = STT_FOR[src]   # Hinglish: hi-IN,en-IN + codemix (never transcribe with 2 languages)
        try:
            stt = await transcribe_upload(data, f"hisaab.{ext}", lang=codes, mode=mode)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except audio.AudioError as e:
            raise HTTPException(415, f"could not decode audio: {e}")
        except GnaniError as e:
            raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
        heard = (stt.get("transcript") or "").strip()
        stt_info = {"language_code": stt.get("language_code"), "mode": stt.get("mode"),
                    "duration_s": stt.get("duration_s")}
        if not heard and typed_amount is None and not transcript:
            raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please record again"})
        transcript = (heard + (" " + transcript if transcript and transcript != heard else "")).strip()
    parsed = parse_correction(transcript, src)
    final_amount = typed_amount if typed_amount is not None else parsed["amount"]
    if final_amount is None or final_amount <= 0:
        raise HTTPException(422, {"error": "no_amount", "state": "no_amount", "message": NO_AMOUNT[src],
                                  "message_en": NO_AMOUNT["en"], "transcript": transcript, "parsed": parsed,
                                  "stt": stt_info or None})
    final_month = month_typed or parsed["month"]
    final_kind = kind or parsed["kind"]
    orig_key = store(case_id, data, ext) if data is not None else None

    with db.session() as s:   # short write
        ctx = _ctx_by_token(s, token)
        if ctx.case.id != case_id or ctx.case.employer_token != case_token:
            raise HTTPException(404, "link not found")
        e, w = ctx.employer, ctx.worker
        rb = readback(e.name, final_amount, final_kind, final_month, ctx.worker_lang)
        p = HisaabProposal(case_id=ctx.case.id, case_token=ctx.case.employer_token, worker_id=w.id,
                           employer_id=e.id, amount=round(float(final_amount), 2),
                           amount_source="typed" if typed_amount is not None else "spoken",
                           kind=final_kind, month=final_month, transcript=transcript,
                           source="voice" if data is not None else "text", language=src,
                           stt_json=json.dumps(stt_info), employer_audio_key=orig_key,
                           worker_text=rb["text"], worker_speech=rb["speech"], worker_lang=rb["language"])
        s.add(p)
        s.flush()
        add_diary_entry(s, w.id, diary_text("proposed", employer_name=e.name, worker_name=w.name, amount=p.amount,
                                            kind=p.kind, month=p.month, proposal_id=p.id),
                        employer_id=e.id, case_id=ctx.case.id, kind="note",
                        audio_sha256=db.sha256_hex(data) if data is not None else None)
        s.commit()
        s.refresh(p)
        pid = p.id
    audio_err = None
    if readback_audio:
        entry, audio_err = await _readback_audio(p)   # outside any session
        if entry is not None:
            with db.session() as s:
                row = s.get(HisaabProposal, pid)
                if row is not None:
                    row.readback_tts_key = entry.key
                    s.add(row)
                    s.commit()
                    p = row
    with db.session() as s:
        ctx = _ctx_by_token(s, token)
        p = s.get(HisaabProposal, pid) or p
        view = proposal_view(p, ctx, for_employer=True)
        return {"state": "proposed", "proposal": view, "parsed": parsed, "stt": stt_info or None,
                "readback_audio_error": audio_err, **_money(s, ctx),
                "message": f"Sent to {ctx.worker.name} as a proposal. Nothing changes until she agrees."}


@router.get("/e/{token}")
async def employer_list(token: str) -> dict:
    with db.session() as s:
        ctx = _ctx_by_token(s, token)
        return _summary(s, ctx, for_employer=True)


# --------------------------------------------------------------------------- worker side
@router.get("/case/{case_id}")
async def case_list(case_id: int) -> dict:
    with db.session() as s:
        ctx = _ctx_by_case(s, case_id)
        return _summary(s, ctx)


@router.get("/{proposal_id}/audio")
async def proposal_audio(proposal_id: int):
    with db.session() as s:
        p, _ctx = _proposal_ctx(s, proposal_id)
        path = tts_cache.lookup(p.readback_tts_key) if p.readback_tts_key else None
        speech, lang_ = p.worker_speech, p.worker_lang
    if path is None:
        entry, err = await _readback_audio(p)   # outside any session
        if entry is None:
            raise HTTPException(503, {"error": "readback_audio_unavailable", "detail": err, "text": p.worker_text})
        with db.session() as s:
            row = s.get(HisaabProposal, proposal_id)
            if row is not None and row.worker_speech == speech and row.worker_lang == lang_:
                row.readback_tts_key = entry.key
                s.add(row)
                s.commit()
        path = entry.path
    return FileResponse(path, media_type="audio/ogg", headers={"Cache-Control": "private, max-age=3600"})


class DecideIn(BaseModel):
    decision: Literal["accept", "reject"]


async def decide_proposal(proposal_id: int, decision: str, *, demo: bool = False) -> dict:
    """Her decision. accept -> app.ledger.record_payment + reconcile (+ the "Paisa aa gaya" alert for a payment
    claim); reject -> disputed, nothing changes. `demo` is only for the public sandbox's synthetic confirmation."""
    alert_for: Optional[tuple[int, float, bool]] = None
    payment: Optional[dict[str, Any]] = None
    rec: Optional[dict[str, Any]] = None
    with db.session() as s:
        p, ctx = _proposal_ctx(s, proposal_id)
        claim = _claim(s, p)
        if p.status != "proposed":
            raise HTTPException(409, {"error": "already_decided", "message": f"already {DISPLAY_STATE[p.status]}",
                                      "proposal": proposal_view(p, ctx, claim)})
        c, e, w = ctx.case, ctx.employer, ctx.worker
        is_claim = p.kind == CLAIM_KIND
        now = db.now_iso()
        bal = ctx.balance
        if decision == "accept":
            if bal <= 0:
                raise HTTPException(409, {"error": "nothing_due", "message": "nothing is owed on this account"})
            if not is_claim and p.amount > bal + ledger.TOL:
                raise HTTPException(409, {"error": "too_much",
                                          "message": f"{fmt_money(p.amount)} is more than the {fmt_money(bal)} "
                                                     "still owed, so it can't be accepted"})
            method = claim.method if claim else METHOD_OF.get(p.kind, "other")
            note = (claim_note(p.id, e.name, method, demo=demo) if is_claim
                    else payment_note(p.id, e.name, p.month))
            try:
                res = ledger.record_payment(
                    s, c, p.amount, method, note,
                    "sandbox_demo" if demo else ("employer_claim" if is_claim else "hisaab_correction"),
                    # a correction is about money given BEFORE: it re-splits a plan, it never settles an instalment
                    plan_credit=is_claim, proposal_id=p.id)
            except ledger.LedgerError as ex:
                raise HTTPException(ex.status, ex.as_dict())
            p.payment_id = res.payment.id
            p.status = "accepted"
            payment, rec = res.as_dict(), res.reconcile
            if is_claim:
                alert_for = (c.id, res.recorded, bool(claim.alert_audio) if claim else True)
        else:
            p.status = "rejected"
            rec = ledger.reconcile(s, c)   # nothing moved; keeps derived state honest
        p.decided_at = now
        p.balance_before = bal
        p.balance_after = c.balance
        if is_claim:
            text = claim_diary_text(p.status, employer_name=e.name, worker_name=w.name, amount=p.amount,
                                    method=claim.method if claim else "other", proposal_id=p.id, demo=demo)
        else:
            text = diary_text(p.status, employer_name=e.name, worker_name=w.name, amount=p.amount,
                              kind=p.kind, month=p.month, proposal_id=p.id)
        add_diary_entry(s, w.id, text, employer_id=e.id, case_id=c.id,
                        kind="payment" if p.status == "accepted" else "note")
        if claim is not None and demo:
            claim.demo = True
            s.add(claim)
        s.add(p)
        s.commit()
        case_id = c.id
    alert = None
    if alert_for is not None:   # after the commit, outside the session (Timbre may run)
        alert = await send_paid_alert(alert_for[0], alert_for[1], want_audio=alert_for[2])
        if alert is not None:
            with db.session() as s:
                cl = s.exec(select(HisaabClaim).where(HisaabClaim.proposal_id == proposal_id)).first()
                if cl is not None:
                    cl.alert_message_id = alert["message_id"]
                    s.add(cl)
                    s.commit()
    with db.session() as s:
        ctx = _ctx_by_case(s, case_id)
        p = s.get(HisaabProposal, proposal_id)
        claim = _claim(s, p)
        full = ctx.total_due > 0 and ctx.balance <= 0
        return {"proposal": proposal_view(p, ctx, claim), "decision": decision, **_money(s, ctx),
                "changed": p.status == "accepted", "payment": payment,
                "fully_paid": full if p.status == "accepted" else False,
                "reopened": bool(rec and rec.get("reopened")),
                "badge": badge(ctx) if (full and p.status == "accepted") else None,
                "alert": alert, "plan": rec.get("plan") if rec else None,
                "confirmed_label": "Demo: Lakshmi confirmed" if demo and p.status == "accepted" else None}


@router.post("/{proposal_id}/decide")
async def decide(proposal_id: int, body: DecideIn) -> dict:
    """She decides. accept -> the ledger records the money; reject -> disputed."""
    return await decide_proposal(proposal_id, body.decision)
