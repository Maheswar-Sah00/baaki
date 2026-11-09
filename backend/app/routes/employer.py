"""The employer's page (opened from the link in the voice note): see, say you paid, pay in parts, reply.

  GET  /api/e/{token}          itemised baaki, the SENT voice note (stale flag), UPI deep link, plan, claims, badge
  POST /api/e/{token}/played   the employer played the voice note
  POST /api/e/{token}/pay      "I've paid" -> a CLAIM (Hisaab proposal, kind "said_paid"). No money moves until the
                               worker confirms it (POST /api/hisaab/{id}/decide); only then "Paisa aa gaya" + badge
  POST /api/e/{token}/plan     2 or 3 instalments -> planned payments + reminders (app.ledger.create_plan)
  POST /api/e/{token}/reply    employer voice (Hinglish / Telugu) or typed `text` -> translation -> Timbre for her

No employer response carries `case_id` (the worker's routes are keyed by it). Sessions are never held across a
Gnani/translate/TTS await: read -> close -> slow work -> short write session.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audio, db, ledger, voice_note
from ..gnani import GnaniError
from ..hisaab_core import (CLAIM_KIND, CLAIM_SENT, CLAIM_STATUS_EMPLOYER, DISPLAY_STATE, claim_diary_text,
                           claim_readback)
from ..hisaab_models import HisaabClaim, HisaabProposal
from ..lang import extract_amounts, today_ist
from ..ledger import PAID_ALERT, REMINDER, split_amount  # noqa: F401  (re-exported: older imports and tests)
from ..messages import (CaseCtx, employer_url, fmt_date, fmt_money, item_label, load_ctx, load_ctx_by_token,
                        name_in, norm_lang, parse_lang, tts_lang, upi_link)
from ..models import Message
from ..stt_service import transcribe_upload
from ..translate import translate
from .cases import add_diary_entry
from .letters import gnani_error_dict, media_url, message_view, store

log = logging.getLogger("employer")
router = APIRouter(prefix="/api/e", tags=["employer"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_REPLY_TEXT = 1000
ACCEPTED_AUDIO = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}
# Prisma settings for the employer's reply. Hinglish: hi-IN,en-IN + codemix (feasibility test 3:
# `transcribe` with two languages dropped "बारह"). Never `transcribe` with more than one language.
STT_FOR = {"hi-en": ("hi-IN,en-IN", "codemix"), "te-IN": ("te-IN,en-IN", "codemix"), "en": ("en-IN", "transcribe")}
# Only what she actually sent reaches his page (GAP #10: drafts never play there)
SENT_STATUSES = ("sent", "played", "replied")

BADGE = {
    "hi-en": "{employer} ने {worker} का पूरा बकाया चुका दिया। Baaki की तरफ़ से Fair Employer।",
    "te-IN": "{employer} {worker} బాకీ మొత్తం చెల్లించారు. బాకీ యాప్ నుండి Fair Employer.",
    "en": "{employer} paid {worker} in full. A Fair Employer, by Baaki.",
}
BADGE_PATTA = {
    "hi-en": "{employer} ने {worker} के साथ Kaam Patta पर sign किया है। Baaki की तरफ़ से Fair Employer।",
    "te-IN": "{employer} {worker} తో కామ్ పట్టా పై సంతకం చేశారు. బాకీ యాప్ నుండి Fair Employer.",
    "en": "{employer} signed a Kaam Patta work agreement with {worker}. A Fair Employer, by Baaki.",
}
PLAN_NOTE = {
    "hi-en": "{employer} ने {n} किस्तों में देने का plan चुना है। पहली किस्त {amount}, {due} तक।",
    "te-IN": "{employer} {n} వాయిదాల్లో చెల్లించే ప్లాన్ ఎంచుకున్నారు. మొదటి వాయిదా {amount}, {due} లోపు.",
    "en": "{employer} chose to pay in {n} instalments. First instalment {amount}, due by {due}.",
}
STALE_NOTE = {
    "hi-en": "यह voice note {old} के हिसाब से बना था। अभी का बकाया {new} है।",
    "te-IN": "ఈ వాయిస్ నోట్ {old} లెక్కతో చేసింది. ఇప్పటి బాకీ {new}.",
    "en": "This voice note was made when {old} was due. The balance now is {new}.",
}


def _ctx_or_404(s, token: str) -> CaseCtx:
    ctx = load_ctx_by_token(s, token)
    if ctx is None:
        raise HTTPException(404, "link not found")
    return ctx


def _latest_to_employer(s, case_id: int) -> Message | None:
    return s.exec(select(Message).where(Message.case_id == case_id, Message.direction == "to_employer",
                                        Message.step.in_(("polite", "firm", "formal")),  # type: ignore[attr-defined]
                                        Message.status.in_(SENT_STATUSES))  # type: ignore[attr-defined]
                  .order_by(Message.id.desc())).first()


def public_message(view: dict[str, Any] | None) -> dict[str, Any] | None:
    """message_view() without the worker's case id (employer pages are keyed by the token only)."""
    if view is None:
        return None
    return {k: v for k, v in view.items() if k != "case_id"}


