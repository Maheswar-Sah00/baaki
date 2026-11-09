"""Case engine routes: listen -> meter -> extract -> create -> read back -> confirm; dashboard; diary.

  POST /api/cases/listen              audio -> transcript, amount chips, running total, safety
  POST /api/cases/meter               text (or edited chips) -> chips and running total (no LLM, a few ms)
  POST /api/cases/extract             text -> proposed facts + calculation preview + read-back text
  POST /api/cases                     create the case from the transcript and/or confirmed facts
  GET  /api/cases/{id}                the case with items, calculation, employer, worker, payments, messages
  POST /api/cases/{id}/readback       read-back text + audio (Timbre, cached)
  POST /api/cases/{id}/confirm        the worker confirms (optionally with edited facts)
  GET  /api/workers/{id}/dashboard    one card per employer
  POST /api/diary                     a voice / text check-in, timestamped and SHA-256 hash-chained
  GET  /api/diary                     the chain for a worker (and employer), with verification
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from .. import audio, db, safety, storage, tts_cache, wages
from ..extract import extract_facts
from ..gnani import GnaniError
from ..lang import today_ist
from ..meter import meter, summarise
from ..models import Case, CaseItem, DiaryEntry, Employer, Message, Payment, Worker
from ..readback import build_readback
from ..stt_service import transcribe_upload

router = APIRouter(prefix="/api/cases", tags=["cases"])
workers_router = APIRouter(prefix="/api/workers", tags=["workers"])
diary_router = APIRouter(prefix="/api/diary", tags=["diary"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ACCEPTED_AUDIO = {"webm", "weba", "ogg", "opus", "oga", "mp3", "m4a", "mp4", "aac", "wav", "flac", "3gp", "amr"}
LANG_TO_STT = {"te-IN": "te", "te": "te", "hi-en": "hinglish", "hinglish": "hinglish", "hi-IN": "hinglish",
               "en-IN": "auto", "auto": "auto"}


# --------------------------------------------------------------------------- helpers
def _today() -> dt.date:
    return today_ist()


def _ext(upload: UploadFile) -> str:
    name = upload.filename or "upload"
    ext = audio.ext_of(name) or audio.ext_of("x." + (upload.content_type or "").split("/")[-1].split(";")[0])
    if ext not in ACCEPTED_AUDIO:
        raise HTTPException(415, f"unsupported audio type '{ext or upload.content_type}'")
    return ext


async def _read_audio(upload: UploadFile) -> tuple[bytes, str]:
    ext = _ext(upload)
    data = await upload.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "audio larger than 25 MB")
    return data, ext


async def _transcribe(data: bytes, ext: str, lang: str) -> dict[str, Any]:
    try:
        return await transcribe_upload(data, f"upload.{ext}", lang=LANG_TO_STT.get(lang, lang))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except audio.AudioError as e:
        raise HTTPException(415, f"could not decode audio: {e}")
    except GnaniError as e:
        raise HTTPException(503 if e.status == 429 else 502, detail=e.as_dict())


def _lang_hint(lang: str | None) -> str | None:
    return {"te-IN": "te", "te": "te", "hi-en": "hinglish", "hinglish": "hinglish", "hi-IN": "hi",
            "en-IN": "en", "en": "en"}.get(lang or "", None)


def calc_from_facts(facts: dict[str, Any], today: dt.date | None = None,
                    include_shortfall: bool = False) -> dict[str, Any]:
    """Facts (as confirmed) -> app.wages.calculate."""
    today = today or _today()
    deductions = []
    for d in facts.get("deductions") or []:
        deductions.append({"amount": d.get("amount") or 0, "reason": d.get("reason") or "other",
                           "days_absent": d.get("days_absent"), "month": d.get("month")})
    unpaid = list(facts.get("unpaid_months") or [])
    if not unpaid and facts.get("unpaid_month_numbers"):
        this_month = today.month
        for n in facts["unpaid_month_numbers"]:
            y = today.year if int(n) < this_month else today.year - 1
            unpaid.append(f"{y:04d}-{int(n):02d}")
    paid_months = dict(facts.get("paid_months") or {})
    calc = wages.calculate(
        monthly_wage=float(facts.get("monthly_wage") or 0),
        category=facts.get("category") or wages.category_for(facts.get("work_type")),
        work_type=facts.get("work_type"),
        hours_per_day=facts.get("hours_per_day"),
        days_per_week=float(facts.get("days_per_week") or 6),
        unpaid_months=unpaid or None,
        months_unpaid=facts.get("months_unpaid"),
        last_month=facts.get("last_unpaid_month"),
        paid_months=paid_months or None,
        deductions=deductions,
        advance_outstanding=float(facts.get("advance_outstanding") or 0),
        dismissed_on=facts.get("dismissed_on"),
        include_shortfall=include_shortfall or bool(facts.get("include_shortfall")),
        today=today,
    )
    lumps = [float(x) for x in facts.get("owed_lumps") or [] if x]
    if lumps:
        for v in lumps:
            calc["items"].append({"kind": "unpaid_wage", "label": "Other amount owed (as she said)", "month": None,
                                  "amount": v, "is_estimate": False, "included_in_total": True, "due_date": None,
                                  "source": wages.SRC_S17_1})
        calc["contractual_due"] = wages.money(calc["contractual_due"] + sum(lumps))
        calc["total"] = wages.money(calc["total"] + sum(lumps))
        calc["total_with_shortfall"] = wages.money(calc["total_with_shortfall"] + sum(lumps))
    return calc


def _write_items(s: Session, case: Case, calc: dict[str, Any]) -> None:
    for old in s.exec(select(CaseItem).where(CaseItem.case_id == case.id)).all():
        s.delete(old)
    for it in calc["items"]:
        s.add(CaseItem(case_id=case.id, kind=it["kind"], label=it["label"], month=it.get("month"),
                       amount=float(it["amount"]), is_estimate=bool(it.get("is_estimate")),
                       included_in_total=bool(it.get("included_in_total", True)), due_date=it.get("due_date"),
                       source=it.get("source") or ""))


def apply_calc(s: Session, case: Case, facts: dict[str, Any], include_shortfall: bool = False,
               today: dt.date | None = None) -> dict[str, Any]:
    """Recompute the case from facts and rewrite its items. Case.total_due == sum of included items."""
    facts = {**facts, "include_shortfall": include_shortfall or bool(facts.get("include_shortfall"))}
    calc = calc_from_facts(facts, today=today)
    case.facts_json = json.dumps(facts, ensure_ascii=False)
    case.calc_json = json.dumps(calc, ensure_ascii=False)
    case.total_due = calc["total"]
    case.shortfall_estimate = calc["min_wage_shortfall"]
    case.monthly_wage = float(facts.get("monthly_wage") or 0)
    if facts.get("hours_per_day"):
        case.hours_per_day = float(facts["hours_per_day"])
    case.days_per_week = float(facts.get("days_per_week") or 6)
    case.months_unpaid = float(len(calc["inputs"]["unpaid_months"]))
    case.work_type = facts.get("work_type") or case.work_type
    case.category = calc["inputs"]["category"]
    case.dismissed = bool(facts.get("dismissed_on") or facts.get("dismissed"))
    case.end_date = facts.get("dismissed_on")
    case.updated_at = db.now_iso()
    s.add(case)
    s.flush()
    _write_items(s, case, calc)
    return calc


def case_json(s: Session, case: Case) -> dict[str, Any]:
    worker = s.get(Worker, case.worker_id)
    employer = s.get(Employer, case.employer_id)
    items = s.exec(select(CaseItem).where(CaseItem.case_id == case.id).order_by(CaseItem.id)).all()
    pays = s.exec(select(Payment).where(Payment.case_id == case.id).order_by(Payment.id)).all()
    msgs = s.exec(select(Message).where(Message.case_id == case.id).order_by(Message.id)).all()
    facts = case.facts()
    rb = build_readback(facts, worker.language if worker else "te-IN", legal_total=case.total_due)
    return {
        "id": case.id, "status": case.status, "worker": worker.model_dump() if worker else None,
        "employer": employer.model_dump() if employer else None,
        "work_type": case.work_type, "category": case.category, "monthly_wage": case.monthly_wage,
        "hours_per_day": case.hours_per_day, "days_per_week": case.days_per_week,
        "months_unpaid": case.months_unpaid, "dismissed": case.dismissed, "end_date": case.end_date,
        "transcript": case.transcript, "transcript_lang": case.transcript_lang,
        "facts": facts, "calc": case.calc(), "safety": json.loads(case.safety_json or "{}"),
        "total_due": case.total_due, "shortfall_estimate": case.shortfall_estimate,
        "amount_paid": case.amount_paid, "balance": case.balance,
        "items": [i.model_dump() for i in items],
        "payments": [p.model_dump() for p in pays],
        "messages": [m.model_dump() for m in msgs],
        "employer_token": case.employer_token, "employer_path": f"/e/{case.employer_token}",
        "readback": rb, "readback_confirmed": case.readback_confirmed, "confirmed_at": case.confirmed_at,
        "created_at": case.created_at, "updated_at": case.updated_at,
    }


def _get_case(s: Session, case_id: int) -> Case:
    case = s.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    return case


# --------------------------------------------------------------------------- listen / meter / extract
@router.post("/listen")
async def listen(audio_file: UploadFile = File(..., alias="audio"), lang: str = Form("auto"),
                 use_llm: bool = Form(True)) -> dict:
    """Audio -> transcript + Baaki Meter chips + safety. lang: te | hinglish | auto | te-IN | hi-en."""
    data, ext = await _read_audio(audio_file)
    stt = await _transcribe(data, ext, lang)
    text = stt["transcript"]
    m = meter(text, _lang_hint(lang))
    sf = await safety.check(text, use_llm=use_llm)
    return {"transcript": text, "language_code": stt["language_code"],
            "detected_language_code": stt.get("detected_language_code"), "mode": stt["mode"],
            "duration_s": stt["duration_s"], "chunks": stt["chunks"], "meter": m, "chips": m["chips"],
            "total": m["total"], "steps": m["steps"], "safety": sf}


class MeterIn(BaseModel):
    text: str = Field("", max_length=8000)
    lang: Optional[str] = None
    chips: Optional[list[dict[str, Any]]] = None  # edited chips: re-total without re-parsing


@router.post("/meter")
async def meter_route(body: MeterIn) -> dict:
    if body.chips is not None:
        out = summarise([dict(c) for c in body.chips])
        return {"text": body.text, "lang": body.lang, "chips": body.chips, **out}
    out = meter(body.text, _lang_hint(body.lang) or body.lang)
    out["safety"] = safety.check_sync(body.text)
    return out


class ExtractIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    lang: Optional[str] = None
    worker_lang: Optional[str] = None
    use_llm: bool = True
    include_shortfall: bool = False


@router.post("/extract")
async def extract_route(body: ExtractIn) -> dict:
    out = await extract_facts(body.text, _lang_hint(body.lang) or body.lang, use_llm=body.use_llm)
    calc = calc_from_facts(out["facts"], include_shortfall=body.include_shortfall)
    out["calc"] = calc
    out["readback"] = build_readback(out["facts"], body.worker_lang or body.lang or "te-IN", legal_total=calc["total"])
    return out


# --------------------------------------------------------------------------- create / get
class EmployerIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    language: Literal["hi-en", "te-IN", "hi-IN", "en-IN"] = "hi-en"
    phone: Optional[str] = None
    locality: Optional[str] = None


class CaseIn(BaseModel):
    worker_id: int
    employer_id: Optional[int] = None
    employer: Optional[EmployerIn] = None
    transcript: str = Field("", max_length=8000)
    lang: Optional[str] = None
    facts: Optional[dict[str, Any]] = None  # confirmed / edited facts override the extracted ones
    include_shortfall: bool = False
    use_llm: bool = True


@router.post("")
async def create_case(body: CaseIn, s: Session = Depends(db.get_session)) -> dict:
    worker = s.get(Worker, body.worker_id)
    if worker is None:
        raise HTTPException(404, "worker not found")
    facts: dict[str, Any] = {}
    warnings: list[str] = []
    source = "manual"
    if body.transcript.strip():
        ex = await extract_facts(body.transcript, _lang_hint(body.lang) or _lang_hint(worker.language),
                                 use_llm=body.use_llm)
        facts, warnings, source = ex["facts"], ex["warnings"], ex["source"]
    if body.facts:
        facts.update({k: v for k, v in body.facts.items() if v is not None})
    if not facts.get("monthly_wage"):
        raise HTTPException(422, "no monthly wage found: say or type the salary per month")
    if body.employer_id is not None:
        employer = s.get(Employer, body.employer_id)
        if employer is None:
            raise HTTPException(404, "employer not found")
    else:
        name = (body.employer.name if body.employer else None) or facts.get("employer_name") or "Employer"
        employer = Employer(name=name, language=body.employer.language if body.employer else "hi-en",
                            phone=body.employer.phone if body.employer else None,
                            locality=body.employer.locality if body.employer else None)
        s.add(employer)
        s.flush()
    sf = safety.check_sync(body.transcript)
    case = Case(worker_id=worker.id, employer_id=employer.id, transcript=body.transcript,
                transcript_lang=body.lang or worker.language, safety_json=json.dumps(sf, ensure_ascii=False),
                work_type=facts.get("work_type") or worker.work_type)
    s.add(case)
    s.flush()
    facts["extraction"] = {"source": source, "warnings": warnings}
    apply_calc(s, case, facts, include_shortfall=body.include_shortfall)
    s.commit()
    s.refresh(case)
    return case_json(s, case)


@router.get("/{case_id}")
async def get_case(case_id: int, s: Session = Depends(db.get_session)) -> dict:
    return case_json(s, _get_case(s, case_id))


# --------------------------------------------------------------------------- read-back / confirm
class ReadbackIn(BaseModel):
    lang: Optional[Literal["te-IN", "hi-en", "hi-IN", "en-IN"]] = None
    voice: Optional[str] = None
    audio: bool = True  # False: text only (no Gnani call)


@router.post("/{case_id}/readback")
async def readback(case_id: int, body: Optional[ReadbackIn] = None, format: str = Query("json"),
                   s: Session = Depends(db.get_session)):
    """Read-back in the worker's language. JSON {text, plain, audio_url, ...}; ?format=ogg returns the audio."""
    body = body or ReadbackIn()
    case = _get_case(s, case_id)
    worker = s.get(Worker, case.worker_id)
    lang = body.lang or (worker.language if worker else "te-IN")
    rb = build_readback(case.facts(), lang, legal_total=case.total_due)
    out: dict[str, Any] = {**rb, "audio_url": None, "duration_s": None, "cached": None, "tts_error": None}
    if not body.audio and format == "json":
        return out
    try:
        entry = await tts_cache.synth(rb["text"], rb["lang"], body.voice)
    except (GnaniError, ValueError, audio.AudioError) as e:
        err = e.as_dict() if isinstance(e, GnaniError) else str(e)
        if format != "json":
            raise HTTPException(502, detail={"error": "readback_tts_failed", "detail": err})
        out["tts_error"] = err
        return out
    data = await run_in_threadpool(entry.path.read_bytes)
    if format in ("ogg", "audio"):
        return Response(content=data, media_type="audio/ogg",
                        headers={"X-Duration-S": f"{entry.duration_s:.2f}", "X-TTS-Cache": "hit" if entry.cached else "miss"})
    key = f"c{case.id}/readback_{entry.key[:16]}.{entry.fmt}"
    st = storage.get_storage()
    if st.local_path(key) is None:
        st.put(key, data)
    out.update(audio_url=f"/api/media/{key}", duration_s=round(entry.duration_s, 2), cached=entry.cached)
    return out


