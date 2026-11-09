"""The Polite -> Firm -> Formal ladder: text, voice note and PDF for each step; the legal-aid pack;
the media files they point to.

  POST /api/cases/{case_id}/messages/{step}   step = polite | firm | formal
  GET  /api/cases/{case_id}/messages
  POST /api/messages/{message_id}/sent        the worker shared it (she presses Send every time)
  GET  /api/cases/{case_id}/legal-pack        PDF for India Labourline / Labour Department / DLSA
  GET  /api/media/{key}                       stored voice notes and PDFs
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from .. import audio, db, letter, storage, voice_note
from ..gnani import GnaniError
from ..lang import today_ist
from ..messages import (STEPS, CaseCtx, compose, disclosure, employer_url, fmt_money, load_ctx, norm_lang,
                        tts_lang, upi_link)
from ..models import Case, Message
from ..translate import translate
from ..voice_profile import active_profile

log = logging.getLogger("letters")
router = APIRouter(tags=["letters"])

MEDIA_TYPES = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav", "pdf": "application/pdf",
               "webm": "audio/webm", "m4a": "audio/mp4", "json": "application/json"}


class StepIn(BaseModel):
    use_llm: bool = True            # the LLM may reword around the slots; amounts are re-checked
    regenerate: bool = False        # otherwise today's message for this step is reused (no new credits)
    voice: Literal["auto", "stock", "clone"] = "auto"   # auto = clone only if she opted in
    audio: bool = True
    pdf: bool = True
    lang: Optional[str] = None      # override the employer's language (hi-en | te-IN | en)


def media_url(key: str | None) -> str | None:
    return f"/api/media/{key}" if key else None


def store(case_id: int, data: bytes, ext: str) -> str:
    return storage.get_storage().put(storage.new_key(case_id, ext), data)


def gnani_error_dict(e: Exception) -> dict[str, Any]:
    if isinstance(e, GnaniError):
        return e.as_dict()
    return {"source": "audio", "message": str(e)[:200]}


def message_view(m: Message, ctx: CaseCtx | None = None) -> dict[str, Any]:
    out = {"message_id": m.id, "case_id": m.case_id, "step": m.step, "direction": m.direction,
           "language": m.language, "text": m.text, "text_worker_lang": m.text_worker_lang,
           "audio_url": media_url(m.audio_path), "pdf_url": media_url(m.pdf_path),
           "voice_note_id": m.voice_note_id, "status": m.status, "created_at": m.created_at, "sent_at": m.sent_at}
    if ctx is not None:
        out["employer_url"] = employer_url(ctx.case.employer_token)
    return out


def _today_utc_prefix() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _reusable(s: Session, ctx: CaseCtx, step: str, lang: str, mode: str, want_audio: bool) -> Message | None:
    m = s.exec(select(Message).where(Message.case_id == ctx.case.id, Message.step == step,
                                     Message.direction == "to_employer", Message.language == lang)
               .order_by(Message.id.desc())).first()
    if m is None or not (m.created_at or "").startswith(_today_utc_prefix()):
        return None
    if not m.text.startswith(disclosure(ctx.worker.name, lang, mode)):
        return None
    if fmt_money(ctx.balance) not in m.text or (want_audio and not m.audio_path) or not m.pdf_path:
        return None
    return m


@router.post("/api/cases/{case_id}/messages/{step}")
async def make_step(case_id: int, step: str, body: StepIn = Body(default_factory=StepIn)) -> dict:
    """Write the step in the employer's language, speak it (AI disclosure first) and render its PDF.

    Polite: warm ask + itemised card. Firm: amount, due date, work log. Formal: bilingual demand letter.
    """
    if step not in STEPS:
        raise HTTPException(404, f"step must be one of {list(STEPS)}")
    with db.session() as s:
        ctx = load_ctx(s, case_id)
        if ctx is None:
            raise HTTPException(404, "case not found")
        if ctx.balance <= 0:
            raise HTTPException(409, {"error": "nothing_due", "message": "this case has no balance due"})
        profile = active_profile(s, ctx.worker.id) if body.voice != "stock" else None
        if body.voice == "clone" and profile is None:
            raise HTTPException(409, {"error": "no_voice_profile",
                                      "message": "no opted-in voice profile; use voice=stock or record one"})
        embedding = voice_note.load_embedding(profile)
        mode = "clone" if embedding else "stock"
        lang = norm_lang(body.lang or ctx.employer.language)
        upi = upi_link(ctx.worker.upi_vpa, ctx.worker.name, ctx.balance)
        if not body.regenerate:
            old = _reusable(s, ctx, step, lang, mode, body.audio)
            if old is not None:
                return {**message_view(old, ctx), "reused": True, "upi_link": upi, "voice_mode": mode,
                        "balance": ctx.balance}

        draft = await compose(ctx, step, voice_mode=mode, use_llm=body.use_llm, lang=lang)
        worker_view = await compose(ctx, step, voice_mode=mode, use_llm=False, lang=ctx.worker_lang)
        draft_en = await compose(ctx, step, voice_mode=mode, use_llm=False, lang="en") if step == "formal" else None

        audio_info, audio_error, audio_key = None, None, None
        if body.audio:
            try:
                note = await voice_note.make_voice_note(draft.speech, tts_lang(lang), worker_name=ctx.worker.name,
                                                        embedding=embedding)
                audio_key = store(case_id, note.data, "ogg")
                audio_info = {"url": media_url(audio_key), "duration_s": note.duration_s, "voice_mode": note.voice_mode,
                              "voice": note.voice, "voice_note_id": note.id, "gnani_calls": note.gnani_calls,
                              "cache_hits": note.cache_hits, "sentences": len(note.sentences),
                              "metadata_comment": note.comment}
            except (GnaniError, audio.AudioError, ValueError) as e:
                log.warning("voice note failed: %s", str(e)[:160])
                audio_error = gnani_error_dict(e)

        pdf_key = None
        if body.pdf:
            pdf_bytes = await run_in_threadpool(letter.render, letter.LetterInput(
                ctx=ctx, step=step, draft=draft, draft_en=draft_en, upi_link=upi))
            pdf_key = store(case_id, pdf_bytes, "pdf")

        m = Message(case_id=case_id, step=step, direction="to_employer", language=lang, text=draft.text,
                    text_worker_lang=worker_view.text if ctx.worker_lang != lang else None,
                    audio_path=audio_key, pdf_path=pdf_key,
                    voice_note_id=audio_info["voice_note_id"] if audio_info else None, status="draft")
        s.add(m)
        s.commit()
        s.refresh(m)
        url = employer_url(ctx.case.employer_token)
        return {
            **message_view(m, ctx),
            "reused": False,
            "source": draft.source,
            "sentences": draft.display_sentences,
            "speech": draft.speech,
            "disclosure": draft.disclosure_display,
            "reply_by": draft.reply_by,
            "voice_mode": mode,
            "audio": audio_info,
            "audio_error": audio_error,
            "upi_link": upi,
            "share_text": f"{draft.text}\n\n{url}",
            "balance": ctx.balance,
            "checks": draft.checks,
        }


@router.get("/api/cases/{case_id}/messages")
async def list_messages(case_id: int) -> dict:
    with db.session() as s:
        if s.get(Case, case_id) is None:
            raise HTTPException(404, "case not found")
        rows = list(s.exec(select(Message).where(Message.case_id == case_id).order_by(Message.id)))
        return {"case_id": case_id, "messages": [message_view(m) for m in rows]}


@router.post("/api/messages/{message_id}/sent")
async def mark_sent(message_id: int) -> dict:
    """The worker shared the step herself (WhatsApp / Web Share)."""
    with db.session() as s:
        m = s.get(Message, message_id)
        if m is None:
            raise HTTPException(404, "message not found")
        m.status, m.sent_at = "sent", db.now_iso()
        c = s.get(Case, m.case_id)
        if c is not None and c.status in ("draft", "confirmed"):
            c.status, c.updated_at = "sent", db.now_iso()
            s.add(c)
        s.add(m)
        s.commit()
        s.refresh(m)
        return message_view(m)


@router.get("/api/cases/{case_id}/legal-pack")
async def legal_pack(case_id: int, use_llm: bool = True) -> Response:
    """PDF case file: statement (her words + English translation), itemised claim, messages sent,
    payments and the diary hash chain, with the state route (never SAMADHAN)."""
    with db.session() as s:
        ctx = load_ctx(s, case_id)
        if ctx is None:
            raise HTTPException(404, "case not found")
        history = [message_view(m) for m in s.exec(select(Message).where(
            Message.case_id == case_id, Message.direction == "to_employer").order_by(Message.id))]
    tr = None
    src = norm_lang(ctx.case.transcript_lang or ctx.worker.language)
    if (ctx.case.transcript or "").strip() and src != "en":
        t = await translate(ctx.case.transcript, src, "en", use_llm=use_llm)
        tr = t.text if t.source == "llm" else None
    data = await run_in_threadpool(letter.render_legal_pack, letter.LetterInput(
        ctx=ctx, step="legal_pack", history=history, statement_translation=tr, today=today_ist()))
    name = f"baaki-legal-pack-case{case_id}.pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.get("/api/media/{key:path}")
async def media(key: str) -> Response:
    st = storage.get_storage()
    try:
        p = st.local_path(key)
    except ValueError:
        raise HTTPException(404, "not found")
    if p is None:
        raise HTTPException(404, "not found")
    ext = p.suffix.lstrip(".").lower()
    data = await run_in_threadpool(p.read_bytes)
    return Response(content=data, media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
                    headers={"Cache-Control": "private, max-age=3600"})