def badge(ctx: CaseCtx) -> dict[str, Any] | None:
    e = ctx.employer
    if not (e.fair_employer or e.kaam_patta_signed):
        return None
    lang = ctx.employer_lang
    reason = "paid_in_full" if ctx.balance <= 0 and ctx.total_due > 0 else (
        "kaam_patta" if e.kaam_patta_signed else "paid_in_full")
    tpl = BADGE if reason == "paid_in_full" else BADGE_PATTA
    kw = {"employer": name_in(e.name, lang), "worker": name_in(ctx.worker.name, lang)}
    kw_en = {"employer": e.name, "worker": ctx.worker.name}
    return {"title": "Fair Employer", "reason": reason, "employer": e.name, "text": tpl[lang].format(**kw),
            "text_en": tpl["en"].format(**kw_en), "share_text": tpl[lang].format(**kw) + " #FairEmployer"}


def _plan_view(ctx: CaseCtx) -> list[dict]:
    return [{"payment_id": p.id, "instalment_no": p.instalment_no, "instalments_total": p.instalments_total,
             "amount": p.amount, "due_date": p.due_date, "status": p.status}
            for p in ctx.payments if p.instalment_no and p.status != "cancelled"]


# --------------------------------------------------------------------------- claims ("I've paid")
def claims(s: Session, ctx: CaseCtx) -> list[tuple[HisaabProposal, HisaabClaim | None]]:
    """His "I've paid" claims on this case, newest first."""
    ps = list(s.exec(select(HisaabProposal).where(HisaabProposal.case_id == ctx.case.id,
                                                  HisaabProposal.case_token == ctx.case.employer_token,
                                                  HisaabProposal.kind == CLAIM_KIND)
                     .order_by(HisaabProposal.id.desc())))  # type: ignore[union-attr]
    out = []
    for p in ps:
        c = s.exec(select(HisaabClaim).where(HisaabClaim.proposal_id == p.id)).first()
        out.append((p, c))
    return out


def claim_view(p: HisaabProposal, c: HisaabClaim | None, ctx: CaseCtx) -> dict[str, Any]:
    """Employer-safe view of one claim (no case id)."""
    el = ctx.employer_lang
    worker = name_in(ctx.worker.name, el)
    return {"id": p.id, "amount": p.amount, "amount_display": fmt_money(p.amount),
            "method": c.method if c else "other", "status": p.status, "display_state": DISPLAY_STATE[p.status],
            "status_text": CLAIM_STATUS_EMPLOYER[p.status][el].format(worker=worker),
            "status_text_en": CLAIM_STATUS_EMPLOYER[p.status]["en"].format(worker=ctx.worker.name),
            "demo": bool(c and c.demo), "created_at": p.created_at, "decided_at": p.decided_at}


def create_claim(s: Session, ctx: CaseCtx, amount: float, method: str, note: Optional[str], *,
                 source: str = "employer_page", alert_audio: bool = True, demo: bool = False) -> tuple[HisaabProposal, HisaabClaim]:
    """Store "I've paid" as a proposal she must confirm. Records no money. Caller commits."""
    e, w = ctx.employer, ctx.worker
    rb = claim_readback(e.name, amount, method, ctx.worker_lang)
    p = HisaabProposal(case_id=ctx.case.id, case_token=ctx.case.employer_token, worker_id=w.id, employer_id=e.id,
                       amount=round(float(amount), 2), amount_source="typed", kind=CLAIM_KIND, month=None,
                       transcript=(note or "").strip(), source="tap", language=ctx.employer_lang,
                       worker_text=rb["text"], worker_speech=rb["speech"], worker_lang=rb["language"])
    s.add(p)
    s.flush()
    c = HisaabClaim(proposal_id=p.id, case_id=ctx.case.id, case_token=ctx.case.employer_token, method=method,
                    note=note, source=source, alert_audio=alert_audio, demo=demo)
    s.add(c)
    add_diary_entry(s, w.id, claim_diary_text("proposed", employer_name=e.name, worker_name=w.name, amount=p.amount,
                                              method=method, proposal_id=p.id),
                    employer_id=e.id, case_id=ctx.case.id, kind="note")
    s.flush()
    return p, c


