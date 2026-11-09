"""Baaki for every promise: the second door. Anyone owed small sums that keep sliding ("next month, first week",
"by the end of this week"): the milkman, the paper boy, the dhobi, or a chit member waiting on an agent.

  POST /api/dues/parse                 multipart text | audio, lang?, kind?, party? -> chips + total (+ a promise), no writes
  POST /api/dues                       JSON: worker_id, kind, party_name, party_lang, owner_name, items[], promise_text?
  GET  /api/dues?worker_id=&as_of=     people who owe this worker, by kind, with totals and broken-promise counts
                                       (accounts belong to a worker through DuesOwner; without worker_id only
                                       accounts that belong to nobody are listed, never another worker's)
  GET  /api/dues/{id}?as_of=           items, promise log (hash-chained), counter, reminder/pack availability
  POST /api/dues/{id}/items            JSON items[] (more owed)          POST /api/dues/{id}/paid   JSON amount
  POST /api/dues/{id}/promises         multipart text | audio, said_on?, lang?, due_date? -> a dated, chained entry
  POST /api/dues/promises/{pid}/status kept | broken | pending
  POST /api/dues/{id}/remind           polite reminder in the other party's language (+ voice note, UPI, wa.me)
  GET  /api/dues/{id}/pack.pdf         record pack (chit / other, after 3 broken promises)
  POST /api/dues/demo?worker_id=       synthetic demo: Ramu's milk bill, Lakshmi's chit money (owned by Lakshmi)
  DELETE /api/dues/{id}

Nothing is sent from here. Amounts come from app.lang only (never an LLM); every reminder is re-checked.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Literal, Optional
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audio, db, storage, voice_note
from ..dues_core import (KINDS, LANGS, PACK_MIN_BROKEN, counter, item_label, lang_of, log_hash, name_of, norm_kind,
                         pack_blocks, pack_eligible, parse_items, parse_promise, promise_status, reminder, verify_log)
from .. import clock
from ..dues_models import DuesAccount, DuesItem, DuesLog, DuesOwner, DuesPromise
from ..gnani import GnaniError
from ..models import Worker
from ..messages import MONTHS, disclosure, fmt_date, fmt_money, norm_lang, tts_lang, upi_link
from ..pdf import render_pdf
from ..stt_service import transcribe_upload
from .employer import ACCEPTED_AUDIO, MAX_UPLOAD_BYTES, STT_FOR

log = logging.getLogger("dues")
router = APIRouter(prefix="/api/dues", tags=["dues"])

MAX_TEXT = 2000
AUTO_STT = ("te-IN,hi-IN,en-IN", "codemix")


def _today() -> dt.date:
    return clock.today()


# ------------------------------------------------------------------ ownership (DuesOwner)
def _owner_of(s: Session, account_id: int) -> Optional[int]:
    o = s.get(DuesOwner, account_id)
    return o.worker_id if o else None


def _set_owner(s: Session, account_id: int, worker_id: Optional[int]) -> None:
    if worker_id is None:
        return
    s.merge(DuesOwner(account_id=account_id, worker_id=worker_id))


def _check_worker(s: Session, worker_id: Optional[int]) -> None:
    if worker_id is not None and s.get(Worker, worker_id) is None:
        raise HTTPException(404, {"error": "no_worker", "message": "worker not found"})


def _accounts_for(s: Session, worker_id: Optional[int]) -> list[DuesAccount]:
    """This worker's accounts (newest first); worker_id None = accounts that belong to nobody."""
    owners = {o.account_id: o.worker_id for o in s.exec(select(DuesOwner)).all()}
    accts = s.exec(select(DuesAccount).order_by(DuesAccount.id.desc())).all()
    return [a for a in accts if owners.get(a.id) == worker_id]


def _demo_owner(s: Session, worker_id: Optional[int]) -> Optional[int]:
    """The demo accounts belong to the given worker, else to the seeded Lakshmi, else to nobody."""
    if worker_id is not None:
        _check_worker(s, worker_id)
        return worker_id
    w = s.exec(select(Worker).where(Worker.name == "Lakshmi").order_by(Worker.id)).first()
    return w.id if w else None


def _as_of(as_of: Optional[str]) -> dt.date:
    if not as_of:
        return _today()
    try:
        return dt.date.fromisoformat(as_of[:10])
    except ValueError:
        raise HTTPException(400, "as_of must be an ISO date")