class ConfirmIn(BaseModel):
    confirmed: bool = True
    facts: Optional[dict[str, Any]] = None
    include_shortfall: Optional[bool] = None


@router.post("/{case_id}/confirm")
async def confirm(case_id: int, body: Optional[ConfirmIn] = None, s: Session = Depends(db.get_session)) -> dict:
    body = body or ConfirmIn()
    case = _get_case(s, case_id)
    if body.facts or body.include_shortfall is not None:
        facts = {**case.facts(), **{k: v for k, v in (body.facts or {}).items() if v is not None}}
        inc = body.include_shortfall if body.include_shortfall is not None else bool(facts.get("include_shortfall"))
        apply_calc(s, case, facts, include_shortfall=inc)
    if body.confirmed:
        case.readback_confirmed = True
        case.confirmed_at = db.now_iso()
        if case.status == "draft":
            case.status = "confirmed"
    case.updated_at = db.now_iso()
    s.add(case)
    s.commit()
    s.refresh(case)
    return case_json(s, case)


# --------------------------------------------------------------------------- dashboard
def _card(s: Session, case: Case) -> dict[str, Any]:
    emp = s.get(Employer, case.employer_id)
    msgs = s.exec(select(Message).where(Message.case_id == case.id, Message.direction == "to_employer")
                  .order_by(Message.id)).all()
    planned = s.exec(select(Payment).where(Payment.case_id == case.id, Payment.status == "planned")
                     .order_by(Payment.due_date)).all()
    last = msgs[-1] if msgs else None
    balance = case.balance
    if case.status in ("paid", "closed") or (case.total_due > 0 and balance <= 0):
        state = "paid"
    elif case.amount_paid > 0:
        state = "partly_paid"
    elif case.total_due <= 0:
        state = "below_minimum" if case.shortfall_estimate > 0 else "clear"
    elif last is not None:
        sent = (last.sent_at or last.created_at or "")[:10]
        try:
            age = (_today() - dt.date.fromisoformat(sent)).days
        except ValueError:
            age = 0
        state = "ignored" if age >= 7 and last.status != "replied" else "sent"
    else:
        state = case.status  # draft | confirmed | plan
    next_reminder = planned[0].due_date if planned else None
    if next_reminder is None and last is not None and state in ("sent", "ignored"):
        try:
            next_reminder = (dt.date.fromisoformat((last.sent_at or last.created_at)[:10])
                             + dt.timedelta(days=7)).isoformat()
        except ValueError:
            next_reminder = None
    calc = case.calc()
    return {
        "case_id": case.id, "employer": emp.model_dump() if emp else None,
        "fair_employer": bool(emp and emp.fair_employer), "status": case.status, "state": state,
        "total_due": case.total_due, "amount_paid": case.amount_paid, "balance": balance,
        "shortfall_estimate": case.shortfall_estimate,
        "haq_check": calc.get("haq_check"), "monthly_wage": case.monthly_wage, "hours_per_day": case.hours_per_day,
        "months_unpaid": case.months_unpaid,
        "last_step": last.step if last else None, "last_sent_at": (last.sent_at or last.created_at) if last else None,
        "next_reminder": next_reminder, "employer_path": f"/e/{case.employer_token}",
        "earliest_overdue": (calc.get("due") or {}).get("earliest_overdue"),
    }