async def send_paid_alert(case_id: int, amount: float, *, want_audio: bool) -> dict[str, Any] | None:
    """The "Paisa aa gaya" alert for her (excited, her language), written only after SHE confirmed the money.
    Read -> close the session -> Timbre (if wanted) -> short write session."""
    with db.session() as s:
        ctx = load_ctx(s, case_id)
        if ctx is None:
            return None
        token = ctx.case.employer_token
        t = ledger.paid_alert_texts(ctx.employer.name, ctx.worker_lang, amount, ctx.balance)
    alert_audio, alert_err, key, note_id = None, None, None, None
    if want_audio:
        try:
            note = await voice_note.make_voice_note([t["speech"]], tts_lang(t["language"]), purpose="payment alert")
            key, note_id = store(case_id, note.data, "ogg"), note.id
            alert_audio = {"url": media_url(key), "duration_s": note.duration_s, "voice": note.voice,
                           "voice_note_id": note.id, "gnani_calls": note.gnani_calls}
        except (GnaniError, audio.AudioError, ValueError) as ex:
            alert_err = gnani_error_dict(ex)
    with db.session() as s:
        ctx = load_ctx(s, case_id)
        if ctx is None or ctx.case.employer_token != token:
            return None
        m = Message(case_id=case_id, step="paid_alert", direction="to_worker", language=t["language"], text=t["text"],
                    audio_path=key, voice_note_id=note_id, status="sent", sent_at=db.now_iso())
        s.add(m)
        s.commit()
        s.refresh(m)
    return {"message_id": m.id, "text": t["text"], "speech": t["speech"], "language": t["language"],
            "audio": alert_audio, "audio_error": alert_err}


# --------------------------------------------------------------------------- page
@router.get("/{token}")
async def employer_page(token: str) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        lang = ctx.employer_lang
        m = _latest_to_employer(s, ctx.case.id)
        items = [{"id": i.id, "kind": i.kind, "label": item_label(i, lang), "label_en": item_label(i, "en"),
                  "month": i.month, "amount": i.amount, "amount_display": fmt_money(i.amount),
                  "due_date": i.due_date, "is_estimate": i.is_estimate, "included_in_total": i.included_in_total,
                  "source": i.source} for i in ctx.items]
        replies = [public_message(message_view(r)) for r in s.exec(select(Message).where(
            Message.case_id == ctx.case.id, Message.direction == "from_employer").order_by(Message.id))]
        st = ledger.staleness(s, m, ctx.case) if m else {"stale": False, "balance_at_make": None}
        msg = public_message(message_view(m)) if m else None
        if msg is not None:
            msg.update(st)
        cl = claims(s, ctx)
        pending = [claim_view(p, c, ctx) for p, c in cl if p.status == "proposed"]
        money = ledger.money_view(s, ctx.case)
        return {
            "status": ctx.case.status,
            "worker": {"name": ctx.worker.name, "language": ctx.worker_lang},
            "employer": {"name": ctx.employer.name, "language": lang, "fair_employer": ctx.employer.fair_employer},
            "items": items,
            "total_due": ctx.total_due,
            "amount_paid": ctx.paid,
            "balance": ctx.balance,
            "balance_display": fmt_money(ctx.balance),
            "overpaid": money["overpaid"],
            "currency": "INR",
            "message": msg,
            "stale": st["stale"],
            "stale_note": STALE_NOTE[lang].format(old=fmt_money(st["balance_at_make"]), new=fmt_money(ctx.balance))
            if st["stale"] else None,
            "audio_url": media_url(m.audio_path) if m else None,
            "pdf_url": media_url(m.pdf_path) if m else None,
            "upi": {"vpa": ctx.worker.upi_vpa, "link": upi_link(ctx.worker.upi_vpa, ctx.worker.name, ctx.balance)}
            if ctx.worker.upi_vpa and ctx.balance > 0 else None,
            "plan": _plan_view(ctx),
            "replies": replies,
            "claims": [claim_view(p, c, ctx) for p, c in cl],
            "pending_confirmation": bool(pending),
            "pending_claim": pending[0] if pending else None,
            "pending_claim_total": round(sum(x["amount"] for x in pending), 2),
            "badge": badge(ctx),
            "ai_notice": "The voice note is AI-generated by the Baaki app on behalf of the worker, with consent.",
        }


