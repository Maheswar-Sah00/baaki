"""Reminders she shares herself: GET /api/cases/{id}/reminders?as_of=YYYY-MM-DD

Nothing is ever sent from here. Each card carries the text for her (her language) and, where there is one, the
message for the employer (his language) with the employer link, a wa.me link and the endpoint that marks it sent.

Card kinds:
* `instalment`   a planned instalment whose due date has come (due today or passed) and that is still unpaid:
                 the Payment row is "planned" (the ledger moves it to settled / cancelled) and its reminder
                 Message is still "scheduled" (the ledger cancels it when the case is paid in full; marking it
                 sent with POST /api/messages/{id}/sent ends it). Read only: this module writes nothing.
* `next_step`    the last ladder step she sent (polite / firm / formal) is 7+ days old, no reply came since and
                 money is still owed: suggest the next step (polite -> firm -> formal -> legal aid hand-over).
                 She makes it with POST /api/cases/{id}/messages/{step} and presses Send herself.
* `promise`      a promise the employer made in a forwarded reply (Share to Baaki) whose date has passed
                 unpaid: POST /api/inbox/promises/{id}/remind writes the reminder quoting his own words.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional
from urllib.parse import quote as url_quote

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, select

from .. import clock, db
from ..messages import employer_url, fmt_date, fmt_money, name_in, norm_lang
from ..models import Case, Employer, Message, Payment, Worker

router = APIRouter(prefix="/api/cases", tags=["reminders"])

LADDER = ("polite", "firm", "formal")
NEXT_STEP = {"polite": "firm", "firm": "formal", "formal": "legal_aid"}
LADDER_WAIT_DAYS = 7
SENT_STATES = ("sent", "played", "replied")

STEP_NAME = {
    "te-IN": {"firm": "గట్టి సందేశం", "formal": "అధికారిక లేఖ", "legal_aid": "ఉచిత న్యాయ సహాయం"},
    "hi-en": {"firm": "सख़्त संदेश", "formal": "औपचारिक पत्र", "legal_aid": "मुफ़्त कानूनी सहायता"},
    "en": {"firm": "a firm message", "formal": "a formal letter", "legal_aid": "free legal aid"},
}
NEXT_STEP_TEXT = {
    "te-IN": "{employer} నుండి {days} రోజులుగా జవాబు లేదు. తర్వాతి అడుగు: {step}. మీరు చూసి మీరే పంపండి.",
    "hi-en": "{employer} ने {days} दिन से जवाब नहीं दिया। अगला कदम: {step}। देखकर खुद भेजिए।",
    "en": "No reply from {employer} for {days} days. Next step: {step}. Check it and send it yourself.",
}
LEGAL_AID_TEXT = {
    "te-IN": "{employer} నుండి {days} రోజులుగా జవాబు లేదు. జిల్లా న్యాయ సేవా సంస్థ (DLSA) లేదా కార్మిక శాఖ ఉచితంగా "
             "సహాయం చేస్తాయి. మీ లెక్క మరియు లేఖలు ఉన్న పత్రాల ప్యాక్ తీసుకెళ్లండి.",
    "hi-en": "{employer} ने {days} दिन से जवाब नहीं दिया। ज़िला विधिक सेवा प्राधिकरण (DLSA) या श्रम विभाग मुफ़्त में "
             "मदद करते हैं। अपना हिसाब और पत्रों वाला पैक साथ ले जाइए।",
    "en": "No reply from {employer} for {days} days. The District Legal Services Authority (DLSA) or the labour "
          "department can help for free. Take the pack with your calculation and letters.",
}
INSTALMENT_TITLE = {"te-IN": "వాయిదా {i}/{n} గడువు వచ్చింది", "hi-en": "किस्त {i}/{n} की तारीख़ आ गई",
                    "en": "Instalment {i} of {n} is due"}


def _as_of(as_of: Optional[str]) -> dt.date:
    if not as_of:
        return clock.today()
    try:
        return dt.date.fromisoformat(as_of[:10])
    except ValueError:
        raise HTTPException(400, "as_of must be an ISO date")


def _day(x: Optional[str]) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat((x or "")[:10])
    except ValueError:
        return None


def _wl(lang: str) -> str:
    l = norm_lang(lang)
    return l if l in NEXT_STEP_TEXT else "en"


def _share(text: str, link: str) -> dict[str, str]:
    full = f"{text}\n{link}"
    return {"share_text": full, "whatsapp_url": "https://wa.me/?text=" + url_quote(full)}


def _instalment_links(s: Session, case: Case, insts: list[Payment]) -> dict[int, Optional[int]]:
    """payment_id -> reminder message id: the ledger's active plan links when there is one, else the last N
    reminder rows in order (one plan's rows are written together)."""
    try:
        import json

        from ..ledger_models import LedgerPlan

        plan = s.exec(select(LedgerPlan).where(LedgerPlan.case_id == case.id, LedgerPlan.status == "active")
                      .order_by(LedgerPlan.id.desc())).first()
        if plan is not None:
            links = json.loads(plan.links_json or "[]")
            return {int(l["payment_id"]): l.get("reminder_id") for l in links if l.get("payment_id")}
    except Exception:  # ledger tables not there (older build): fall back to the row order
        pass
    msgs = list(s.exec(select(Message).where(Message.case_id == case.id, Message.step == "reminder")
                       .order_by(Message.id)))[-len(insts):] if insts else []
    return {p.id: (msgs[i].id if i < len(msgs) else None) for i, p in enumerate(insts) if p.id is not None}


def instalment_cards(s: Session, case: Case, worker: Worker, employer: Employer, day: dt.date) -> list[dict[str, Any]]:
    pays = list(s.exec(select(Payment).where(Payment.case_id == case.id).order_by(Payment.id)))
    insts = [p for p in pays if p.instalment_no and p.status in ("planned", "settled", "cancelled")]
    links = _instalment_links(s, case, sorted(insts, key=lambda p: p.instalment_no or 0))
    wl, el = _wl(worker.language), norm_lang(employer.language)
    link = employer_url(case.employer_token)
    out = []
    for p in insts:
        due = _day(p.due_date)
        if p.status != "planned" or due is None or due > day:
            continue
        rid = links.get(p.id) if p.id is not None else None
        m = s.get(Message, rid) if rid else None
        if m is not None and m.status not in ("scheduled", "draft"):
            continue  # cancelled by the ledger, or she already shared it
        from ..ledger import reminder_texts  # read-only helper (F2): the same wording the plan stored

        el_text, wl_text = reminder_texts(worker.name, el, wl, p.instalment_no or 1, p.instalments_total or 1,
                                          p.amount, p.due_date or day)
        message = (m.text if m is not None and m.text else el_text)
        out.append({
            "kind": "instalment", "key": f"instalment:{p.id}", "case_id": case.id, "due_date": p.due_date,
            "days_overdue": (day - due).days, "amount": p.amount, "amount_display": fmt_money(p.amount),
            "title": INSTALMENT_TITLE[wl].format(i=p.instalment_no, n=p.instalments_total),
            "text": (m.text_worker_lang if m is not None and m.text_worker_lang else wl_text), "text_lang": wl,
            "message": message, "message_lang": el, "employer_url": link, **_share(message, link),
            "message_id": m.id if m is not None else None, "payment_id": p.id,
            "mark_sent": {"method": "POST", "path": f"/api/messages/{m.id}/sent"} if m is not None else None,
            "auto_send": False,
        })
    return out


def next_step_card(s: Session, case: Case, worker: Worker, employer: Employer, day: dt.date) -> Optional[dict[str, Any]]:
    if case.balance <= 0:
        return None
    msgs = list(s.exec(select(Message).where(Message.case_id == case.id).order_by(Message.id)))
    sent = [m for m in msgs if m.direction == "to_employer" and m.step in LADDER and m.status in SENT_STATES]
    if not sent:
        return None
    last = sent[-1]
    at = last.sent_at or last.created_at or ""
    sent_day = _day(at)
    if sent_day is None:
        return None
    days = (day - sent_day).days
    if days < LADDER_WAIT_DAYS:
        return None
    if last.status == "replied" or any(m.direction == "from_employer" and (m.created_at or "") >= at for m in msgs):
        return None
    try:  # a reply she forwarded through Share to Baaki counts too
        from ..inbox_models import InboxCard

        if s.exec(select(InboxCard).where(InboxCard.case_id == case.id, InboxCard.created_at >= at)).first():
            return None
    except Exception:
        pass
    nxt = NEXT_STEP[last.step]
    if nxt != "legal_aid" and any(m.step == nxt and m.direction == "to_employer" and m.status in SENT_STATES
                                  for m in msgs):
        return None
    wl = _wl(worker.language)
    emp = name_in(employer.name, wl)
    tmpl = LEGAL_AID_TEXT if nxt == "legal_aid" else NEXT_STEP_TEXT
    return {
        "kind": "next_step", "key": f"next_step:{last.id}:{nxt}", "case_id": case.id,
        "due_date": (sent_day + dt.timedelta(days=LADDER_WAIT_DAYS)).isoformat(), "days_overdue": days - LADDER_WAIT_DAYS,
        "last_step": last.step, "last_sent_at": at, "days_since": days, "next_step": nxt,
        "title": STEP_NAME[wl][nxt], "text": tmpl[wl].format(employer=emp, days=days, step=STEP_NAME[wl][nxt]),
        "text_lang": wl, "message": None, "message_lang": norm_lang(employer.language),
        "action": ({"method": "GET", "path": f"/api/cases/{case.id}/legal-pack"} if nxt == "legal_aid" else
                   {"method": "POST", "path": f"/api/cases/{case.id}/messages/{nxt}"}),
        "auto_send": False,
    }


def promise_cards(s: Session, case: Case, worker: Worker, day: dt.date) -> list[dict[str, Any]]:
    try:
        from ..inbox_models import InboxPromise
        from .inbox import promise_view
    except Exception:
        return []
    wl = _wl(worker.language)
    out = []
    for p in s.exec(select(InboxPromise).where(InboxPromise.case_id == case.id).order_by(InboxPromise.due_date)):
        v = promise_view(s, p, day, case.balance, wl)
        if v["status"] != "passed":
            continue
        out.append({"kind": "promise", "key": f"promise:{p.id}", "case_id": case.id, "due_date": p.due_date,
                    "days_overdue": (day - (_day(p.due_date) or day)).days, "amount": p.amount,
                    "amount_display": v["amount_display"], "quote": p.quote, "title": v["due_display"],
                    "text": None, "text_lang": wl, "message": None, "promise_id": p.id,
                    "action": {"method": "POST", "path": f"/api/inbox/promises/{p.id}/remind"}, "auto_send": False})
    return out


def due_reminders(s: Session, case: Case, day: dt.date) -> list[dict[str, Any]]:
    worker, employer = s.get(Worker, case.worker_id), s.get(Employer, case.employer_id)
    if worker is None or employer is None or case.status in ("draft", "closed"):
        return []
    cards = instalment_cards(s, case, worker, employer, day)
    step = next_step_card(s, case, worker, employer, day)
    if step:
        cards.append(step)
    cards += promise_cards(s, case, worker, day)
    return sorted(cards, key=lambda c: (c["due_date"] or "", c["kind"]))


@router.get("/{case_id}/reminders")
async def reminders(case_id: int, as_of: Optional[str] = Query(None)) -> dict:
    """Due reminders for this case, as cards she shares herself (`as_of` = demo time travel)."""
    day = _as_of(as_of)
    with db.session() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise HTTPException(404, "case not found")
        cards = due_reminders(s, case, day)
        return {"case_id": case_id, "as_of": day.isoformat(), "balance": case.balance,
                "balance_display": fmt_money(case.balance), "count": len(cards), "reminders": cards,
                "next_check": fmt_date(day + dt.timedelta(days=1), "en")}
