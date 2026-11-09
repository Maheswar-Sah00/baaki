"""Share to Baaki + Promise Keeper (W04+G16+W05). Owned by the tournament feature agent for this module.

The employer replies on WhatsApp, not on the Baaki page. The worker forwards / uploads that voice note
(or pastes the text) into Baaki for one case:

  POST /api/inbox/{case_id}                    multipart: audio (file) | text, lang?, said_on?, use_llm?, speak?
       -> Prisma (Hinglish / Telugu codemix, or auto) -> translation into her language (amounts checked)
       -> Timbre read-out + promise read-back -> promise (app.lang amount + dates.py date)
       -> hash-chained evidence card (a DiaryEntry kind="evidence" in her existing diary chain)
  GET  /api/inbox/{case_id}?as_of=YYYY-MM-DD   cards + promises with status (pending / passed / kept / broken)
  POST /api/inbox/promises/{id}/remind         gentle reminder in the employer's language quoting their words
  POST /api/inbox/promises/{id}/status         kept | broken | pending, confirm the read-back, fix date / amount

Nothing is ever sent from here: the worker shares the reminder herself (Web Share / WhatsApp link).
The employer's audio stays private to her case (DPDP s.17(1)(a), our reading).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Literal, Optional
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audio, clock, db, voice_note
from ..gnani import GnaniError
from ..inbox_logic import (detect_lang, effective_status, evidence_text, extract_past_payments, extract_promises,
                           readback_speech, reminder, summary)
from ..inbox_models import InboxCard, InboxPromise
from ..lang import extract_amounts
from ..messages import (CaseCtx, employer_url, fmt_date, fmt_money, load_ctx, name_in, norm_lang, parse_lang,
                        tts_lang)
from ..models import DiaryEntry, Payment
from ..stt_service import transcribe_upload
from ..translate import translate
from .cases import add_diary_entry, entry_hash, verify_chain
from .employer import ACCEPTED_AUDIO, MAX_UPLOAD_BYTES, STT_FOR
from .letters import gnani_error_dict, media_url, store

log = logging.getLogger("inbox")
router = APIRouter(prefix="/api/inbox", tags=["inbox"])

MAX_TEXT = 4000
AUTO_STT = ("te-IN,hi-IN,en-IN", "codemix")   # unknown language: Prisma picks; we read the script afterwards
_DEFAULT_LANG = (None, "", "employer")
_AUTO_LANG = ("auto", "indic-auto", "unknown")


def _today() -> dt.date:
    return clock.today()


def _ctx(s: Session, case_id: int) -> CaseCtx:
    ctx = load_ctx(s, case_id)
    if ctx is None or ctx.worker is None or ctx.employer is None:
        raise HTTPException(404, "case not found")
    return ctx


def _as_of(as_of: Optional[str]) -> dt.date:
    if not as_of:
        return _today()
    try:
        return dt.date.fromisoformat(as_of[:10])
    except ValueError:
        raise HTTPException(400, "as_of must be an ISO date")


def _auto_kept(s: Session, p: InboxPromise, balance: float) -> bool:
    """Kept without a tap: the case is fully paid, or payments since the promise cover the promised amount."""
    if balance <= 0:
        return True
    if p.amount is None:
        return False
    paid = s.exec(select(Payment).where(Payment.case_id == p.case_id, Payment.status == "paid")).all()
    since = sum(float(x.amount) for x in paid if (x.paid_at or x.created_at or "") >= p.created_at)
    return since + 0.5 >= float(p.amount)


def promise_view(s: Session, p: InboxPromise, as_of: dt.date, balance: float, worker_lang: str) -> dict[str, Any]:
    auto = _auto_kept(s, p, balance) if p.status == "pending" else False
    status = effective_status(p.status, p.due_date, as_of, auto)
    return {"id": p.id, "card_id": p.card_id, "case_id": p.case_id, "amount": p.amount,
            "amount_display": fmt_money(p.amount) if p.amount is not None else None, "is_rest": p.is_rest,
            "due_date": p.due_date, "due_display": fmt_date(p.due_date, worker_lang, year=False),
            "range_start": p.range_start, "precision": p.precision, "phrase": p.phrase, "quote": p.quote,
            "confidence": p.confidence, "confirmed": p.confirmed, "edited": p.edited,
            "status": status, "stored_status": p.status, "status_at": p.status_at, "reminded_at": p.reminded_at,
            "can_remind": status == "passed"}


PAST_PAID_LINE = {
    "te-IN": ("{employer} {date} న {amount} ఇచ్చామని చెప్పారు. మీకు అందిందా?",
              "{employer} {amount} ఇచ్చామని చెప్పారు. మీకు అందిందా?",
              "{employer} {date} న డబ్బు ఇచ్చామని చెప్పారు. మీకు అందిందా?"),
    "hi-en": ("{employer} कहते हैं {date} को {amount} दिए थे। क्या आपको मिले?",
              "{employer} कहते हैं {amount} दिए थे। क्या आपको मिले?",
              "{employer} कहते हैं {date} को पैसे दिए थे। क्या आपको मिले?"),
    "en": ("{employer} says {amount} was paid on {date}. Did it reach you?",
           "{employer} says {amount} was paid. Did it reach you?",
           "{employer} says money was paid on {date}. Did it reach you?"),
}


def past_payments_view(c: InboxCard, ctx: CaseCtx) -> list[dict[str, Any]]:
    """Payments the employer SAYS he already made ("5 November ko 2000 diya tha"), for her to check. Read-only:
    nothing is recorded; only her confirmation through Hisaab could ever record money."""
    try:
        said = dt.date.fromisoformat((c.said_on or "")[:10])
    except ValueError:
        return []
    wl = norm_lang(ctx.worker_lang)
    wl = wl if wl in PAST_PAID_LINE else "en"
    emp = name_in(ctx.employer.name, wl)
    out = []
    for x in extract_past_payments(c.transcript, c.language_code, said):
        amount = fmt_money(x["amount"]) if x.get("amount") else None
        date = fmt_date(x["paid_on"], wl, year=False) if x.get("paid_on") else None
        both, amount_only, date_only = PAST_PAID_LINE[wl]
        line = (both if amount and date else amount_only if amount else date_only).format(
            employer=emp, amount=amount, date=date)
        out.append({"amount": x.get("amount"), "amount_display": amount, "paid_on": x.get("paid_on"),
                    "text": x.get("quote", ""), "line": line, "line_lang": wl, "recorded": False})
    return out


def card_view(s: Session, c: InboxCard, ctx: CaseCtx, as_of: dt.date) -> dict[str, Any]:
    ps = s.exec(select(InboxPromise).where(InboxPromise.card_id == c.id).order_by(InboxPromise.due_date)).all()
    pv = [promise_view(s, p, as_of, ctx.balance, ctx.worker_lang) for p in ps]
    prim = pv[0] if pv else None
    wl = ctx.worker_lang
    return {
        "id": c.id, "case_id": c.case_id, "source": c.source, "language_code": c.language_code,
        "stt": {"language_code": c.stt_language_code, "detected_language_code": c.detected_language_code,
                "mode": c.stt_mode},
        "transcript": c.transcript, "translation": c.translation, "translation_lang": c.translation_lang,
        "translation_source": c.translation_source, "amounts": json.loads(c.amounts_json or "[]"),
        "said_on": c.said_on, "audio_url": media_url(c.audio_path), "original_audio_url": media_url(c.original_audio_path),
        "summary": {"text": summary(ctx.employer.name, c.said_on, prim, wl), "language": wl,
                    "text_en": summary(ctx.employer.name, c.said_on, prim, "en")},
        "promise": prim, "promises": pv,
        "past_payments": past_payments_view(c, ctx),
        "card": {"id": c.id, "hash": c.hash, "prev_hash": c.prev_hash, "at": c.created_at,
                 "diary_entry_id": c.diary_entry_id},
    }


def card_chain_ok(s: Session, c: InboxCard) -> bool:
    """The card's hash is its diary entry's hash, and that entry still hashes to itself."""
    e = s.get(DiaryEntry, c.diary_entry_id) if c.diary_entry_id else None
    return bool(e and e.hash == c.hash and e.prev_hash == c.prev_hash and entry_hash(e.prev_hash, e) == e.hash)


async def _read_upload(upload: UploadFile) -> tuple[bytes, str]:
    name = upload.filename or "reply"
    ext = audio.ext_of(name) or audio.ext_of("x." + (upload.content_type or "").split("/")[-1].split(";")[0])
    if ext not in ACCEPTED_AUDIO:
        raise HTTPException(415, f"unsupported audio type '{ext or upload.content_type}'")
    data = await upload.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "audio larger than 25 MB")
    if ext == "opus":   # WhatsApp voice notes are Ogg/Opus named .opus; Prisma reads the format from the name
        ext = "ogg"
    return data, ext


# ------------------------------------------------------------------ POST /api/inbox/{case_id}
@router.post("/{case_id}")
async def add_reply(case_id: int, audio_file: Optional[UploadFile] = File(None, alias="audio"),
                    text: str = Form(""), lang: Optional[str] = Form(None), said_on: Optional[str] = Form(None),
                    use_llm: bool = Form(True), speak: bool = Form(True)) -> dict:
    """A forwarded WhatsApp reply (voice note or pasted text) -> transcript, translation, read-out, promise, card."""
    text = (text or "").strip()
    if audio_file is None and not text:
        raise HTTPException(400, "send a voice note (audio) or paste the text")
    if len(text) > MAX_TEXT:
        raise HTTPException(413, f"text longer than {MAX_TEXT} characters")
    try:
        said = dt.date.fromisoformat(said_on[:10]) if said_on else _today()
    except ValueError:
        raise HTTPException(400, "said_on must be an ISO date")
    if said > _today():
        raise HTTPException(400, "said_on is in the future")
    lang_in = (lang or "").strip().lower() or None

    data: bytes | None = None
    ext = ""
    if audio_file is not None:
        data, ext = await _read_upload(audio_file)
    content_sha = db.sha256_hex(data if data is not None else text.encode("utf-8"))

    def _duplicate(s: Session) -> Optional[dict]:
        """The same note shared twice FOR THIS CASE: the card already made (no new credits, no second chain entry).
        Scoped to the case: the same clip forwarded into another case is new evidence there."""
        dup = s.exec(select(InboxCard).where(InboxCard.case_id == case_id, InboxCard.content_sha256 == content_sha)).first()
        if dup is None:
            return None
        out = card_view(s, dup, _ctx(s, case_id), _today())
        out.update({"duplicate": True, "audio": None, "audio_error": None})
        return out

    # 1. short read: the case context and the duplicate check. No session is held during Gnani / LLM work
    #    (a session per waiting upload exhausted the pool and blocked every other request).
    with db.session() as s:
        ctx = _ctx(s, case_id)
        dup_view = _duplicate(s)
    if dup_view is not None:
        return dup_view
    employer_lang, wl = ctx.employer_lang, ctx.worker_lang
    employer_name, worker_id, employer_id = ctx.employer.name, ctx.worker.id, ctx.employer.id

    # 2. the slow part, no database connection: STT -> translation -> Timbre read-out
    stt_info: dict[str, Any] = {"language_code": None, "detected_language_code": None, "mode": None}
    if data is not None:
        if lang_in in _DEFAULT_LANG:
            codes, mode = STT_FOR[employer_lang]
        elif lang_in in _AUTO_LANG:
            codes, mode = AUTO_STT
        else:
            codes, mode = STT_FOR[norm_lang(lang_in)]
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
            raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please try another clip"})
        stt_info = {"language_code": stt.get("language_code"),
                    "detected_language_code": stt.get("detected_language_code"), "mode": stt.get("mode")}
        fallback = employer_lang if lang_in in _DEFAULT_LANG + _AUTO_LANG else norm_lang(lang_in)
        src = detect_lang(transcript, stt.get("detected_language_code"), fallback)
        source = "audio"
    else:
        transcript = text
        src = detect_lang(text, None, employer_lang) if lang_in in _DEFAULT_LANG + _AUTO_LANG else norm_lang(lang_in)
        source = "text"

    amounts = [{"value": a["amount_inr"], "text": a["source_text"], "start": a["start"], "end": a["end"]}
               for a in extract_amounts(transcript, parse_lang(src))]
    promises = extract_promises(transcript, src, said)
    tr = await translate(transcript, src, wl, speaker=employer_name, use_llm=use_llm)

    orig_key = store(case_id, data, ext) if data is not None else None
    audio_key, audio_err, audio_info = None, None, None
    if speak:
        sentence = " ".join([*tr.speech, *readback_speech(promises, wl)])
        try:
            # one Timbre call: translation + promise read-back (stock voice; the employer's voice is never cloned)
            note = await voice_note.make_voice_note([sentence], tts_lang(wl), purpose="reply translation")
            audio_key = store(case_id, note.data, "ogg")
            audio_info = {"duration_s": note.duration_s, "voice": note.voice, "voice_note_id": note.id,
                          "gnani_calls": note.gnani_calls, "cache_hits": note.cache_hits}
        except (GnaniError, audio.AudioError, ValueError) as ex:
            audio_err = gnani_error_dict(ex)

    # 3. short write (no awaits inside, so the chain append cannot interleave with another request's)
    with db.session() as s:
        dup_view = _duplicate(s)  # the same clip may have landed while this one was in STT
        if dup_view is not None:
            return dup_view
        ctx = _ctx(s, case_id)
        entry = add_diary_entry(s, worker_id,
                                evidence_text(employer_name, said.isoformat(), source, transcript, promises),
                                employer_id=employer_id, case_id=case_id, kind="evidence",
                                audio_sha256=db.sha256_hex(data) if data is not None else None)
        card = InboxCard(case_id=case_id, worker_id=worker_id, employer_id=employer_id, source=source,
                         language_code=src, stt_language_code=stt_info["language_code"],
                         detected_language_code=stt_info["detected_language_code"], stt_mode=stt_info["mode"],
                         transcript=transcript, translation=tr.text, translation_lang=wl, translation_source=tr.source,
                         amounts_json=json.dumps(amounts, ensure_ascii=False), said_on=said.isoformat(),
                         original_audio_path=orig_key, audio_path=audio_key, content_sha256=content_sha,
                         diary_entry_id=entry.id, prev_hash=entry.prev_hash, hash=entry.hash, created_at=entry.timestamp)
        s.add(card)
        s.flush()
        for p in promises:
            s.add(InboxPromise(card_id=card.id, case_id=case_id, amount=p["amount"], is_rest=p["is_rest"],
                               due_date=p["due_date"], range_start=p["range_start"], precision=p["precision"],
                               phrase=p["phrase"], quote=p["quote"], confidence=p["confidence"],
                               created_at=entry.timestamp))
        s.commit()
        s.refresh(card)
        out = card_view(s, card, ctx, _today())
        out.update({"duplicate": False, "audio": audio_info, "audio_error": audio_err,
                    "translation_checks": tr.checks})
        return out


# ------------------------------------------------------------------ GET /api/inbox/{case_id}
@router.get("/{case_id}")
async def list_inbox(case_id: int, as_of: Optional[str] = Query(None)) -> dict:
    """`as_of` (ISO date) is for the demo: "a week later", so the promise has passed."""
    day = _as_of(as_of)
    with db.session() as s:
        ctx = _ctx(s, case_id)
        cards = s.exec(select(InboxCard).where(InboxCard.case_id == case_id).order_by(InboxCard.id.desc())).all()
        views = [card_view(s, c, ctx, day) for c in cards]
        promises = sorted((p for v in views for p in v["promises"]), key=lambda p: p["due_date"])
        counts = {"pending": 0, "passed": 0, "kept": 0, "broken": 0}
        for p in promises:
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        chain_entries = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == ctx.worker.id).order_by(DiaryEntry.id)))
        return {
            "case": {"id": ctx.case.id, "status": ctx.case.status, "balance": ctx.balance,
                     "balance_display": fmt_money(ctx.balance),
                     "employer": {"name": ctx.employer.name, "language": ctx.employer_lang},
                     "worker": {"name": ctx.worker.name, "language": ctx.worker_lang}},
            "as_of": day.isoformat(),
            "cards": views,
            "promises": promises,
            "passed": [p for p in promises if p["status"] == "passed"],
            "counts": counts,
            "chain": {**verify_chain(chain_entries), "cards_linked": all(card_chain_ok(s, c) for c in cards)},
        }


# ------------------------------------------------------------------ promises
def _promise_ctx(s: Session, promise_id: int) -> tuple[InboxPromise, InboxCard, CaseCtx]:
    p = s.get(InboxPromise, promise_id)
    if p is None:
        raise HTTPException(404, "promise not found")
    c = s.get(InboxCard, p.card_id)
    return p, c, _ctx(s, p.case_id)


class RemindIn(BaseModel):
    as_of: Optional[str] = None
    force: bool = False     # preview the text before the date passes (the UI offers it only once passed)


@router.post("/promises/{promise_id}/remind")
async def remind(promise_id: int, body: RemindIn = Body(default_factory=RemindIn)) -> dict:
    """A gentle reminder in the employer's language that quotes their own words. Template only (no LLM), so every
    rupee figure is the quote's or the promised amount (re-extracted and checked). The worker shares it herself."""
    day = _as_of(body.as_of)
    with db.session() as s:
        p, c, ctx = _promise_ctx(s, promise_id)
        view = promise_view(s, p, day, ctx.balance, ctx.worker_lang)
        if view["status"] == "kept":
            raise HTTPException(409, {"error": "already_kept", "message": "this promise is marked as kept"})
        if view["status"] == "pending" and not body.force:
            raise HTTPException(409, {"error": "not_passed_yet", "message": f"the promised date is {p.due_date}"})
        r = reminder(employer=ctx.employer.name, worker=ctx.worker.name, employer_lang=ctx.employer_lang,
                     worker_lang=ctx.worker_lang, said_on=c.said_on, quote=p.quote or c.transcript,
                     quote_lang=c.language_code, amount=p.amount, is_rest=p.is_rest, due_date=p.due_date)
        link = employer_url(ctx.case.employer_token)
        r["share_text"] = f"{r['share_text']}\n{link}"
        r["employer_url"] = link
        r["whatsapp_url"] = "https://wa.me/?text=" + url_quote(r["share_text"])
        p.reminded_at = db.now_iso()
        s.add(p)
        s.commit()
        r["promise"] = promise_view(s, p, day, ctx.balance, ctx.worker_lang)
        return r