@workers_router.get("/{worker_id}/dashboard")
async def dashboard(worker_id: int, s: Session = Depends(db.get_session)) -> dict:
    worker = s.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(404, "worker not found")
    cases = s.exec(select(Case).where(Case.worker_id == worker_id).order_by(Case.id)).all()
    cards = [_card(s, c) for c in cases]
    return {
        "worker": worker.model_dump(),
        "cards": cards,
        "totals": {"homes": len({c["employer"]["id"] for c in cards if c["employer"]}),
                   "baaki": wages.money(sum(c["balance"] for c in cards)),
                   "recovered": wages.money(sum(c["amount_paid"] for c in cards)),
                   "hidden_baaki_estimate": wages.money(sum(c["shortfall_estimate"] for c in cards))},
    }


@workers_router.get("/{worker_id}")
async def get_worker(worker_id: int, s: Session = Depends(db.get_session)) -> dict:
    worker = s.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(404, "worker not found")
    return worker.model_dump()


# --------------------------------------------------------------------------- diary (hash chain)
def entry_hash(prev_hash: str, e: DiaryEntry) -> str:
    canon = json.dumps({"worker_id": e.worker_id, "employer_id": e.employer_id, "case_id": e.case_id,
                        "timestamp": e.timestamp, "kind": e.kind, "text": e.text, "audio_sha256": e.audio_sha256},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canon}".encode("utf-8")).hexdigest()


