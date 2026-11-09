"""Haq Raise: ask for a raise to the legal minimum, with a step-up plan. Owned by the Haq Raise agent.

Worker side (case id):
  GET  /api/raise/summary?worker_id=          per home: current, legal estimate, gap (month / year), status; totals
  GET  /api/raise/case/{case_id}              numbers + suggested plans (+ the current raise request, if any)
  POST /api/raise/case/{case_id}/compose      JSON plan -> message in the EMPLOYER's language + voice note (+ her line)
  POST /api/raise/case/{case_id}/sent         she shared it (she presses Send herself)
Employer side (its own token, separate from the case's /e/{token}):
  GET  /api/raise/e/{token}                   the request in the employer's language, the note, a small "why"
  POST /api/raise/e/{token}/played
  POST /api/raise/e/{token}/accept            JSON {choice: asked | step} -> new wage, agreement PDF, celebration
  POST /api/raise/e/{token}/step-up           = accept with choice "step"
  POST /api/raise/e/{token}/talk              multipart audio | text -> transcript -> worker's language (+ voice)
  GET  /api/raise/e/{token}/payday.ics        monthly payday reminder at the new wage
Demo:
  POST /api/raise/demo                        synthetic: Mehta madam's home (Rs 2,500 for 2 h a day) ready to ask

Every amount comes from check_core / app.wages and is re-checked in the message (raise_core.compose).
The case row itself is never changed: the new wage starts next month and lives on the RaiseAsk.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from .. import audio, config, db, raise_core, voice_note, wages
from ..gnani import GnaniError
from ..lang import today_ist
from ..messages import CaseCtx, fmt_money, load_ctx, month_name, name_in, norm_lang, tts_lang
from ..models import Case, Employer, Worker
from ..raise_models import RaiseAsk, RaiseEvent
from ..stt_service import transcribe_upload
from ..translate import speakable, translate
from .employer import ACCEPTED_AUDIO, MAX_UPLOAD_BYTES, STT_FOR
from .letters import gnani_error_dict, media_url, store

log = logging.getLogger("raise")
router = APIRouter(prefix="/api/raise", tags=["raise"])

ANSWERED = ("accepted", "stepped")
MAX_TEXT = 600
DEMO_YEARS = 4          # synthetic: Lakshmi has worked 4 years for Mehta madam (ideas_W_worker W07)
VOICE_ERRORS = (GnaniError, audio.AudioError, ValueError, RuntimeError)


def _today() -> dt.date:
    return today_ist()


# --------------------------------------------------------------------------- loading
def _valid(ra: RaiseAsk | None, case: Case | None) -> bool:
    return ra is not None and case is not None and ra.case_token == case.employer_token


def _latest(s: Session, case: Case) -> RaiseAsk | None:
    ra = s.exec(select(RaiseAsk).where(RaiseAsk.case_id == case.id).order_by(RaiseAsk.id.desc())).first()
    return ra if _valid(ra, case) else None


def _ctx_or_404(s: Session, case_id: int) -> CaseCtx:
    ctx = load_ctx(s, case_id)
    if ctx is None or ctx.worker is None or ctx.employer is None:
        raise HTTPException(404, "case not found")
    return ctx


def _by_token(s: Session, token: str) -> tuple[RaiseAsk, CaseCtx]:
    ra = s.exec(select(RaiseAsk).where(RaiseAsk.token == token)).first()
    ctx = load_ctx(s, ra.case_id) if ra else None
    if ra is None or ctx is None or not _valid(ra, ctx.case):
        raise HTTPException(404, "link not found")
    return ra, ctx


def _estimate(case: Case, today: dt.date) -> dict[str, Any]:
    # Hours come from what she said (calc_inputs.case_hours); the DB default of 8 h is never used as a guess.
    return raise_core.estimate_for_case(case, today)


def _next_month(today: dt.date) -> str:
    return wages.month_key(raise_core.first_of_next_month(today))


def _nums(ra: RaiseAsk) -> dict[str, Any]:
    out: dict[str, Any] = {"plan": ra.plan, "ask": ra.ask_amount, "start": f"{ra.start_month}-01",
                           "start_month": ra.start_month, "step1": None, "months": None, "step_date": None,
                           "step_month": None}
    if ra.plan == "step" and ra.step1_amount:
        out.update(step1=ra.step1_amount, months=ra.step_months, step_month=ra.step_month,
                   step_date=f"{ra.step_month}-01")
    return out


def _event(s: Session, ra: RaiseAsk, kind: str, **kw: Any) -> RaiseEvent:
    data = kw.pop("data", None)
    ev = RaiseEvent(raise_id=ra.id, kind=kind, data_json=json.dumps(data or {}, ensure_ascii=False), **kw)
    s.add(ev)
    return ev


def _events(s: Session, ra: RaiseAsk) -> list[RaiseEvent]:
    return list(s.exec(select(RaiseEvent).where(RaiseEvent.raise_id == ra.id).order_by(RaiseEvent.id)))


def _event_view(ev: RaiseEvent) -> dict[str, Any]:
    return {"id": ev.id, "kind": ev.kind, "direction": ev.direction, "language": ev.language, "text": ev.text,
            "text_worker_lang": ev.text_worker_lang, "audio_url": media_url(ev.audio_key),
            "original_audio_url": media_url(ev.original_audio_key), "data": json.loads(ev.data_json or "{}"),
            "created_at": ev.created_at}


def employer_path(token: str) -> str:
    return f"/raise/e/{token}"


def _month_text(ym: str | None, lang: str) -> str | None:
    return month_name(ym, lang, year=True) if ym else None


def _final_wage(ra: RaiseAsk | None) -> float | None:
    if ra is None or ra.status not in ANSWERED:
        return None
    return ra.step_up_to or ra.new_wage


def _answer(ra: RaiseAsk) -> dict[str, Any] | None:
    if ra.status not in ANSWERED:
        return None
    return {"choice": ra.choice, "new_wage": ra.new_wage, "new_wage_from": ra.new_wage_from,
            "step_up_to": ra.step_up_to, "step_up_from": ra.step_up_from, "answered_at": ra.answered_at,
            "yearly_gain": raise_core.yearly_gain(ra.current_wage, _final_wage(ra) or ra.current_wage)}


def _celebration(s: Session, ra: RaiseAsk) -> dict[str, Any] | None:
    ev = s.exec(select(RaiseEvent).where(RaiseEvent.raise_id == ra.id, RaiseEvent.kind == "celebration")
                .order_by(RaiseEvent.id.desc())).first()
    if ev is None:
        return None
    return {**json.loads(ev.data_json or "{}"), "event_id": ev.id, "text": ev.text,
            "audio_url": media_url(ev.audio_key), "created_at": ev.created_at}


def _ics_url(ra: RaiseAsk) -> str | None:
    return f"/api/raise/e/{ra.token}/payday.ics" if ra.status in ANSWERED else None


def _raise_view(s: Session, ra: RaiseAsk, ctx: CaseCtx) -> dict[str, Any]:
    msg = json.loads(ra.message_json or "{}")
    path = employer_path(ra.token)
    url = f"{config.public_base_url()}{path}"
    return {
        "id": ra.id,
        "status": ra.status,
        "plan": ra.plan,
        "current": ra.current_wage,
        "legal_estimate": ra.legal_estimate,
        "ask_amount": ra.ask_amount,
        "step1_amount": ra.step1_amount,
        "step_months": ra.step_months if ra.plan == "step" else None,
        "start_month": ra.start_month,
        "step_month": ra.step_month,
        "mention_law": ra.mention_law,
        "years_worked": ra.years_worked,
        "personal_text": ra.personal_text,
        "message": {"lang": ra.message_lang, "text": ra.message_text, "sentences": msg.get("sentences", []),
                    "disclosure": (msg.get("speech") or [""])[0], "source": msg.get("source"), "checks": msg.get("checks"), "personal": msg.get("personal"),
                    "text_worker_lang": msg.get("text_worker_lang")},
        "audio_url": media_url(ra.audio_key),
        "audio_error": msg.get("audio_error"),
        "employer_path": path,
        "employer_url": url,
        "share_text": f"{ra.message_text}\n\n{url}" if ra.message_text else None,
        "answer": _answer(ra),
        "celebration": _celebration(s, ra),
        "agreement_url": media_url(ra.agreement_key),
        "ics_url": _ics_url(ra),
        "events": [_event_view(e) for e in _events(s, ra)],
        "yearly_gain_asked": raise_core.yearly_gain(ra.current_wage, ra.ask_amount),
        "per_day": raise_core.per_day(ra.ask_amount - ra.current_wage, ra.working_days),
        "per_day_step1": raise_core.per_day((ra.step1_amount or 0) - ra.current_wage, ra.working_days)
        if ra.step1_amount else None,
        "demo": ra.demo,
        "updated_at": ra.updated_at,
    }


def _plan_view(p: dict[str, Any] | None, est: dict[str, Any], lang: str) -> dict[str, Any] | None:
    if p is None:
        return None
    return {**p, "per_day": raise_core.per_day(p["ask"] - est["current"], est["working_days"]),
            "per_day_step1": raise_core.per_day(p["step1"] - est["current"], est["working_days"]) if p["step1"] else None,
            "yearly_gain": raise_core.yearly_gain(est["current"], p["ask"]),
            "start_display": _month_text(p["start_month"], lang), "step_display": _month_text(p["step_month"], lang)}


# --------------------------------------------------------------------------- summary (dashboard card)
@router.get("/summary")
async def summary(worker_id: int = Query(..., gt=0)) -> dict:
    today = _today()
    with db.session() as s:
        w = s.get(Worker, worker_id)
        if w is None:
            raise HTTPException(404, "worker not found")
        cases = list(s.exec(select(Case).where(Case.worker_id == worker_id).order_by(Case.id)))
        homes: list[dict[str, Any]] = []
        possible, won, best = 0.0, 0.0, None
        for c in cases:
            if not c.monthly_wage or c.monthly_wage <= 0:
                continue
            e = s.get(Employer, c.employer_id)
            est = _estimate(c, today)
            ra = _latest(s, c)
            if ra:
                status = ra.status
            elif est.get("needs_hours"):
                status = "needs_hours"          # can't call it fair (or unfair) without her hours
            else:
                status = "fair" if est["gap_monthly"] <= 0 else "none"
            answered = ra is not None and ra.status in ANSWERED
            won_y = raise_core.yearly_gain(c.monthly_wage, _final_wage(ra) or 0) if answered else 0.0
            home = {"case_id": c.id, "employer": e.name if e else "", "employer_id": c.employer_id,
                    "employer_language": norm_lang(e.language) if e else "hi-en",
                    "current": est["current"], "legal_estimate": est["legal_estimate"], "target": est["target"],
                    "is_estimate": est["is_estimate"], "gap_monthly": est["gap_monthly"],
                    "gap_yearly": est["gap_yearly"], "per_day": est["per_day"], "hours_per_day": est["hours_per_day"],
                    "status": status, "raise_id": ra.id if ra else None, "new_wage": _final_wage(ra),
                    "yearly_gain_won": won_y, "url": f"/raise/{c.id}"}
            homes.append(home)
            if answered:
                won += won_y
            elif est["gap_yearly"] > 0:
                possible += est["gap_yearly"]
                if best is None or est["gap_yearly"] > best["gap_yearly"]:
                    best = home
        return {"worker_id": worker_id, "worker": w.name, "language": norm_lang(w.language), "per_home": homes,
                "total_yearly_gain_possible": round(possible, 2), "total_yearly_gain_won": round(won, 2),
                "best_case_id": best["case_id"] if best else None, "best_url": best["url"] if best else None,
                "best_employer": best["employer"] if best else None,
                "source_note": "Legal figures are estimates from Telangana G.O.Ms.No.6 (part-time pro-rated)."}


# --------------------------------------------------------------------------- worker side
@router.get("/case/{case_id}")
async def case_view(case_id: int) -> dict:
    today = _today()
    with db.session() as s:
        ctx = _ctx_or_404(s, case_id)
        est = _estimate(ctx.case, today)
        ra = _latest(s, ctx.case)
        wl = ctx.worker_lang
        sug = raise_core.suggestions(est, today)
        return {
            "case_id": ctx.case.id,
            "worker": {"id": ctx.worker.id, "name": ctx.worker.name, "language": wl},
            "employer": {"id": ctx.employer.id, "name": ctx.employer.name, "language": ctx.employer_lang,
                         "name_display": name_in(ctx.employer.name, wl),
                         "name_by_lang": {lg: name_in(ctx.employer.name, lg) for lg in raise_core.LANGS}},
            "numbers": est,
            "plans": {"full": _plan_view(sug["full"], est, wl), "step": _plan_view(sug["step"], est, wl)},
            "raise": _raise_view(s, ra, ctx) if ra else None,
            "today": today.isoformat(),
        }


class ComposeIn(BaseModel):
    plan: Literal["full", "step"] = "step"
    ask_amount: Optional[float] = Field(default=None, gt=0)
    step1_amount: Optional[float] = Field(default=None, gt=0)
    step_months: Optional[int] = Field(default=None, ge=1, le=12)
    start_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    mention_law: bool = False                       # judge J1: OFF by default
    years_worked: Optional[float] = Field(default=None, ge=0, le=60)
    personal_text: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    personal_lang: Optional[str] = None             # language of personal_text (default: the worker's)
    use_llm: bool = True                            # LLM may translate her own line (amounts re-checked)
    reword: bool = False                            # LLM may also reword the template sentences (slots fixed)
    audio: bool = True


async def _personal_for(text: str, src: str, dst: str, worker: str, use_llm: bool) -> dict[str, Any] | None:
    """Her own line, in the employer's language. LLM translation (amounts re-checked by translate()); without
    it, her words are quoted with a lead-in and left out of the spoken note."""
    text = (text or "").strip()
    if not text:
        return None
    src, dst = norm_lang(src), norm_lang(dst)
    if src == dst:
        return {"display": text, "speech": speakable(text, dst), "source": "same_language", "original": text}
    tr = await translate(text, src, dst, use_llm=use_llm)
    if tr.source == "llm":
        return {"display": tr.text, "speech": speakable(tr.text, dst), "source": "llm", "original": text}
    lead = raise_core.PERSONAL_LEAD[dst].format(worker=name_in(worker, dst))
    return {"display": f"{lead} “{text}”", "speech": None, "source": "quoted", "original": text}


async def _compose_into(s: Session, ra: RaiseAsk, ctx: CaseCtx, body: ComposeIn, today: dt.date) -> None:
    est = _estimate(ctx.case, today)
    if est.get("needs_hours") and body.ask_amount is None:
        raise HTTPException(409, {"error": "needs_hours", "message": "hours not said: estimate needs hours",
                                  "how": est.get("how")})
    if est["gap_monthly"] <= 0 and body.ask_amount is None:
        raise HTTPException(409, {"error": "already_fair", "message": "this home already pays at least the estimate"})
    try:
        nums = raise_core.plan_numbers(body.plan, est["current"], est["target"], today, ask=body.ask_amount,
                                       step1=body.step1_amount, months=body.step_months, start_month=body.start_month)
    except ValueError as e:
        raise HTTPException(400, {"error": "bad_plan", "message": str(e)})
    el, wl = ctx.employer_lang, ctx.worker_lang
    mask = [ctx.worker.phone or "", ctx.employer.phone or "", ctx.worker.upi_vpa or ""]
    p_src = norm_lang(body.personal_lang or wl)
    personal = await _personal_for(body.personal_text or "", p_src, el, ctx.worker.name, body.use_llm)
    common = dict(worker=ctx.worker.name, employer=ctx.employer.name, current=est["current"],
                  legal=est["legal_estimate"], nums=nums, mention_law=body.mention_law, years=body.years_worked,
                  mask=mask)
    msg = await raise_core.compose(lang=el, personal=personal, use_llm=body.use_llm and body.reword, **common)
    text_wl = None
    if wl != el:  # what the message says, for her, in her language (template, no LLM)
        p_w = None
        if personal:
            p_w = {"display": personal["original"] if p_src == wl else personal["display"], "speech": None}
        text_wl = (await raise_core.compose(lang=wl, personal=p_w, use_llm=False, **common))["text"]

    audio_key, note_id, audio_err, audio_info = None, None, None, None
    if body.audio:
        try:
            # stock Timbre pauses at full stops by itself: disclosure + one body clip = at most 2 Gnani calls
            spoken = [msg["speech"][0], " ".join(msg["speech"][1:])]
            note = await voice_note.make_voice_note(spoken, tts_lang(el), worker_name=ctx.worker.name,
                                                    purpose="raise request")
            audio_key, note_id = store(ctx.case.id, note.data, "ogg"), note.id
            audio_info = {"duration_s": note.duration_s, "voice": note.voice, "gnani_calls": note.gnani_calls,
                          "cache_hits": note.cache_hits}
        except VOICE_ERRORS as e:
            log.warning("raise voice note failed: %s", str(e)[:160])
            audio_err = gnani_error_dict(e)

    ra.current_wage, ra.legal_estimate, ra.is_estimate = est["current"], est["legal_estimate"], est["is_estimate"]
    ra.work_type, ra.hours_per_day, ra.days_per_week = est["work_type"], est["hours_per_day"], est["days_per_week"]
    ra.working_days = est["working_days"]
    ra.plan, ra.ask_amount, ra.step1_amount = nums["plan"], nums["ask"], nums["step1"]
    ra.step_months = nums["months"] or raise_core.DEFAULT_STEP_MONTHS
    ra.start_month, ra.step_month = nums["start_month"], nums["step_month"]
    ra.mention_law, ra.years_worked = body.mention_law, body.years_worked
    ra.personal_text = (body.personal_text or "").strip()
    ra.personal_lang = p_src if ra.personal_text else ""
    ra.message_lang, ra.message_text = el, msg["text"]
    ra.message_json = json.dumps({"sentences": msg["sentences"], "speech": msg["speech"], "source": msg["source"],
                                  "checks": msg["checks"], "personal": msg["personal"],
                                  "personal_source": personal["source"] if personal else None,
                                  "text_worker_lang": text_wl, "audio_error": audio_err, "audio": audio_info},
                                 ensure_ascii=False)
    ra.audio_key, ra.voice_note_id = audio_key, note_id
    ra.status = "draft"
    ra.updated_at = db.now_iso()
    s.add(ra)
    s.flush()
    _event(s, ra, "composed", direction="to_employer", language=el, text=msg["text"], text_worker_lang=text_wl,
           audio_key=audio_key, data={"plan": nums, "mention_law": body.mention_law, "source": msg["source"]})


@router.post("/case/{case_id}/compose")
async def compose(case_id: int, body: ComposeIn = Body(default_factory=ComposeIn)) -> dict:
    today = _today()
    with db.session() as s:
        ctx = _ctx_or_404(s, case_id)
        ra = _latest(s, ctx.case)
        if ra is not None and ra.status in ANSWERED:
            raise HTTPException(409, {"error": "already_agreed", "message": "this raise was already agreed"})
        if ra is None:
            ra = RaiseAsk(case_id=ctx.case.id, worker_id=ctx.worker.id, employer_id=ctx.employer.id,
                          case_token=ctx.case.employer_token)
        await _compose_into(s, ra, ctx, body, today)
        s.commit()
        s.refresh(ra)
        return _raise_view(s, ra, ctx)


@router.post("/case/{case_id}/sent")
async def mark_sent(case_id: int) -> dict:
    with db.session() as s:
        ctx = _ctx_or_404(s, case_id)
        ra = _latest(s, ctx.case)
        if ra is None or not ra.message_text:
            raise HTTPException(404, "no raise request to send")
        if ra.status == "draft":
            ra.status, ra.updated_at = "sent", db.now_iso()
            s.add(ra)
            _event(s, ra, "sent", direction="to_employer", language=ra.message_lang)
            s.commit()
        return {"ok": True, "status": ra.status, "raise_id": ra.id}


# --------------------------------------------------------------------------- employer side
WHY = {
    "hi-en": {"per_day": "यह हर काम के दिन के लिए लगभग ₹{n} ज़्यादा है।",
              "per_day_step": "पहले कदम में हर दिन लगभग ₹{n} ज़्यादा।",
              "legal": "{worker} ने बताया: Telangana में इस काम का न्यूनतम वेतन लगभग {legal} है (अनुमान)।",
              "fair": "Hyderabad में इस काम की fair pay देखें"},
    "te-IN": {"per_day": "ఇది ప్రతి పని రోజుకు సుమారు ₹{n} ఎక్కువ.",
              "per_day_step": "మొదటి దశలో రోజుకు సుమారు ₹{n} ఎక్కువ.",
              "legal": "{worker} చెప్పారు: ఈ పనికి తెలంగాణ కనీస వేతనం సుమారు {legal} (అంచనా).",
              "fair": "హైదరాబాద్‌లో ఈ పనికి న్యాయమైన జీతం చూడండి"},
    "en": {"per_day": "That is about ₹{n} more per working day.",
           "per_day_step": "The first step is about ₹{n} more a day.",
           "legal": "{worker} mentioned: the Telangana minimum for this work is about {legal} (estimate).",
           "fair": "See fair pay for this work in Hyderabad"},
}


def _step_offer(ra: RaiseAsk, today: dt.date) -> dict[str, Any] | None:
    """For a full-amount request, the step-up the employer can choose instead (same target, half now)."""
    if ra.plan != "full":
        return None
    try:
        return raise_core.plan_numbers("step", ra.current_wage, ra.ask_amount, today,
                                       start_month=max(ra.start_month, _next_month(today)))
    except ValueError:
        return None


@router.get("/e/{token}")
async def employer_view(token: str) -> dict:
    today = _today()
    with db.session() as s:
        ra, ctx = _by_token(s, token)
        el = ctx.employer_lang
        msg = json.loads(ra.message_json or "{}")
        pd = raise_core.per_day(ra.ask_amount - ra.current_wage, ra.working_days)
        pd1 = raise_core.per_day((ra.step1_amount or 0) - ra.current_wage, ra.working_days) if ra.step1_amount else None
        offer = _step_offer(ra, today)
        W = WHY[el]
        worker_n = name_in(ctx.worker.name, el)
        why = {"per_day": pd, "per_day_text": W["per_day"].format(n=pd),
               "per_day_step1": pd1, "per_day_step1_text": W["per_day_step"].format(n=pd1) if pd1 else None,
               "legal_estimate": ra.legal_estimate if ra.mention_law else None,
               "legal_text": W["legal"].format(worker=worker_n, legal=fmt_money(ra.legal_estimate))
               if ra.mention_law else None,
               "fair_pay_link": None if ra.mention_law else "/check",
               "fair_pay_text": None if ra.mention_law else W["fair"]}
        replies = [_event_view(e) for e in _events(s, ra) if e.kind == "talk"]
        return {
            "raise_id": ra.id,
            "status": ra.status,
            "worker": {"name": ctx.worker.name, "name_display": worker_n, "language": ctx.worker_lang},
            "employer": {"name": ctx.employer.name, "name_display": name_in(ctx.employer.name, el), "language": el},
            "message": {"text": ra.message_text, "sentences": msg.get("sentences", []), "lang": ra.message_lang,
                        "disclosure": (msg.get("speech") or [""])[0]},
            "audio_url": media_url(ra.audio_key),
            "plan": ra.plan,
            "current": ra.current_wage,
            "ask_amount": ra.ask_amount,
            "step1_amount": ra.step1_amount,
            "start_month": ra.start_month,
            "step_month": ra.step_month,
            "start_display": _month_text(ra.start_month, el),
            "step_display": _month_text(ra.step_month, el),
            "step_offer": {"step1": offer["step1"], "months": offer["months"], "start_month": offer["start_month"],
                           "step_month": offer["step_month"], "start_display": _month_text(offer["start_month"], el),
                           "step_display": _month_text(offer["step_month"], el),
                           "per_day_step1": raise_core.per_day(offer["step1"] - ra.current_wage, ra.working_days)}
            if offer else None,
            "why": why,
            "can_answer": ra.status not in ANSWERED and bool(ra.message_text),
            "answer": _answer(ra),
            "agreement_url": media_url(ra.agreement_key),
            "ics_url": _ics_url(ra),
            "replies": replies,
            "ai_notice": "The voice note is AI-generated by the Baaki app on behalf of the worker, with consent.",
        }


@router.post("/e/{token}/played")
async def played(token: str) -> dict:
    with db.session() as s:
        ra, _ = _by_token(s, token)
        if ra.status in ("draft", "sent"):
            ra.status, ra.updated_at = "played", db.now_iso()
            s.add(ra)
            _event(s, ra, "played", direction="from_employer")
            s.commit()
        return {"ok": True, "status": ra.status}


class AcceptIn(BaseModel):
    choice: Literal["asked", "step"] = "asked"
    alert_audio: bool = True


async def _accept(token: str, body: AcceptIn) -> dict:
    today = _today()
    with db.session() as s:
        ra, ctx = _by_token(s, token)
        if ra.status in ANSWERED:
            raise HTTPException(409, {"error": "already_agreed", "message": "already agreed"})
        if not ra.message_text:
            raise HTTPException(409, {"error": "not_ready", "message": "the request is not ready yet"})
        nums = _nums(ra)
        if body.choice == "step" and ra.plan == "full":
            nums = _step_offer(ra, today)
            if nums is None:
                raise HTTPException(400, {"error": "bad_plan", "message": "the gap is too small for a step-up"})
        elif nums["start_month"] < wages.month_key(today):
            # an old request: the new wage still starts next month, never in the past
            nums = raise_core.plan_numbers(ra.plan, ra.current_wage, ra.ask_amount, today, step1=ra.step1_amount,
                                           months=ra.step_months if ra.plan == "step" else None)
        step = nums.get("step1") is not None
        now = db.now_iso()
        ra.status = "stepped" if body.choice == "step" else "accepted"
        ra.choice = body.choice
        ra.new_wage = nums["step1"] if step else nums["ask"]
        ra.new_wage_from = nums["start"]
        ra.step_up_to = nums["ask"] if step else None
        ra.step_up_from = nums["step_date"] if step else None
        ra.answered_at, ra.updated_at = now, now

        pdf = await run_in_threadpool(lambda: raise_core.agreement_pdf(
            worker=ctx.worker.name, employer=ctx.employer.name, worker_lang=ctx.worker_lang,
            employer_lang=ctx.employer_lang, work_type=ra.work_type, hours=ra.hours_per_day, days=ra.days_per_week,
            current=ra.current_wage, nums=nums, choice=body.choice, today=today))
        ra.agreement_key = store(ctx.case.id, pdf, "pdf")
        s.add(ra)
        _event(s, ra, ra.status, direction="from_employer", language=ctx.employer_lang,
               data={"nums": nums, "choice": body.choice})

        cel = raise_core.celebration(worker_lang=ctx.worker_lang, employer=ctx.employer.name, nums=nums,
                                     current=ra.current_wage)
        key, audio_err, audio_info = None, None, None
        if body.alert_audio:
            try:
                note = await voice_note.make_voice_note([cel["speech"]], tts_lang(ctx.worker_lang),
                                                        purpose="raise alert")
                key = store(ctx.case.id, note.data, "ogg")
                audio_info = {"duration_s": note.duration_s, "voice": note.voice, "gnani_calls": note.gnani_calls}
            except VOICE_ERRORS as e:
                audio_err = gnani_error_dict(e)
        _event(s, ra, "celebration", direction="to_worker", language=ctx.worker_lang, text=cel["text"], audio_key=key,
               data={**{k: v for k, v in cel.items() if k != "text"}, "audio_error": audio_err, "audio": audio_info})
        s.commit()
        s.refresh(ra)
        return {"status": ra.status, "answer": _answer(ra), "celebration": _celebration(s, ra),
                "agreement_url": media_url(ra.agreement_key), "ics_url": _ics_url(ra)}


@router.post("/e/{token}/accept")
async def accept(token: str, body: AcceptIn = Body(default_factory=AcceptIn)) -> dict:
    return await _accept(token, body)


@router.post("/e/{token}/step-up")
async def step_up(token: str) -> dict:
    return await _accept(token, AcceptIn(choice="step"))


@router.post("/e/{token}/talk")
async def talk(token: str, audio_file: Optional[UploadFile] = File(None, alias="audio"),
               text: Optional[str] = Form(None), lang: Optional[str] = Form(None),
               use_llm: bool = Form(True)) -> dict:
    """'Let's talk': the employer speaks (or types) -> transcript -> the worker's language (+ a voice note)."""
    data, ext = b"", ""
    if audio_file is not None:
        name = audio_file.filename or "reply"
        ext = audio.ext_of(name) or audio.ext_of("x." + (audio_file.content_type or "").split("/")[-1].split(";")[0])
        if ext not in ACCEPTED_AUDIO:
            raise HTTPException(415, f"unsupported audio type '{ext or audio_file.content_type}'")
        data = await audio_file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "audio larger than 25 MB")
    if not data and not (text or "").strip():
        raise HTTPException(400, "send audio or text")
    with db.session() as s:
        ra, ctx = _by_token(s, token)
        src = norm_lang(lang or ctx.employer.language)
        stt_info = None
        if data:
            codes, mode = STT_FOR[src]
            try:
                stt = await transcribe_upload(data, f"talk.{ext}", lang=codes, mode=mode)
            except ValueError as e:
                raise HTTPException(400, str(e))
            except audio.AudioError as e:
                raise HTTPException(415, f"could not decode audio: {e}")
            except GnaniError as e:
                raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
            transcript = (stt.get("transcript") or "").strip()
            stt_info = {"language_code": stt.get("language_code"), "mode": stt.get("mode"),
                        "duration_s": stt.get("duration_s")}
            if not transcript:
                raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please record again"})
        else:
            transcript = (text or "").strip()[:MAX_TEXT]
        wl = ctx.worker_lang
        tr = await translate(transcript, src, wl, speaker=ctx.employer.name, use_llm=use_llm)
        orig_key = store(ctx.case.id, data, ext) if data else None
        key, audio_err = None, None
        try:
            note = await voice_note.make_voice_note([" ".join(tr.speech)], tts_lang(wl),
                                                    purpose="raise reply translation")
            key = store(ctx.case.id, note.data, "ogg")
        except VOICE_ERRORS as e:
            audio_err = gnani_error_dict(e)
        if ra.status not in ANSWERED:
            ra.status = "talk"
        ra.updated_at = db.now_iso()
        s.add(ra)
        ev = _event(s, ra, "talk", direction="from_employer", language=src, text=transcript, text_worker_lang=tr.text,
                    audio_key=key, original_audio_key=orig_key,
                    data={"translation_source": tr.source, "amounts": tr.amounts, "stt": stt_info,
                          "audio_error": audio_err})
        s.commit()
        s.refresh(ev)
        return {"status": ra.status, "transcript": transcript, "language": src,
                "translation": {"text": tr.text, "language": wl, "source": tr.source, "amounts": tr.amounts},
                "audio_url": media_url(key), "audio_error": audio_err, "original_audio_url": media_url(orig_key),
                "event": _event_view(ev)}


@router.get("/e/{token}/payday.ics")
async def payday(token: str) -> Response:
    with db.session() as s:
        ra, ctx = _by_token(s, token)
        if ra.status not in ANSWERED:
            raise HTTPException(409, {"error": "not_agreed", "message": "no new wage agreed yet"})
        nums = {"start": ra.new_wage_from, "ask": ra.step_up_to or ra.new_wage,
                "step1": ra.new_wage if ra.step_up_to else None, "step_date": ra.step_up_from}
        ics = raise_core.payday_ics(worker=ctx.worker.name, nums=nums, uid=f"raise-{ra.id}")
        fname = "".join(ch for ch in ctx.worker.name.lower() if ch.isalnum()) or "worker"
        return Response(content=ics, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="payday-{fname}.ics"'})


# --------------------------------------------------------------------------- demo
class DemoIn(BaseModel):
    audio: bool = True
    plan: Literal["full", "step"] = "step"


def _mehta_case(s: Session) -> Case | None:
    for e in s.exec(select(Employer).where(Employer.name == "Mehta madam").order_by(Employer.id.desc())):
        c = s.exec(select(Case).where(Case.employer_id == e.id).order_by(Case.id.desc())).first()
        if c is not None:
            return c
    return None


@router.post("/demo")
async def demo(body: DemoIn = Body(default_factory=DemoIn)) -> dict:
    """Synthetic: Mehta madam's home (Rs 2,500 for 2 h a day), a fresh step-up request, ready to share.
    Seeds the demo story first only if it is missing (never wipes an existing one)."""
    from .. import seed  # import only

    today = _today()
    with db.session() as s:
        case = _mehta_case(s)
        empty = s.exec(select(Worker)).first() is None
    if case is None:
        if not empty:  # never wipe an existing story from here (POST /api/demo/reset does that, admin-only)
            raise HTTPException(409, {"error": "demo_missing",
                                      "message": "Mehta madam's home is not in this database; reset the demo first"})
        await run_in_threadpool(seed.reset)  # empty database: nothing to wipe
    with db.session() as s:
        case = _mehta_case(s)
        if case is None:
            raise HTTPException(500, "demo seed has no Mehta madam home")
        ctx = _ctx_or_404(s, case.id)
        ra = RaiseAsk(case_id=case.id, worker_id=ctx.worker.id, employer_id=ctx.employer.id,
                      case_token=case.employer_token, demo=True)
        # _compose_into makes the voice note (TTS) before its first write; the old asks are removed after
        # it, so no write transaction is held open across the Gnani call.
        await _compose_into(s, ra, ctx, ComposeIn(plan=body.plan, years_worked=DEMO_YEARS, use_llm=False,
                                                  audio=body.audio), today)
        for old in list(s.exec(select(RaiseAsk).where(RaiseAsk.case_id == case.id, RaiseAsk.id != ra.id))):
            for ev in list(s.exec(select(RaiseEvent).where(RaiseEvent.raise_id == old.id))):
                s.delete(ev)
            s.delete(old)
        s.commit()
        s.refresh(ra)
        return {"case_id": case.id, "worker_id": ctx.worker.id, "raise_id": ra.id, "token": ra.token,
                "worker_path": f"/raise/{case.id}", "employer_path": employer_path(ra.token),
                "raise": _raise_view(s, ra, ctx)}