class StatusIn(BaseModel):
    status: Optional[Literal["pending", "kept", "broken"]] = None
    confirmed: Optional[bool] = None
    due_date: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    clear_amount: bool = False
    as_of: Optional[str] = None


@router.post("/promises/{promise_id}/status")
async def set_status(promise_id: int, body: StatusIn) -> dict:
    """Mark kept / broken (or back to pending), confirm the read-back, or correct the date / amount.
    The evidence card and its hash never change: corrections live on the promise and are flagged `edited`."""
    day = _as_of(body.as_of)
    with db.session() as s:
        p, _c, ctx = _promise_ctx(s, promise_id)
        if body.due_date is not None:
            try:
                p.due_date = dt.date.fromisoformat(body.due_date[:10]).isoformat()
            except ValueError:
                raise HTTPException(400, "due_date must be an ISO date")
            p.precision, p.range_start, p.edited = "day", None, True
        if body.clear_amount:
            p.amount, p.edited = None, True
        elif body.amount is not None:
            p.amount, p.is_rest, p.edited = round(float(body.amount), 2), False, True
        if body.confirmed is not None:
            p.confirmed = body.confirmed
        if body.status is not None:
            p.status, p.status_at = body.status, db.now_iso()
        s.add(p)
        s.commit()
        s.refresh(p)
        return promise_view(s, p, day, ctx.balance, ctx.worker_lang)