@router.post("/{token}/played")
async def played(token: str) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        m = _latest_to_employer(s, ctx.case.id)
        if m is not None and m.status == "sent":
            m.status = "played"
            s.add(m)
            s.commit()
        return {"ok": True, "message_id": m.id if m else None, "status": m.status if m else None}


class PayIn(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)     # default: the whole balance (less pending claims)
    method: Literal["upi", "cash", "bank", "other"] = "upi"
    note: Optional[str] = Field(default=None, max_length=300)
    alert_audio: bool = True                                 # make the "Paisa aa gaya" clip when she confirms


def _claim_response(ctx: CaseCtx, p: HisaabProposal, c: HisaabClaim | None, *, already: bool) -> dict:
    el = ctx.employer_lang
    return {
        "pending_confirmation": True, "already_claimed": already,
        "claim": claim_view(p, c, ctx), "claimed": p.amount, "claimed_display": fmt_money(p.amount),
        # nothing is recorded until she confirms
        "paid": 0.0, "paid_display": fmt_money(0), "amount_paid": ctx.paid, "balance": ctx.balance,
        "status": ctx.case.status, "fully_paid": False, "fair_employer": ctx.employer.fair_employer, "badge": None,
        "alert": None,
        "message": CLAIM_SENT[el].format(worker=name_in(ctx.worker.name, el)),
        "message_en": CLAIM_SENT["en"].format(worker=ctx.worker.name),
    }


@router.post("/{token}/pay")
async def pay(token: str, body: PayIn = Body(default_factory=PayIn)) -> dict:
    """"I've paid" -> a claim she confirms. A second tap while one is waiting returns that claim."""
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        bal = ctx.balance
        if bal <= 0:
            raise HTTPException(409, {"error": "nothing_due", "message": "already paid in full"})
        pending = [(p, c) for p, c in claims(s, ctx) if p.status == "proposed"]
        avail = round(bal - sum(p.amount for p, _ in pending), 2)
        if pending and avail <= ledger.TOL:
            p, c = pending[0]
            return _claim_response(ctx, p, c, already=True)
        amount = round(float(body.amount if body.amount is not None else avail), 2)
        if amount > avail + ledger.TOL:
            extra = f" ({fmt_money(bal - avail)} is already waiting for her to confirm)" if pending else ""
            raise HTTPException(400, {"error": "too_much", "message": f"balance is {fmt_money(bal)}{extra}"})
        amount = min(amount, avail)
        p, c = create_claim(s, ctx, amount, body.method, body.note, alert_audio=body.alert_audio)
        s.commit()
        s.refresh(p)
        return _claim_response(ctx, p, c, already=False)


class PlanIn(BaseModel):
    instalments: int = Field(..., ge=2, le=3)
    first_due: Optional[str] = None     # ISO date; default 7 days from today
    every_days: int = Field(default=30, ge=7, le=45)


@router.post("/{token}/plan")
async def plan(token: str, body: PlanIn) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        bal = ctx.balance
        if bal <= 0:
            raise HTTPException(409, {"error": "nothing_due", "message": "already paid in full"})
        try:
            first = dt.date.fromisoformat(body.first_due) if body.first_due else today_ist() + dt.timedelta(days=7)
        except ValueError:
            raise HTTPException(400, "first_due must be an ISO date")
        if first < today_ist():
            raise HTTPException(400, "first_due is in the past")
        _, out = ledger.create_plan(s, ctx.case, instalments=body.instalments, first_due=first,
                                    every_days=body.every_days, worker=ctx.worker, employer=ctx.employer)
        ledger.reconcile(s, ctx.case)
        wl = ctx.worker_lang
        parts = [p.amount for p, _ in out]
        note = Message(case_id=ctx.case.id, step="plan", direction="to_worker", language=wl, status="sent",
                       sent_at=db.now_iso(),
                       text=PLAN_NOTE[wl].format(employer=name_in(ctx.employer.name, wl), n=body.instalments,
                                                 amount=fmt_money(parts[0]), due=fmt_date(first, wl)))
        s.add(note)
        s.commit()
        return {
            "status": "plan", "balance": bal, "instalments": [
                {"payment_id": p.id, "instalment_no": p.instalment_no, "amount": p.amount,
                 "amount_display": fmt_money(p.amount), "due_date": p.due_date, "status": p.status,
                 "reminder": {"message_id": r.id, "text": r.text, "send_on": p.due_date, "status": r.status},
                 "upi_link": upi_link(ctx.worker.upi_vpa, ctx.worker.name, p.amount)} for p, r in out],
            "total_check": round(sum(parts), 2) == round(bal, 2),
            "worker_note": {"message_id": note.id, "text": note.text},
        }


