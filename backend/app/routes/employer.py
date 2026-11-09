"""The employer's page (opened from the link in the voice note): see, pay, pay in parts, reply.

  GET  /api/e/{token}          itemised baaki, voice-note audio, UPI deep link, plan, badge
  POST /api/e/{token}/played   the employer played the voice note
  POST /api/e/{token}/pay      marks paid -> "Paisa aa gaya" (<excited>, worker's language) + Fair Employer badge
  POST /api/e/{token}/plan     2 or 3 instalments -> planned payments + reminders
  POST /api/e/{token}/reply    employer voice (Hinglish / Telugu) -> Prisma -> translation -> Timbre for the worker
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import select

from .. import audio, db, voice_note
from ..gnani import GnaniError
from ..lang import extract_amounts, today_ist
from ..messages import (CaseCtx, employer_url, fmt_date, fmt_money, item_label, load_ctx_by_token, money_words,
                        name_in, norm_lang, parse_lang, tts_lang, upi_link)
from ..models import Employer, Message, Payment
from ..stt_service import transcribe_upload
from ..translate import translate
from .letters import gnani_error_dict, media_url, message_view, store

log = logging.getLogger("employer")
router = APIRouter(prefix="/api/e", tags=["employer"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ACCEPTED_AUDIO = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}
# Prisma settings for the employer's reply. Hinglish: hi-IN,en-IN + codemix (feasibility test 3:
# `transcribe` with two languages dropped "बारह"). Never `transcribe` with more than one language.
STT_FOR = {"hi-en": ("hi-IN,en-IN", "codemix"), "te-IN": ("te-IN,en-IN", "codemix"), "en": ("en-IN", "transcribe")}

PAID_ALERT = {
    "hi-en": ("<excited> पैसा आ गया! {employer} ने {amount} भेज दिए, पूरा हिसाब हो गया।",
              "<excited> पैसा आ गया! {employer} ने {amount} भेज दिए, अभी {balance} बाकी हैं।"),
    "te-IN": ("<excited> డబ్బులు వచ్చేశాయి! {employer} {amount} పంపించారు, మొత్తం లెక్క పూర్తయింది.",
              "<excited> డబ్బులు వచ్చేశాయి! {employer} {amount} పంపించారు, ఇంకా {balance} బాకీ ఉంది."),
    "en": ("<excited> The money has arrived! {employer} sent {amount}, and everything is settled.",
           "<excited> The money has arrived! {employer} sent {amount}; {balance} is still due."),
}
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
REMINDER = {
    "hi-en": "याद दिलाना: {worker} की किस्त {i}/{n}, {amount}, {due} तक।",
    "te-IN": "గుర్తు: {worker} వాయిదా {i}/{n}, {amount}, {due} లోపు.",
    "en": "Reminder: instalment {i} of {n} for {worker}, {amount}, due by {due}.",
}
PLAN_NOTE = {
    "hi-en": "{employer} ने {n} किस्तों में देने का plan चुना है। पहली किस्त {amount}, {due} तक।",
    "te-IN": "{employer} {n} వాయిదాల్లో చెల్లించే ప్లాన్ ఎంచుకున్నారు. మొదటి వాయిదా {amount}, {due} లోపు.",
    "en": "{employer} chose to pay in {n} instalments. First instalment {amount}, due by {due}.",
}


def _ctx_or_404(s, token: str) -> CaseCtx:
    ctx = load_ctx_by_token(s, token)
    if ctx is None:
        raise HTTPException(404, "link not found")
    return ctx


def _latest_to_employer(s, case_id: int) -> Message | None:
    return s.exec(select(Message).where(Message.case_id == case_id, Message.direction == "to_employer",
                                        Message.step.in_(("polite", "firm", "formal")))
                  .order_by(Message.id.desc())).first()


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
            for p in ctx.payments if p.instalment_no]


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
        replies = [message_view(r) for r in s.exec(select(Message).where(
            Message.case_id == ctx.case.id, Message.direction == "from_employer").order_by(Message.id))]
        return {
            "case_id": ctx.case.id,
            "status": ctx.case.status,
            "worker": {"name": ctx.worker.name, "language": ctx.worker_lang},
            "employer": {"name": ctx.employer.name, "language": lang, "fair_employer": ctx.employer.fair_employer},
            "items": items,
            "total_due": ctx.total_due,
            "amount_paid": ctx.paid,
            "balance": ctx.balance,
            "balance_display": fmt_money(ctx.balance),
            "currency": "INR",
            "message": message_view(m) if m else None,
            "audio_url": media_url(m.audio_path) if m else None,
            "pdf_url": media_url(m.pdf_path) if m else None,
            "upi": {"vpa": ctx.worker.upi_vpa, "link": upi_link(ctx.worker.upi_vpa, ctx.worker.name, ctx.balance)}
            if ctx.worker.upi_vpa and ctx.balance > 0 else None,
            "plan": _plan_view(ctx),
            "replies": replies,
            "badge": badge(ctx),
            "ai_notice": "The voice note is AI-generated by the Baaki app on behalf of the worker, with consent.",
        }


@router.post("/{token}/played")
async def played(token: str) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        m = _latest_to_employer(s, ctx.case.id)
        if m is not None and m.status in ("draft", "sent"):
            m.status = "played"
            s.add(m)
            s.commit()
        return {"ok": True, "message_id": m.id if m else None, "status": m.status if m else None}


class PayIn(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)     # default: the whole balance
    method: Literal["upi", "cash", "bank", "other"] = "upi"
    note: Optional[str] = Field(default=None, max_length=300)
    alert_audio: bool = True


@router.post("/{token}/pay")
async def pay(token: str, body: PayIn = Body(default_factory=PayIn)) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        bal = ctx.balance
        if bal <= 0:
            raise HTTPException(409, {"error": "nothing_due", "message": "already paid in full"})
        amount = round(float(body.amount if body.amount is not None else bal), 2)
        if amount > bal + 0.5:
            raise HTTPException(400, {"error": "too_much", "message": f"balance is {fmt_money(bal)}"})
        amount = min(amount, bal)
        now = db.now_iso()
        s.add(Payment(case_id=ctx.case.id, amount=amount, method=body.method, status="paid", paid_at=now,
                      note=body.note))
        c = ctx.case
        c.amount_paid = round(float(c.amount_paid or 0) + amount, 2)
        c.updated_at = now
        # instalments covered by everything paid so far are settled
        covered = c.amount_paid
        for p in sorted([p for p in ctx.payments if p.instalment_no], key=lambda p: p.instalment_no or 0):
            covered -= p.amount
            if covered >= -0.5 and p.status == "planned":
                p.status = "settled"
                s.add(p)
        full = c.balance <= 0.5
        e: Employer = ctx.employer
        if full:
            c.status = "paid"
            e.fair_employer = True
            s.add(e)
        s.add(c)
        s.commit()
        s.refresh(c)

        wl = ctx.worker_lang
        tpl = PAID_ALERT[wl][0 if full else 1]
        kw_s = {"employer": name_in(e.name, wl), "amount": money_words(amount, wl), "balance": money_words(c.balance, wl)}
        kw_d = {"employer": name_in(e.name, wl), "amount": fmt_money(amount), "balance": fmt_money(c.balance)}
        speech = tpl.format(**kw_s)
        display = tpl.replace("<excited> ", "").format(**kw_d)
        alert_audio, alert_err, key, note_id = None, None, None, None
        if body.alert_audio:
            try:
                note = await voice_note.make_voice_note([speech], tts_lang(wl), purpose="payment alert")
                key, note_id = store(c.id, note.data, "ogg"), note.id
                alert_audio = {"url": media_url(key), "duration_s": note.duration_s, "voice": note.voice,
                               "voice_note_id": note.id, "gnani_calls": note.gnani_calls}
            except (GnaniError, audio.AudioError, ValueError) as ex:
                alert_err = gnani_error_dict(ex)
        m = Message(case_id=c.id, step="paid_alert", direction="to_worker", language=wl, text=display,
                    audio_path=key, voice_note_id=note_id, status="sent", sent_at=now)
        s.add(m)
        s.commit()
        s.refresh(m)
        ctx.case = c
        return {"paid": amount, "paid_display": fmt_money(amount), "amount_paid": c.amount_paid,
                "balance": c.balance, "status": c.status, "fully_paid": full,
                "fair_employer": e.fair_employer, "badge": badge(ctx) if full else None,
                "alert": {"message_id": m.id, "text": display, "speech": speech, "language": wl,
                          "audio": alert_audio, "audio_error": alert_err}}


class PlanIn(BaseModel):
    instalments: int = Field(..., ge=2, le=3)
    first_due: Optional[str] = None     # ISO date; default 7 days from today
    every_days: int = Field(default=30, ge=7, le=45)


def split_amount(total: float, n: int) -> list[float]:
    """Whole-rupee instalments that add up exactly; any remainder (and paise) goes on the first."""
    whole = int(total)
    base = whole // n
    parts = [float(base)] * n
    parts[0] = round(total - base * (n - 1), 2)
    return parts


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
        for p in ctx.payments:  # a new plan replaces the old one
            if p.instalment_no and p.status == "planned":
                s.delete(p)
        for m in s.exec(select(Message).where(Message.case_id == ctx.case.id, Message.step == "reminder",
                                              Message.status == "scheduled")):
            s.delete(m)
        parts = split_amount(bal, body.instalments)
        el, wl = ctx.employer_lang, ctx.worker_lang
        out = []
        for i, amt in enumerate(parts, 1):
            due = first + dt.timedelta(days=body.every_days * (i - 1))
            p = Payment(case_id=ctx.case.id, amount=amt, method="upi", status="planned", due_date=due.isoformat(),
                        instalment_no=i, instalments_total=body.instalments)
            s.add(p)
            r = Message(case_id=ctx.case.id, step="reminder", direction="to_employer", language=el, status="scheduled",
                        text=REMINDER[el].format(worker=name_in(ctx.worker.name, el), i=i, n=body.instalments,
                                                 amount=fmt_money(amt), due=fmt_date(due, el)),
                        text_worker_lang=REMINDER[wl].format(worker=name_in(ctx.worker.name, wl), i=i, n=body.instalments,
                                                             amount=fmt_money(amt), due=fmt_date(due, wl)))
            s.add(r)
            out.append((p, r))
        ctx.case.status, ctx.case.updated_at = "plan", db.now_iso()
        s.add(ctx.case)
        note = Message(case_id=ctx.case.id, step="plan", direction="to_worker", language=wl, status="sent",
                       sent_at=db.now_iso(),
                       text=PLAN_NOTE[wl].format(employer=name_in(ctx.employer.name, wl), n=body.instalments,
                                                 amount=fmt_money(parts[0]), due=fmt_date(first, wl)))
        s.add(note)
        s.commit()
        return {
            "case_id": ctx.case.id, "status": "plan", "balance": bal, "instalments": [
                {"payment_id": p.id, "instalment_no": p.instalment_no, "amount": p.amount,
                 "amount_display": fmt_money(p.amount), "due_date": p.due_date, "status": p.status,
                 "reminder": {"message_id": r.id, "text": r.text, "send_on": p.due_date, "status": r.status},
                 "upi_link": upi_link(ctx.worker.upi_vpa, ctx.worker.name, p.amount)} for p, r in out],
            "total_check": round(sum(parts), 2) == round(bal, 2),
            "worker_note": {"message_id": note.id, "text": note.text},
        }


@router.post("/{token}/reply")
async def reply(token: str, audio_file: UploadFile = File(..., alias="audio"), lang: Optional[str] = Form(None),
                use_llm: bool = Form(True)) -> dict:
    """Employer speaks (Hinglish or Telugu) -> Prisma -> translation (amounts checked) -> Timbre in the
    worker's language (stock voice; the employer's voice is never cloned)."""
    name = audio_file.filename or "reply"
    ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
    if ext not in ACCEPTED_AUDIO:
        raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
    data = await audio_file.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "audio larger than 25 MB")
    with db.session() as s:
        ctx = _ctx_or_404(s, token)
        src = norm_lang(lang or ctx.employer.language)
        codes, mode = STT_FOR[src]
        try:
            stt = await transcribe_upload(data, f"reply.{ext}", lang=codes, mode=mode)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except audio.AudioError as e:
            raise HTTPException(415, f"could not decode audio: {e}")
        except GnaniError as e:
            raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
        transcript = (stt.get("transcript") or "").strip()
        if not transcript:
            raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please record again"})
        chips = [{"value": a["amount_inr"], "text": a["source_text"], "start": a["start"], "end": a["end"]}
                 for a in extract_amounts(transcript, parse_lang(src))]
        wl = ctx.worker_lang
        tr = await translate(transcript, src, wl, speaker=ctx.employer.name, use_llm=use_llm)
        orig_key = store(ctx.case.id, data, ext)   # the employer's own reply, kept as the record
        audio_info, audio_err, key = None, None, None
        try:
            # one Timbre call for the short translated reply (stock Timbre pauses at full stops by itself;
            # one-sentence-per-call is needed for the cloned voice, which is never used here)
            note = await voice_note.make_voice_note([" ".join(tr.speech)], tts_lang(wl), purpose="reply translation")
            key = store(ctx.case.id, note.data, "ogg")
            audio_info = {"url": media_url(key), "duration_s": note.duration_s, "voice": note.voice,
                          "voice_note_id": note.id, "gnani_calls": note.gnani_calls, "cache_hits": note.cache_hits}
        except (GnaniError, audio.AudioError, ValueError) as ex:
            audio_err = gnani_error_dict(ex)
        now = db.now_iso()
        m_in = Message(case_id=ctx.case.id, step="reply", direction="from_employer", language=src, text=transcript,
                       text_worker_lang=tr.text, audio_path=orig_key, status="replied", sent_at=now)
        m_out = Message(case_id=ctx.case.id, step="reply", direction="to_worker", language=wl, text=tr.text,
                        audio_path=key, voice_note_id=audio_info["voice_note_id"] if audio_info else None,
                        status="sent", sent_at=now)
        last = _latest_to_employer(s, ctx.case.id)
        if last is not None:
            last.status = "replied"
            s.add(last)
        s.add(m_in)
        s.add(m_out)
        s.commit()
        s.refresh(m_in)
        s.refresh(m_out)
        return {
            "transcript": transcript, "language": src, "stt": {"language_code": stt.get("language_code"),
                                                                "mode": stt.get("mode"),
                                                                "duration_s": stt.get("duration_s")},
            "amounts": chips,
            "translation": {"text": tr.text, "language": wl, "source": tr.source, "speech": tr.speech,
                            "amounts": tr.amounts, "checks": tr.checks},
            "audio": audio_info, "audio_error": audio_err,
            "original_audio_url": media_url(orig_key),
            "message_ids": {"from_employer": m_in.id, "to_worker": m_out.id},
            "employer_url": employer_url(ctx.case.employer_token),
        }