def _iso_day(x: Optional[str], name: str, default: dt.date) -> dt.date:
    if not x:
        return default
    try:
        return dt.date.fromisoformat(x[:10])
    except ValueError:
        raise HTTPException(400, f"{name} must be an ISO date")


def _lang_in(x: Optional[str]) -> Optional[str]:
    v = (x or "").strip().lower()
    if v in ("", "auto", "unknown"):
        return None
    if v in ("te", "te-in", "telugu"):
        return "te-IN"
    if v in ("hinglish", "hi-en", "hi", "hi-in", "hindi"):
        return "hi-en"
    if v in ("en", "en-in", "english"):
        return "en"
    raise HTTPException(400, "lang must be te | hinglish | en | auto")


# ------------------------------------------------------------------ chain
def _append(s: Session, account_id: int, kind: str, said_on: str, text: str, data: dict[str, Any]) -> DuesLog:
    prev = s.exec(select(DuesLog).where(DuesLog.account_id == account_id).order_by(DuesLog.id.desc())).first()
    e = DuesLog(account_id=account_id, kind=kind, said_on=said_on, text=text,
                data_json=json.dumps(data, ensure_ascii=False, sort_keys=True), prev_hash=prev.hash if prev else "")
    e.hash = log_hash(e.prev_hash, e.model_dump())
    s.add(e)
    s.flush()
    return e


def _chain(s: Session, account_id: int) -> dict[str, Any]:
    logs = s.exec(select(DuesLog).where(DuesLog.account_id == account_id).order_by(DuesLog.id)).all()
    return verify_log([e.model_dump() for e in logs])


# ------------------------------------------------------------------ STT
async def _read_audio(upload: UploadFile) -> tuple[bytes, str]:
    name = upload.filename or "clip"
    ext = audio.ext_of(name) or audio.ext_of("x." + (upload.content_type or "").split("/")[-1].split(";")[0])
    if ext not in ACCEPTED_AUDIO:
        raise HTTPException(415, f"unsupported audio type '{ext or upload.content_type}'")
    data = await upload.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "audio larger than 25 MB")
    return data, ("ogg" if ext == "opus" else ext)