@router.post("/{token}/reply")
async def reply(token: str, audio_file: Optional[UploadFile] = File(None, alias="audio"), text: str = Form(""),
                lang: Optional[str] = Form(None), use_llm: bool = Form(True)) -> dict:
    """Employer speaks (Hinglish or Telugu) or types -> Prisma (voice only) -> translation (amounts checked) ->
    Timbre in the worker's language (stock voice; the employer's voice is never cloned)."""
    data, ext = None, None
    if audio_file is not None and (audio_file.filename or audio_file.content_type):
        name = audio_file.filename or "reply"
        ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
        if ext not in ACCEPTED_AUDIO:
            raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
        data = await audio_file.read()
        if not data:
            raise HTTPException(400, "empty audio")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "audio larger than 25 MB")
    typed = (text or "").strip()
    if len(typed) > MAX_REPLY_TEXT:
        raise HTTPException(400, f"text longer than {MAX_REPLY_TEXT} characters")
    if data is None and not typed:
        raise HTTPException(400, {"error": "empty", "message": "record a voice reply or type it"})
    with db.session() as s:   # read only; closed before any Gnani / translate work
        ctx = _ctx_or_404(s, token)
        src = norm_lang(lang or ctx.employer.language)
        wl, case_id, case_token, employer_name = ctx.worker_lang, ctx.case.id, ctx.case.employer_token, ctx.employer.name
    stt: dict[str, Any] = {}
    if data is not None:
        codes, mode = STT_FOR[src]
        try:
            stt = await transcribe_upload(data, f"reply.{ext}", lang=codes, mode=mode)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except audio.AudioError as e:
            raise HTTPException(415, f"could not decode audio: {e}")
        except GnaniError as e:
            raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
        heard = (stt.get("transcript") or "").strip()
        if not heard and not typed:
            raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please record again"})
        transcript = (heard + (" " + typed if typed and typed != heard else "")).strip()
    else:
        transcript = typed
    chips = [{"value": a["amount_inr"], "text": a["source_text"], "start": a["start"], "end": a["end"]}
             for a in extract_amounts(transcript, parse_lang(src))]
    tr = await translate(transcript, src, wl, speaker=employer_name, use_llm=use_llm)
    orig_key = store(case_id, data, ext) if data is not None else None   # his own reply, kept as the record
    audio_info, audio_err, key = None, None, None
    try:
        # one Timbre call for the short translated reply (stock voice)
        note = await voice_note.make_voice_note([" ".join(tr.speech)], tts_lang(wl), purpose="reply translation")
        key = store(case_id, note.data, "ogg")
        audio_info = {"url": media_url(key), "duration_s": note.duration_s, "voice": note.voice,
                      "voice_note_id": note.id, "gnani_calls": note.gnani_calls, "cache_hits": note.cache_hits}
    except (GnaniError, audio.AudioError, ValueError) as ex:
        audio_err = gnani_error_dict(ex)
    with db.session() as s:   # short write
        ctx = load_ctx_by_token(s, token)
        if ctx is None or ctx.case.id != case_id or ctx.case.employer_token != case_token:
            raise HTTPException(404, "link not found")
        now = db.now_iso()
        m_in = Message(case_id=case_id, step="reply", direction="from_employer", language=src, text=transcript,
                       text_worker_lang=tr.text, audio_path=orig_key, status="replied", sent_at=now)
        m_out = Message(case_id=case_id, step="reply", direction="to_worker", language=wl, text=tr.text,
                        audio_path=key, voice_note_id=audio_info["voice_note_id"] if audio_info else None,
                        status="sent", sent_at=now)
        last = _latest_to_employer(s, case_id)
        if last is not None:
            last.status = "replied"
            s.add(last)
        s.add(m_in)
        s.add(m_out)
        s.commit()
        s.refresh(m_in)
        s.refresh(m_out)
    return {
        "transcript": transcript, "language": src, "source": "voice" if data is not None else "text",
        "stt": {"language_code": stt.get("language_code"), "mode": stt.get("mode"), "duration_s": stt.get("duration_s")},
        "amounts": chips,
        "translation": {"text": tr.text, "language": wl, "source": tr.source, "speech": tr.speech,
                        "amounts": tr.amounts, "checks": tr.checks},
        "audio": audio_info, "audio_error": audio_err,
        "original_audio_url": media_url(orig_key),
        "message_ids": {"from_employer": m_in.id, "to_worker": m_out.id},
        "employer_url": employer_url(case_token),
    }