def add_diary_entry(s: Session, worker_id: int, text: str, *, employer_id: int | None = None,
                    case_id: int | None = None, kind: str = "checkin", audio_sha256: str | None = None,
                    timestamp: str | None = None) -> DiaryEntry:
    """Append to the worker's chain: hash = sha256(prev_hash | canonical JSON of the entry)."""
    prev = s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == worker_id)
                  .order_by(DiaryEntry.id.desc())).first()  # type: ignore[union-attr]
    e = DiaryEntry(worker_id=worker_id, employer_id=employer_id, case_id=case_id, kind=kind, text=text,
                   audio_sha256=audio_sha256, timestamp=timestamp or db.now_iso(), prev_hash=prev.hash if prev else "")
    e.hash = entry_hash(e.prev_hash, e)
    s.add(e)
    s.flush()
    return e


def verify_chain(entries: list[DiaryEntry]) -> dict[str, Any]:
    prev = ""
    for e in entries:
        if e.prev_hash != prev or entry_hash(e.prev_hash, e) != e.hash:
            return {"valid": False, "broken_at": e.id, "head": None, "count": len(entries)}
        prev = e.hash
    return {"valid": True, "broken_at": None, "head": prev or None, "count": len(entries)}


@diary_router.post("")
async def diary_add(worker_id: int = Form(...), text: str = Form(""), employer_id: Optional[int] = Form(None),
                    case_id: Optional[int] = Form(None), kind: str = Form("checkin"), lang: str = Form("auto"),
                    audio_file: Optional[UploadFile] = File(None, alias="audio"),
                    s: Session = Depends(db.get_session)) -> dict:
    """Voice (or text) check-in: "Aaj Sharma ji ke ghar, do ghante". The audio is hashed (sha256), not kept."""
    if s.get(Worker, worker_id) is None:
        raise HTTPException(404, "worker not found")
    if kind not in ("checkin", "absence", "payment", "note"):
        raise HTTPException(400, "kind must be checkin | absence | payment | note")
    audio_sha = None
    if audio_file is not None:
        data, ext = await _read_audio(audio_file)
        audio_sha = db.sha256_hex(data)
        if not text.strip():
            text = (await _transcribe(data, ext, lang))["transcript"]
    if not text.strip() and audio_sha is None:
        raise HTTPException(400, "send text or audio")
    e = add_diary_entry(s, worker_id, text.strip(), employer_id=employer_id, case_id=case_id, kind=kind,
                        audio_sha256=audio_sha)
    s.commit()
    s.refresh(e)
    hours = meter(e.text)["hours_per_day"] if e.text else None
    return {"entry": e.model_dump(), "hours": hours}


@diary_router.get("")
async def diary_list(worker_id: int, employer_id: Optional[int] = None, s: Session = Depends(db.get_session)) -> dict:
    all_entries = list(s.exec(select(DiaryEntry).where(DiaryEntry.worker_id == worker_id).order_by(DiaryEntry.id)).all())
    shown = [e for e in all_entries if employer_id is None or e.employer_id == employer_id]
    return {"entries": [e.model_dump() for e in shown], "chain": verify_chain(all_entries)}


ROUTERS = [router, workers_router, diary_router]