async def _transcribe(upload: UploadFile, lang: Optional[str]) -> dict[str, Any]:
    data, ext = await _read_audio(upload)
    codes, mode = STT_FOR[lang] if lang else AUTO_STT
    try:
        stt = await transcribe_upload(data, f"dues.{ext}", lang=codes, mode=mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except audio.AudioError as e:
        raise HTTPException(415, f"could not decode audio: {e}")
    except GnaniError as e:
        raise HTTPException(503 if e.status == 429 else 502, e.as_dict())
    text = (stt.get("transcript") or "").strip()
    if not text:
        raise HTTPException(422, {"error": "no_speech", "message": "nothing was heard; please try again"})
    return {"transcript": text, "language_code": stt.get("language_code"),
            "detected_language_code": stt.get("detected_language_code"), "mode": stt.get("mode")}


async def _text_or_audio(text: str, upload: Optional[UploadFile], lang: Optional[str]) -> tuple[str, dict | None]:
    text = (text or "").strip()
    if upload is None and not text:
        raise HTTPException(400, "speak (audio) or type (text)")
    if len(text) > MAX_TEXT:
        raise HTTPException(413, f"text longer than {MAX_TEXT} characters")
    if upload is not None:
        stt = await _transcribe(upload, lang)
        return stt["transcript"], stt
    return text, None


# ------------------------------------------------------------------ views
def _account(s: Session, account_id: int) -> DuesAccount:
    a = s.get(DuesAccount, account_id)
    if a is None:
        raise HTTPException(404, "not found")
    return a


def _hash_of(s: Session, log_id: Optional[int]) -> str:
    e = s.get(DuesLog, log_id) if log_id else None
    return e.hash if e else ""


def account_view(s: Session, a: DuesAccount, as_of: dt.date) -> dict[str, Any]:
    items_all = s.exec(select(DuesItem).where(DuesItem.account_id == a.id).order_by(DuesItem.said_on, DuesItem.id)).all()
    items = [i for i in items_all if i.said_on <= as_of.isoformat()]
    idicts = [{"kind": i.kind, "amount": i.amount, "said_on": i.said_on} for i in items]
    iv = [{"id": i.id, "kind": i.kind, "label": i.label, "item_key": i.item_key, "month": i.month, "amount": i.amount,
           "amount_display": fmt_money(i.amount), "source_text": i.source_text, "said_on": i.said_on,
           "display": {l: (item_label(i.item_key, i.month, i.label, l, a.kind) if i.kind == "due" else
                           {"en": "Received", "hi-en": "मिला", "te-IN": "అందింది"}[l]) for l in LANGS},
           "hash": _hash_of(s, i.log_id)} for i in items]
    total_due = round(sum(i.amount for i in items if i.kind == "due"), 2)
    total_paid = round(sum(i.amount for i in items if i.kind == "paid"), 2)
    balance = round(max(total_due - total_paid, 0), 2)
    ps_all = s.exec(select(DuesPromise).where(DuesPromise.account_id == a.id)
                    .order_by(DuesPromise.said_on, DuesPromise.id)).all()
    pv = []
    for p in ps_all:
        if p.said_on > as_of.isoformat():
            continue
        d = {"id": p.id, "said_on": p.said_on, "due_date": p.due_date, "range_start": p.range_start,
             "precision": p.precision, "phrase": p.phrase, "quote": p.quote, "lang": p.lang, "amount": p.amount,
             "amount_display": fmt_money(p.amount) if p.amount else None, "source": p.source,
             "stored_status": p.status, "status": p.status, "status_at": p.status_at, "hash": _hash_of(s, p.log_id)}
        d["status"] = promise_status(d, as_of, idicts)
        d["said_display"] = {l: fmt_date(p.said_on, l, year=False) for l in LANGS}
        d["due_display"] = {l: fmt_date(p.due_date, l, year=False) for l in LANGS}
        pv.append(d)
    c = counter(pv, as_of)
    last = pv[-1] if pv else None
    upi = upi_link(a.owner_vpa, a.owner_name, balance) if a.kind == "vendor" and balance > 0 else None
    return {
        "account": {"id": a.id, "kind": a.kind, "title": a.title, "party_name": a.party_name,
                    "party_lang": a.party_lang, "party_phone": a.party_phone, "owner_name": a.owner_name,
                    "owner_lang": a.owner_lang, "owner_vpa": a.owner_vpa, "note": a.note, "demo": a.demo,
                    "created_at": a.created_at,
                    "party_display": {l: name_of(a.party_name, l) for l in LANGS}},
        "as_of": as_of.isoformat(),
        "items": iv, "total_due": total_due, "total_paid": total_paid, "balance": balance,
        "balance_display": fmt_money(balance),
        "promises": pv, "last_promise": last, "counter": c,
        "chain": _chain(s, a.id),
        "upi_url": upi,
        "pack": {"eligible": pack_eligible(a.kind, c["broken"]) and balance > 0, "min_broken": PACK_MIN_BROKEN,
                 "applies": a.kind in ("chit", "other"), "url": f"/api/dues/{a.id}/pack.pdf"},
        "can_remind": balance > 0,
    }


def summary_view(v: dict[str, Any]) -> dict[str, Any]:
    a, c = v["account"], v["counter"]
    return {"id": a["id"], "kind": a["kind"], "title": a["title"], "party_name": a["party_name"],
            "party_display": a["party_display"], "party_lang": a["party_lang"], "owner_name": a["owner_name"],
            "balance": v["balance"], "balance_display": v["balance_display"], "items": len(v["items"]),
            "item_labels": [i["display"] for i in v["items"] if i["kind"] == "due"][:3],
            "promises_made": c["made"], "promises_broken": c["broken"], "first_promised": c["first_promised"],
            "months_ago": c["months_ago"], "last_due": v["last_promise"]["due_date"] if v["last_promise"] else None,
            "last_status": v["last_promise"]["status"] if v["last_promise"] else None,
            "pack_eligible": v["pack"]["eligible"], "demo": a["demo"]}


# ------------------------------------------------------------------ parse (no writes)
@router.post("/parse")
async def parse(audio_file: Optional[UploadFile] = File(None, alias="audio"), text: str = Form(""),
                lang: Optional[str] = Form(None), kind: str = Form("vendor"), party: str = Form(""),
                said_on: Optional[str] = Form(None)) -> dict:
    """Speak or type what is owed -> chips and a running total (app.lang). A promise in the same words is shown too."""
    lg = _lang_in(lang)
    words, stt = await _text_or_audio(text, audio_file, lg)
    out = parse_items(words, lg or "auto", norm_kind(kind), party)
    said = _iso_day(said_on, "said_on", _today())
    out.update({"transcript": words, "stt": stt, "promise": parse_promise(words, out["lang"], said),
                "kind": norm_kind(kind)})
    return out


# ------------------------------------------------------------------ create / list
class ItemIn(BaseModel):
    label: str = Field("", max_length=120)
    amount: float = Field(..., gt=0, le=10_000_000)
    item_key: Optional[str] = None
    month: Optional[int] = Field(None, ge=1, le=12)
    source_text: str = Field("", max_length=200)
    said_on: Optional[str] = None


class AccountIn(BaseModel):
    worker_id: Optional[int] = None            # the worker this account belongs to (the UI always sends it)
    kind: Literal["vendor", "chit", "other"] = "vendor"
    party_name: str = Field(..., min_length=1, max_length=80)
    party_lang: str = "hi-en"
    party_phone: Optional[str] = Field(None, max_length=20)
    owner_name: str = Field("", max_length=80)
    owner_lang: str = "hi-en"
    owner_vpa: Optional[str] = Field(None, max_length=80)
    title: str = Field("", max_length=80)
    note: str = Field("", max_length=300)
    items: list[ItemIn] = Field(default_factory=list, max_length=30)
    said_on: Optional[str] = None
    promise_text: Optional[str] = Field(None, max_length=MAX_TEXT)


def _add_item(s: Session, a: DuesAccount, it: ItemIn, default_day: dt.date, kind: str = "due") -> DuesItem:
    day = _iso_day(it.said_on, "said_on", default_day).isoformat()
    label = (it.label or "").strip() or item_label(it.item_key, it.month, "", a.owner_lang, a.kind)
    key = it.item_key if it.item_key in (None, "milk", "paper", "ironing", "vegetables", "water", "chit", "loan",
                                         "savings") else None
    e = _append(s, a.id, kind, day, f"{label}: {fmt_money(it.amount)} {'owed' if kind == 'due' else 'received'}",
                {"label": label, "amount": round(it.amount, 2), "item_key": key, "month": it.month,
                 "source_text": it.source_text})
    item = DuesItem(account_id=a.id, kind=kind, label=label, item_key=key, month=it.month,
                    amount=round(it.amount, 2), source_text=it.source_text, said_on=day, log_id=e.id)
    s.add(item)
    s.flush()
    return item


def _add_promise(s: Session, a: DuesAccount, words: str, said: dt.date, lang: Optional[str], source: str = "text",
                 due_override: Optional[str] = None) -> DuesPromise:
    p = parse_promise(words, lang or a.party_lang, said)
    if due_override:
        d = _iso_day(due_override, "due_date", said)
        p = {**(p or {"phrase": "", "quote": words, "lang": lang_of(words, lang or a.party_lang), "amount": None}),
             "due_date": d.isoformat(), "range_start": None, "precision": "day"}
    if p is None:
        raise HTTPException(422, {"error": "no_date", "message": "no date heard in those words; pick the date"})
    e = _append(s, a.id, "promise", said.isoformat(),
                f"{a.party_name} said on {fmt_date(said, 'en')}: “{words}” -> by {fmt_date(p['due_date'], 'en')}",
                {"quote": words, "due_date": p["due_date"], "phrase": p["phrase"], "amount": p["amount"]})
    row = DuesPromise(account_id=a.id, said_on=said.isoformat(), due_date=p["due_date"], range_start=p["range_start"],
                      precision=p["precision"], phrase=p["phrase"], quote=words, lang=p["lang"], amount=p["amount"],
                      source=source, log_id=e.id)
    s.add(row)
    s.flush()
    return row


@router.post("")
async def create(body: AccountIn) -> dict:
    said = _iso_day(body.said_on, "said_on", _today())
    with db.session() as s:
        _check_worker(s, body.worker_id)
        a = DuesAccount(kind=body.kind, title=body.title.strip(), party_name=body.party_name.strip(),
                        party_lang=norm_lang(body.party_lang), party_phone=(body.party_phone or "").strip() or None,
                        owner_name=body.owner_name.strip(), owner_lang=norm_lang(body.owner_lang),
                        owner_vpa=(body.owner_vpa or "").strip() or None, note=body.note.strip())
        s.add(a)
        s.flush()
        _set_owner(s, a.id, body.worker_id)
        _append(s, a.id, "account", said.isoformat(), f"{a.owner_name or 'User'} is owed money by {a.party_name}",
                {"kind": a.kind, "title": a.title, "party": a.party_name})
        for it in body.items:
            _add_item(s, a, it, said)
        if body.promise_text and body.promise_text.strip():
            _add_promise(s, a, body.promise_text.strip(), said, None)
        s.commit()
        return account_view(s, a, _today())


@router.get("")
async def list_dues(as_of: Optional[str] = Query(None), worker_id: Optional[int] = Query(None)) -> dict:
    day = _as_of(as_of)
    with db.session() as s:
        _check_worker(s, worker_id)
        accts = _accounts_for(s, worker_id)
        rows = [summary_view(account_view(s, a, day)) for a in accts]
        by_kind = {k: {"count": 0, "balance": 0.0, "broken": 0} for k in KINDS}
        for r in rows:
            b = by_kind[r["kind"]]
            b["count"] += 1
            b["balance"] = round(b["balance"] + r["balance"], 2)
            b["broken"] += r["promises_broken"]
        total = round(sum(r["balance"] for r in rows), 2)
        return {"as_of": day.isoformat(), "worker_id": worker_id, "accounts": rows, "by_kind": by_kind,
                "total": total,
                "total_display": fmt_money(total),
                "promises_broken": sum(r["promises_broken"] for r in rows)}


@router.get("/{account_id}")
async def get_dues(account_id: int, as_of: Optional[str] = Query(None),
                   worker_id: Optional[int] = Query(None)) -> dict:
    day = _as_of(as_of)
    with db.session() as s:
        a = _account(s, account_id)
        if worker_id is not None and _owner_of(s, a.id) != worker_id:
            raise HTTPException(404, "not found")  # another worker's account
        return account_view(s, a, day)


@router.delete("/{account_id}")
async def delete_dues(account_id: int) -> dict:
    with db.session() as s:
        a = _account(s, account_id)
        _delete(s, a)
        s.commit()
        return {"deleted": account_id}


def _delete(s: Session, a: DuesAccount) -> None:
    for model in (DuesItem, DuesPromise):
        for r in s.exec(select(model).where(model.account_id == a.id)).all():
            s.delete(r)
    s.flush()
    for r in s.exec(select(DuesLog).where(DuesLog.account_id == a.id)).all():
        s.delete(r)
    owner = s.get(DuesOwner, a.id)
    if owner is not None:
        s.delete(owner)
    s.flush()
    s.delete(a)


# ------------------------------------------------------------------ add to an account
class ItemsIn(BaseModel):
    items: list[ItemIn] = Field(..., min_length=1, max_length=30)
    as_of: Optional[str] = None


@router.post("/{account_id}/items")
async def add_items(account_id: int, body: ItemsIn) -> dict:
    with db.session() as s:
        a = _account(s, account_id)
        for it in body.items:
            _add_item(s, a, it, _today())
        s.commit()
        return account_view(s, a, _as_of(body.as_of))


class PaidIn(BaseModel):
    amount: float = Field(..., gt=0, le=10_000_000)
    said_on: Optional[str] = None
    as_of: Optional[str] = None


@router.post("/{account_id}/paid")
async def add_paid(account_id: int, body: PaidIn) -> dict:
    with db.session() as s:
        a = _account(s, account_id)
        _add_item(s, a, ItemIn(label="Received", amount=body.amount, said_on=body.said_on), _today(), kind="paid")
        s.commit()
        return account_view(s, a, _as_of(body.as_of))


@router.post("/{account_id}/promises")
async def add_promise(account_id: int, audio_file: Optional[UploadFile] = File(None, alias="audio"),
                      text: str = Form(""), lang: Optional[str] = Form(None), said_on: Optional[str] = Form(None),
                      due_date: Optional[str] = Form(None), as_of: Optional[str] = Form(None)) -> dict:
    """What they said ("end of this week, pakka") -> a dated promise in the chain. The date resolves from `said_on`."""
    said = _iso_day(said_on, "said_on", _today())
    if said > _today() and not as_of:
        raise HTTPException(400, "said_on is in the future")
    with db.session() as s:
        a = _account(s, account_id)
        lg = _lang_in(lang) or a.party_lang
        words, stt = await _text_or_audio(text, audio_file, lg)
        row = _add_promise(s, a, words, said, lg, "audio" if stt else "text", due_date)
        s.commit()
        out = account_view(s, a, _as_of(as_of) if as_of else max(_today(), said))
        out["added_promise_id"] = row.id
        out["stt"] = stt
        return out


class StatusIn(BaseModel):
    status: Literal["pending", "kept", "broken"]
    as_of: Optional[str] = None


@router.post("/promises/{promise_id}/status")
async def set_status(promise_id: int, body: StatusIn) -> dict:
    with db.session() as s:
        p = s.get(DuesPromise, promise_id)
        if p is None:
            raise HTTPException(404, "promise not found")
        a = _account(s, p.account_id)
        p.status, p.status_at = body.status, db.now_iso()
        _append(s, a.id, "status", _today().isoformat(), f"Promise of {fmt_date(p.said_on, 'en')} marked {body.status}",
                {"promise_hash": _hash_of(s, p.log_id), "status": body.status})
        s.add(p)
        s.commit()
        return account_view(s, a, _as_of(body.as_of))


# ------------------------------------------------------------------ reminder
class RemindIn(BaseModel):
    lang: Optional[str] = None        # default: the other party's language
    voice: bool = False               # a Timbre voice note (starts with the spoken AI disclosure)
    as_of: Optional[str] = None


@router.post("/{account_id}/remind")
async def remind(account_id: int, body: RemindIn = Body(default_factory=RemindIn)) -> dict:
    day = _as_of(body.as_of)
    with db.session() as s:
        a = _account(s, account_id)
        v = account_view(s, a, day)
    if v["balance"] <= 0:
        raise HTTPException(409, {"error": "nothing_owed", "message": "nothing is owed on this account"})
    lang = _lang_in(body.lang) or a.party_lang
    open_items = [i for i in v["items"] if i["kind"] == "due"] if v["total_paid"] == 0 else []
    r = reminder(kind=a.kind, party=a.party_name, owner=a.owner_name or "Baaki", lang=lang, balance=v["balance"],
                 items=open_items, last_promise=v["last_promise"], upi=v["upi_url"])
    mine = reminder(kind=a.kind, party=a.party_name, owner=a.owner_name or "Baaki", lang=a.owner_lang,
                    balance=v["balance"], items=open_items, last_promise=v["last_promise"], upi=v["upi_url"])
    phone = "".join(ch for ch in (a.party_phone or "") if ch.isdigit())
    if len(phone) == 10:
        phone = "91" + phone
    r.update({"text_owner_lang": mine["text"], "owner_language": mine["language"], "upi_url": v["upi_url"],
              "whatsapp_url": f"https://wa.me/{phone}?text={url_quote(r['share_text'])}" if phone else
              "https://wa.me/?text=" + url_quote(r["share_text"]),
              "audio_url": None, "audio": None, "audio_error": None})
    if body.voice:
        sentences = [disclosure(a.owner_name or "Baaki", lang), " ".join(r["speech_sentences"])]
        try:
            note = await voice_note.make_voice_note(sentences, tts_lang(lang), worker_name=a.owner_name,
                                                    purpose="dues reminder")
            key = storage.get_storage().put(storage.new_key(None, "ogg"), note.data)
            r["audio_url"] = f"/api/media/{key}"
            r["audio"] = {"duration_s": note.duration_s, "voice": note.voice, "gnani_calls": note.gnani_calls,
                          "cache_hits": note.cache_hits, "disclosure": sentences[0]}
        except (GnaniError, audio.AudioError, ValueError) as ex:
            r["audio_error"] = ex.as_dict() if isinstance(ex, GnaniError) else {"message": str(ex)[:200]}
    return r


# ------------------------------------------------------------------ record pack
@router.get("/{account_id}/pack.pdf")
async def pack(account_id: int, as_of: Optional[str] = Query(None)) -> Response:
    day = _as_of(as_of)
    with db.session() as s:
        a = _account(s, account_id)
        v = account_view(s, a, day)
    if not v["pack"]["applies"]:
        raise HTTPException(409, {"error": "not_for_kind", "message": "the record pack is for chit and other money"})
    if not v["pack"]["eligible"]:
        raise HTTPException(409, {"error": "too_early",
                                  "message": f"the record pack opens after {PACK_MIN_BROKEN} broken promises"})
    data = render_pdf(pack_blocks(v), title=f"Baaki record: {a.party_name}")
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="baaki-record-{a.id}.pdf"'})


# ------------------------------------------------------------------ demo (synthetic)
def _prev_month(d: dt.date) -> dt.date:
    return d.replace(day=1) - dt.timedelta(days=1)


CHIT_PROMISES = (   # (days before today, words) - Srinivas, in Telugu; all synthetic
    (126, "ఈ వారం చివరికి ఇస్తాను, కంగారు పడకండి"),
    (105, "ఈ వారం చివర్లో పక్కా ఇచ్చేస్తాను"),
    (84, "Lakshmi garu, ee vaaram chivariki istanu"),
    (63, "ఈ వారం చివరికి మొత్తం నలభై వేలు ఇస్తాను"),
    (42, "ఈ వారం చివర్లో ఇస్తాను, పక్కా"),
    (21, "ఈ వారం చివరికి ఇచ్చేస్తాను"),
)


@router.post("/demo")
async def demo(worker_id: Optional[int] = Query(None)) -> dict:
    """Synthetic demo set (replaces the previous demo set): Ramu the milkman, owed ₹1,850 for last month by
    Reddy garu (two "first week" promises), and Lakshmi's chit money from Srinivas agent, ₹40,000 with six
    "end of this week" promises over four months. Both accounts belong to Lakshmi (or `worker_id`)."""
    today = _today()
    with db.session() as s:
        return seed_demo(s, today, _demo_owner(s, worker_id))


def seed_demo(s: Session, today: dt.date, owner: Optional[int]) -> dict:
    """Write the demo accounts for `owner` (sync; the demo route and seed.reset share it). Commits."""
    for old in s.exec(select(DuesAccount).where(DuesAccount.demo == True)).all():  # noqa: E712
        _delete(s, old)
    s.flush()
    # 1. milk
    pm = _prev_month(today)
    mname = MONTHS["en"][pm.month - 1]
    milk = DuesAccount(kind="vendor", title="Milk bill", party_name="Reddy garu", party_lang="hi-en",
                       owner_name="Ramu", owner_lang="hi-en", owner_vpa="demo.ramu@baaki", demo=True)
    s.add(milk)
    s.flush()
    _set_owner(s, milk.id, owner)
    _append(s, milk.id, "account", pm.replace(day=1).isoformat(), "Ramu is owed money by Reddy garu",
            {"kind": "vendor", "title": "Milk bill", "party": "Reddy garu"})
    parsed = parse_items(f"{mname} doodh 1850", "hinglish", "vendor")["items"][0]
    _add_item(s, milk, ItemIn(label=parsed["label"], amount=parsed["amount"], item_key=parsed["item_key"],
                              month=parsed["month"], source_text=parsed["source_text"],
                              said_on=pm.isoformat()), pm)
    _add_promise(s, milk, "Ramu bhai, agle mahine pehle hafte mein pakka de dunga", pm, "hi-en")
    _add_promise(s, milk, "agle mahine pehle hafte pakka, dono mahine ka saath mein",
                 today - dt.timedelta(days=1), "hi-en")
    # 2. chit
    first = today - dt.timedelta(days=CHIT_PROMISES[0][0])
    chit = DuesAccount(kind="chit", title="Chit money from Srinivas agent", party_name="Srinivas agent",
                       party_lang="te-IN", owner_name="Lakshmi", owner_lang="te-IN", demo=True,
                       note="Chit lifted; payout promised")
    s.add(chit)
    s.flush()
    _set_owner(s, chit.id, owner)
    start = first - dt.timedelta(days=4)
    _append(s, chit.id, "account", start.isoformat(), "Lakshmi is owed money by Srinivas agent",
            {"kind": "chit", "title": chit.title, "party": "Srinivas agent"})
    _add_item(s, chit, ItemIn(label="చిట్టీ డబ్బులు", amount=40000, item_key="chit", source_text="40,000",
                              said_on=start.isoformat()), start)
    for days, words in CHIT_PROMISES:
        _add_promise(s, chit, words, today - dt.timedelta(days=days), "te-IN")
    s.commit()
    return {"accounts": {"milk": milk.id, "chit": chit.id}, "as_of": today.isoformat(), "worker_id": owner,
            "milk": summary_view(account_view(s, milk, today)), "chit": summary_view(account_view(s, chit, today))}
