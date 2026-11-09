"""Exit Kit (W03 lite): "Madam said don't come from tomorrow."

  POST /api/exit                    {worker_id, employer_id | case_id, last_day?, days_worked_this_month?,
                                     monthly_wage?, transcript?, lang?} -> due date, what is owed, the gate
                                     checklist (cached audio only, never a new TTS call) and the plan for the
                                     normal Polite step (existing case/message endpoints)
  GET  /api/exit/{id}               the saved result again (checklist audio re-checked against the cache)
  GET  /api/exit/checklist?lang=    the 4-item checklist, cache lookup only
  POST /api/exit/checklist          {lang} speak the missing items through the Timbre cache (<= 4 calls per
                                     language, once ever); a TTS failure leaves audio_url null with tts_error
  GET  /api/exit/audio/{key}.ogg    a cached checklist clip

No new ladder step: the Polite message is the existing POST /api/cases/{id}/messages/polite, after the
case is given the exit amount through the existing POST /api/cases/{id}/confirm (or POST /api/cases).
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from .. import audio, db, safety, tts_cache, wages
from .. import exit_kit as ek
from ..gnani import GnaniError
from ..lang import extract_dates, today_ist
from ..models import Case, DiaryEntry, Employer, Worker
from .cases import calc_from_facts

router = APIRouter(prefix="/api/exit", tags=["exit"])


class ExitIn(BaseModel):
    worker_id: int
    employer_id: Optional[int] = None
    case_id: Optional[int] = None
    last_day: Optional[dt.date] = None             # default: from what she said, else today
    days_worked_this_month: Optional[float] = Field(None, ge=0, le=31)
    monthly_wage: Optional[float] = Field(None, gt=0, le=1_000_000)
    hours_per_day: Optional[float] = Field(None, gt=0, le=24)
    days_per_week: Optional[float] = Field(None, gt=0, le=7)
    transcript: str = Field("", max_length=4000)  # optional: what she said (from /api/cases/listen)
    lang: Optional[str] = None                     # checklist language (default: the worker's)


class ChecklistIn(BaseModel):
    lang: str = "te-IN"


# --------------------------------------------------------------------------- checklist audio
def _key(item: dict[str, str]) -> str:
    return tts_cache.cache_key(item["speech"].strip(), item["lang"], tts_cache.default_voice(item["lang"]))


def checklist(lang: str) -> list[dict[str, Any]]:
    """Cache lookup only: never spends a Gnani credit."""
    out = []
    for item in ek.checklist_texts(lang):
        key = _key(item)
        hit = tts_cache.lookup(key)
        out.append({"id": item["id"], "text": item["text"], "lang": item["lang"],
                    "audio_url": f"/api/exit/audio/{key}.ogg" if hit else None, "tts_error": None})
    return out


async def speak_checklist(lang: str) -> dict[str, Any]:
    """Synthesise the missing clips one at a time (the Gnani client holds the 1-active-request lock).
    A failed clip keeps its text and gets audio_url=None + tts_error; the page then shows text only."""
    items, calls = [], 0
    for item in ek.checklist_texts(lang):
        row: dict[str, Any] = {"id": item["id"], "text": item["text"], "lang": item["lang"],
                               "audio_url": None, "tts_error": None}
        try:
            entry = await tts_cache.synth(item["speech"], item["lang"])
            calls += 0 if entry.cached else 1
            row["audio_url"] = f"/api/exit/audio/{entry.key}.ogg"
            row["duration_s"] = round(entry.duration_s, 2)
        except (GnaniError, ValueError, audio.AudioError) as e:
            row["tts_error"] = e.as_dict() if isinstance(e, GnaniError) else str(e)[:200]
        items.append(row)
    return {"lang": ek.norm_lang(lang), "checklist": items, "tts_calls": calls,
            "fallback": "text" if any(r["audio_url"] is None for r in items) else None}


# --------------------------------------------------------------------------- helpers
def last_day_from(text: str, lang: str | None, today: dt.date) -> tuple[dt.date, str]:
    """"Repu nunchi raavaddu" (don't come from tomorrow) -> today is the last day. She can change it."""
    if text.strip():
        hint = {"te-IN": "te", "hi-en": "hinglish", "en-IN": "en"}.get(ek.norm_lang(lang))
        try:
            found = extract_dates(text, hint, today)
        except Exception:  # never let date parsing break the kit
            found = []
        for f in found:
            try:
                d = dt.date.fromisoformat(str(f["iso"])[:10])
            except (KeyError, ValueError):
                continue
            if d == today + dt.timedelta(days=1):
                return today, "from_tomorrow"
            if today - dt.timedelta(days=62) <= d <= today:
                return d, "said"
            if today < d <= today + dt.timedelta(days=31):
                return d - dt.timedelta(days=1), "day_before"
    return today, "today"


def _resolve(s: Session, body: ExitIn) -> tuple[Worker, Employer, Optional[Case]]:
    worker = s.get(Worker, body.worker_id)
    if worker is None:
        raise HTTPException(404, "worker not found")
    case = None
    if body.case_id is not None:
        case = s.get(Case, body.case_id)
        if case is None or case.worker_id != worker.id:
            raise HTTPException(404, "case not found for this worker")
    elif body.employer_id is not None:
        case = s.exec(select(Case).where(Case.worker_id == worker.id, Case.employer_id == body.employer_id)
                      .order_by(Case.id.desc())).first()  # type: ignore[union-attr]
    else:
        raise HTTPException(422, "send employer_id or case_id")
    employer = s.get(Employer, case.employer_id if case else body.employer_id)
    if employer is None:
        raise HTTPException(404, "employer not found")
    return worker, employer, case


def _view(row: ek.ExitKit, lang: str) -> dict[str, Any]:
    out = row.result()
    out["id"] = row.id
    out["lang"] = lang
    out["checklist"] = checklist(lang)
    out["checklist_audio"] = "cached" if all(c["audio_url"] for c in out["checklist"]) else "text_only"
    return out


# --------------------------------------------------------------------------- routes
@router.get("/checklist")
async def get_checklist(lang: str = Query("te-IN")) -> dict:
    items = checklist(lang)
    return {"lang": ek.norm_lang(lang), "checklist": items,
            "fallback": "text" if any(r["audio_url"] is None for r in items) else None}


@router.post("/checklist")
async def post_checklist(body: ChecklistIn) -> dict:
    return await speak_checklist(body.lang)


@router.get("/audio/{name}")
async def checklist_audio(name: str) -> Response:
    key, _, fmt = name.partition(".")
    fmt = fmt or "ogg"
    p = tts_cache.lookup(key, fmt) if fmt in ("ogg", "mp3") else None
    if p is None:
        raise HTTPException(404, "not cached")
    data = await run_in_threadpool(p.read_bytes)
    return Response(content=data, media_type="audio/ogg" if fmt == "ogg" else "audio/mpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("")
async def create_exit(body: ExitIn, s: Session = Depends(db.get_session)) -> dict:
    today = today_ist()
    worker, employer, case = _resolve(s, body)
    lang = ek.norm_lang(body.lang or worker.language)
    if body.last_day is not None:
        last_day, last_day_how = body.last_day, "given"
    else:
        last_day, last_day_how = last_day_from(body.transcript, lang, today)

    facts = case.facts() if case else {}
    clean = ek.clean_facts(facts)
    monthly = float(body.monthly_wage or (case.monthly_wage if case else 0) or clean.get("monthly_wage") or 0)
    if monthly <= 0:
        raise HTTPException(422, "monthly wage needed: send monthly_wage")
    dpw = float(body.days_per_week or (case.days_per_week if case else 0) or 6)
    hours = body.hours_per_day or (case.hours_per_day if case else None)
    category = case.category if case else wages.category_for(worker.work_type, worker.category)

    earlier, frozen = None, None
    if case is not None:
        # freeze the case's unpaid months first: "3 months unpaid" must not slide onto the dismissal month
        frozen = list(calc_from_facts(clean, today=today)["inputs"]["unpaid_months"])
        exit_facts = {**clean, "dismissed_on": last_day.isoformat()}
        if frozen and not clean.get("unpaid_months"):
            exit_facts["unpaid_months"] = frozen
        earlier = calc_from_facts(exit_facts, today=today)

    checkins = [e.timestamp for e in s.exec(select(DiaryEntry).where(
        DiaryEntry.worker_id == worker.id, DiaryEntry.employer_id == employer.id,
        DiaryEntry.kind == "checkin")).all()]

    result = ek.build(last_day=last_day, monthly_wage=monthly, days_per_week=dpw, hours_per_day=hours,
                      category=category, days_given=body.days_worked_this_month, checkin_dates=checkins,
                      start_date=case.start_date if case else None, earlier=earlier,
                      amount_paid=float(case.amount_paid or 0) if case else 0.0, case_facts=facts,
                      frozen_unpaid=frozen)
    result["last_day_how"] = last_day_how
    result["worker"] = {"id": worker.id, "name": worker.name, "language": worker.language}
    result["employer"] = {"id": employer.id, "name": employer.name, "language": employer.language,
                          "phone": employer.phone}
    result["case_id"] = case.id if case else None
    result["safety"] = safety.check_sync(body.transcript) if body.transcript.strip() else None

    patch = result.pop("case_facts_patch")
    lump = patch["exit_kit"]["lump"]
    if result["total"] <= 0:
        polite: dict[str, Any] = {"mode": "nothing_due"}
    elif case is not None:
        polite = {"mode": "update_case", "case_id": case.id,
                  "confirm": {"confirmed": True, "facts": patch},
                  "then": f"/api/cases/{case.id}/messages/polite"}
    else:
        polite = {"mode": "new_case",
                  "create": {"worker_id": worker.id, "employer_id": employer.id, "use_llm": False,
                             "facts": {"monthly_wage": monthly, "hours_per_day": hours, "days_per_week": dpw,
                                       "work_type": worker.work_type, "category": category,
                                       "owed_lumps": [lump] if lump > 0 else [],
                                       "dismissed_on": last_day.isoformat(), "dismissed": True,
                                       "exit_kit": patch["exit_kit"]}},
                  "then": "/api/cases/{id}/messages/polite"}
    result["polite"] = polite
    if ek.find_never_claims(result):  # belt and braces: law file section 8 B4
        raise HTTPException(500, "exit kit produced a claim Baaki never makes")

    row = ek.ExitKit(worker_id=worker.id, employer_id=employer.id, case_id=case.id if case else None,
                     last_day=last_day.isoformat(), due_by=result["due_by"], total=result["total"],
                     result_json=json.dumps({**result, "lang": lang}, ensure_ascii=False))
    s.add(row)
    s.commit()
    s.refresh(row)
    return _view(row, lang)


@router.get("/{exit_id}")
async def get_exit(exit_id: int, lang: Optional[str] = None, s: Session = Depends(db.get_session)) -> dict:
    row = s.get(ek.ExitKit, exit_id)
    if row is None:
        raise HTTPException(404, "exit kit not found")
    return _view(row, ek.norm_lang(lang or row.result().get("lang")))
