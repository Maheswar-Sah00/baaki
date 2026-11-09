"""The money ledger (fix stream F2, root causes R1 + R3). One place writes money; one place derives what follows.

  record_payment(s, case, amount, method, note, source, paid_at=None) -> PaymentResult
      The ONLY writer of Payment rows with status "paid" and of Case.amount_paid. Caps the recorded amount at the
      balance and reports what was beyond it (`excess`) instead of dropping it silently. Calls reconcile().

  reconcile(s, case) -> dict
      Called after every payment and every calculation change (routes/cases.py apply_calc, employer plan,
      hisaab decide). From the balance it derives:
        * case.status: "paid" when nothing is owed; a paid case opens again ("plan" / "sent" / "confirmed")
          when the total rises; a "plan" case with no instalment left falls back to the open status
        * the Fair Employer badge: given when paid in full, taken back while anything is owed, but only if this
          case gave it (FairBadgeGrant)
        * the pay-in-parts plan: instalments are settled ONLY by money paid after the plan was made (the plan's
          baseline Payment id); when the balance changes the remaining instalments are re-split so the plan
          still adds up, and when nothing is owed the unpaid ones are cancelled; reminder Message rows follow
          (scheduled <-> cancelled, text rewritten when an amount changes)
        * `overpaid`: money paid beyond a reduced total (plus anything confirmed beyond the balance)
      Never commits; the caller does.

  create_plan(...)        a new 2/3-part plan with its baseline (replaces the old one)
  snapshot_message(...)   balance/total a voice note was made with; staleness(...) compares it to now

Every rupee figure here is arithmetic on stored amounts (which come from app.lang / app.wages); no LLM.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from typing import Any, Optional

from sqlmodel import Session, select

from . import db
from .ledger_models import FairBadgeGrant, LedgerEntry, LedgerPlan, MessageSnapshot
from .messages import fmt_date, fmt_money, money_words, name_in, norm_lang
from .models import Case, Employer, Message, Payment, Worker

TOL = 0.5                       # rupee rounding tolerance used everywhere money is compared
METHODS = ("upi", "cash", "bank", "other")
OPEN_STEPS = ("polite", "firm", "formal")


class LedgerError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status

    def as_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message}


@dataclasses.dataclass
class PaymentResult:
    payment: Payment
    recorded: float              # what went into amount_paid
    requested: float             # what was said / confirmed
    excess: float                # requested beyond the balance (not recorded; shown as overpaid)
    balance_before: float
    balance_after: float
    fully_paid: bool
    reconcile: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"payment_id": self.payment.id, "recorded": self.recorded, "requested": self.requested,
                "excess": self.excess, "balance_before": self.balance_before, "balance_after": self.balance_after,
                "fully_paid": self.fully_paid}


# --------------------------------------------------------------------------- texts that carry amounts
REMINDER = {
    "hi-en": "याद दिलाना: {worker} की किस्त {i}/{n}, {amount}, {due} तक।",
    "te-IN": "గుర్తు: {worker} వాయిదా {i}/{n}, {amount}, {due} లోపు.",
    "en": "Reminder: instalment {i} of {n} for {worker}, {amount}, due by {due}.",
}
PAID_ALERT = {
    "hi-en": ("<excited> पैसा आ गया! {employer} ने {amount} भेज दिए, पूरा हिसाब हो गया।",
              "<excited> पैसा आ गया! {employer} ने {amount} भेज दिए, अभी {balance} बाकी हैं।"),
    "te-IN": ("<excited> డబ్బులు వచ్చేశాయి! {employer} {amount} పంపించారు, మొత్తం లెక్క పూర్తయింది.",
              "<excited> డబ్బులు వచ్చేశాయి! {employer} {amount} పంపించారు, ఇంకా {balance} బాకీ ఉంది."),
    "en": ("<excited> The money has arrived! {employer} sent {amount}, and everything is settled.",
           "<excited> The money has arrived! {employer} sent {amount}; {balance} is still due."),
}


def reminder_texts(worker_name: str, employer_lang: str, worker_lang: str, i: int, n: int, amount: float,
                   due: dt.date | str) -> tuple[str, str]:
    el, wl = norm_lang(employer_lang), norm_lang(worker_lang)
    return (REMINDER[el].format(worker=name_in(worker_name, el), i=i, n=n, amount=fmt_money(amount),
                                due=fmt_date(due, el)),
            REMINDER[wl].format(worker=name_in(worker_name, wl), i=i, n=n, amount=fmt_money(amount),
                                due=fmt_date(due, wl)))


def paid_alert_texts(employer_name: str, worker_lang: str, amount: float, balance: float) -> dict[str, str]:
    """"Paisa aa gaya" in her language: `speech` (Timbre, amounts as words, <excited>) and `text` (display)."""
    wl = norm_lang(worker_lang)
    full = balance <= TOL
    tpl = PAID_ALERT[wl][0 if full else 1]
    speech = tpl.format(employer=name_in(employer_name, wl), amount=money_words(amount, wl),
                        balance=money_words(balance, wl))
    text = tpl.replace("<excited> ", "").format(employer=name_in(employer_name, wl), amount=fmt_money(amount),
                                                balance=fmt_money(balance))
    return {"speech": speech, "text": text, "language": wl, "full": full}


def split_amount(total: float, n: int) -> list[float]:
    """Whole-rupee instalments that add up exactly; any remainder (and paise) goes on the first."""
    whole = int(total)
    base = whole // n
    parts = [float(base)] * n
    parts[0] = round(total - base * (n - 1), 2)
    return parts


# --------------------------------------------------------------------------- reads
def _payments(s: Session, case: Case) -> list[Payment]:
    return list(s.exec(select(Payment).where(Payment.case_id == case.id).order_by(Payment.id)))


def _entries(s: Session, case: Case) -> list[LedgerEntry]:
    return list(s.exec(select(LedgerEntry).where(LedgerEntry.case_id == case.id,
                                                 LedgerEntry.case_token == case.employer_token)))


def overpaid(s: Session, case: Case) -> float:
    """Paid beyond the (possibly reduced) total, plus money confirmed beyond the balance at the time."""
    beyond_total = max(0.0, float(case.amount_paid or 0) - float(case.total_due or 0))
    beyond_balance = sum(max(0.0, e.requested - e.amount) for e in _entries(s, case))
    v = round(beyond_total + beyond_balance, 2)
    return v if v > 0.009 else 0.0


def money_view(s: Session, case: Case) -> dict[str, Any]:
    over = overpaid(s, case)
    return {"total_due": round(float(case.total_due or 0), 2), "amount_paid": round(float(case.amount_paid or 0), 2),
            "balance": case.balance, "balance_display": fmt_money(case.balance), "overpaid": over,
            "overpaid_display": fmt_money(over) if over else None}


# --------------------------------------------------------------------------- the only money writer
def record_payment(s: Session, case: Case, amount: float, method: str, note: Optional[str], source: str,
                   paid_at: Optional[str] = None, *, plan_credit: bool = True,
                   proposal_id: Optional[int] = None) -> PaymentResult:
    """Record money that reached her. Caps at the balance; returns what was beyond it. Runs reconcile()."""
    requested = round(float(amount or 0), 2)
    if requested <= 0:
        raise LedgerError("bad_amount", "amount must be more than zero", 400)
    bal = case.balance
    if bal <= 0:
        raise LedgerError("nothing_due", "already paid in full")
    recorded = round(min(requested, bal), 2)
    excess = round(requested - recorded, 2)
    if excess <= TOL:          # rounding, not real money beyond the balance
        excess = 0.0
    now = db.now_iso()
    p = Payment(case_id=case.id, amount=recorded, method=method if method in METHODS else "other", status="paid",
                paid_at=paid_at or now, note=note)
    s.add(p)
    case.amount_paid = round(float(case.amount_paid or 0) + recorded, 2)
    case.updated_at = now
    s.add(case)
    s.flush()
    s.add(LedgerEntry(case_id=case.id, case_token=case.employer_token, payment_id=p.id, amount=recorded,
                      requested=round(recorded + excess, 2), method=p.method, source=source,
                      plan_credit=plan_credit, proposal_id=proposal_id, recorded_at=now))
    s.flush()
    rec = reconcile(s, case)
    return PaymentResult(payment=p, recorded=recorded, requested=requested, excess=excess, balance_before=bal,
                         balance_after=case.balance, fully_paid=case.balance <= TOL, reconcile=rec)


# --------------------------------------------------------------------------- plans
def _links(plan: LedgerPlan) -> list[dict[str, Any]]:
    try:
        return list(json.loads(plan.links_json or "[]"))
    except ValueError:
        return []


def _active_plan(s: Session, case: Case, pays: list[Payment]) -> Optional[LedgerPlan]:
    plan = s.exec(select(LedgerPlan).where(LedgerPlan.case_id == case.id, LedgerPlan.case_token == case.employer_token,
                                           LedgerPlan.status == "active").order_by(LedgerPlan.id.desc())).first()
    if plan is not None:
        return plan
    planned = sorted([p for p in pays if p.instalment_no and p.status == "planned"], key=lambda p: p.id or 0)
    if not planned:
        return None
    # A plan made before the ledger existed: adopt it. Its baseline is the row just before its first instalment.
    # one plan's instalments were written together, so their ids are consecutive
    first_id = (planned[0].id or 0) - ((planned[0].instalment_no or 1) - 1)
    insts = sorted([p for p in pays if p.instalment_no and p.status in ("planned", "settled")
                    and (p.id or 0) >= first_id], key=lambda p: p.instalment_no or 0)
    reminders = list(s.exec(select(Message).where(Message.case_id == case.id, Message.step == "reminder")
                            .order_by(Message.id)))[-len(insts):] if insts else []
    links = [{"no": p.instalment_no, "payment_id": p.id,
              "reminder_id": reminders[i].id if i < len(reminders) else None} for i, p in enumerate(insts)]
    plan = LedgerPlan(case_id=case.id, case_token=case.employer_token,
                      baseline_payment_id=min(p.id or 0 for p in insts) - 1, instalments_total=len(insts),
                      balance_at_plan=round(sum(p.amount for p in insts), 2), links_json=json.dumps(links))
    s.add(plan)
    s.flush()
    return plan


def create_plan(s: Session, case: Case, *, instalments: int, first_due: dt.date, every_days: int,
                worker: Worker, employer: Employer) -> tuple[LedgerPlan, list[tuple[Payment, Message]]]:
    """Replace any plan with a new one over today's balance. Baseline = the highest Payment id before it."""
    bal = case.balance
    if bal <= 0:
        raise LedgerError("nothing_due", "already paid in full")
    pays = _payments(s, case)
    for p in pays:                                   # a new plan replaces the old one
        if p.instalment_no and p.status == "planned":
            s.delete(p)
    for m in s.exec(select(Message).where(Message.case_id == case.id, Message.step == "reminder",
                                          Message.status == "scheduled")):
        s.delete(m)
    for old in s.exec(select(LedgerPlan).where(LedgerPlan.case_id == case.id, LedgerPlan.status == "active")):
        old.status, old.updated_at = "replaced", db.now_iso()
        s.add(old)
    s.flush()
    baseline = max([p.id or 0 for p in _payments(s, case)] or [0])
    parts = split_amount(bal, instalments)
    out: list[tuple[Payment, Message]] = []
    for i, amt in enumerate(parts, 1):
        due = first_due + dt.timedelta(days=every_days * (i - 1))
        p = Payment(case_id=case.id, amount=amt, method="upi", status="planned", due_date=due.isoformat(),
                    instalment_no=i, instalments_total=instalments)
        el_text, wl_text = reminder_texts(worker.name, employer.language, worker.language, i, instalments, amt, due)
        r = Message(case_id=case.id, step="reminder", direction="to_employer", language=norm_lang(employer.language),
                    status="scheduled", text=el_text, text_worker_lang=wl_text)
        s.add(p)
        s.add(r)
        out.append((p, r))
    s.flush()
    plan = LedgerPlan(case_id=case.id, case_token=case.employer_token, baseline_payment_id=baseline,
                      balance_at_plan=bal, instalments_total=instalments, every_days=every_days,
                      links_json=json.dumps([{"no": p.instalment_no, "payment_id": p.id, "reminder_id": r.id}
                                             for p, r in out]))
    s.add(plan)
    case.status, case.updated_at = "plan", db.now_iso()
    s.add(case)
    s.flush()
    return plan, out


def _reconcile_plan(s: Session, case: Case, pays: list[Payment], owed: bool) -> Optional[dict[str, Any]]:
    plan = _active_plan(s, case, pays)
    if plan is None:
        return None
    links = _links(plan)
    by_id = {p.id: p for p in pays}
    insts = [by_id[l["payment_id"]] for l in links if l.get("payment_id") in by_id]
    insts = [p for p in insts if p.status in ("planned", "settled", "cancelled")]
    insts.sort(key=lambda p: p.instalment_no or 0)
    no_credit = {e.payment_id for e in _entries(s, case) if not e.plan_credit}
    post = round(sum(p.amount for p in pays if p.status == "paid" and (p.id or 0) > plan.baseline_payment_id
                     and p.id not in no_credit), 2)
    worker = s.get(Worker, case.worker_id)
    employer = s.get(Employer, case.employer_id)
    resplit = False

    def settle_walk() -> list[str]:
        credit, out = post, []
        for p in insts:
            credit = round(credit - p.amount, 2)
            out.append("settled" if credit >= -TOL else "planned")
        return out

    states = settle_walk()
    if owed:
        # the plan must still add up: instalments == balance + money paid since the plan
        settled_sum = sum(p.amount for p, st in zip(insts, states) if st == "settled")
        open_rows = [p for p, st in zip(insts, states) if st != "settled"]
        target = round(case.balance + post - settled_sum, 2)
        if open_rows and abs(sum(p.amount for p in open_rows) - target) > TOL and target > 0:
            for p, amt in zip(open_rows, split_amount(target, len(open_rows))):
                p.amount = amt
            resplit = True
            states = settle_walk()
    else:
        states = ["settled" if st == "settled" else "cancelled" for st in states]

    changed_amount = set()
    for p, st in zip(insts, states):
        if resplit and st == "planned":
            changed_amount.add(p.id)
        if p.status != st:
            p.status = st
        s.add(p)
    # reminders follow their instalment
    for l in links:
        rid, pid = l.get("reminder_id"), l.get("payment_id")
        if not rid or pid not in by_id:
            continue
        r = s.get(Message, rid)
        if r is None or r.case_id != case.id:
            continue
        p = by_id[pid]
        if p.status == "planned" and r.status == "cancelled":
            r.status = "scheduled"
        elif p.status != "planned" and r.status == "scheduled":
            r.status = "cancelled"
        if pid in changed_amount and worker is not None and employer is not None and p.due_date:
            r.text, r.text_worker_lang = reminder_texts(worker.name, employer.language, worker.language,
                                                        p.instalment_no or 0, p.instalments_total or len(insts),
                                                        p.amount, p.due_date)
        s.add(r)
    still_open = [p for p in insts if p.status == "planned"]
    if not still_open:
        plan.status = "done"
    plan.updated_at = db.now_iso()
    s.add(plan)
    return {"plan_id": plan.id, "status": plan.status, "paid_since_plan": post, "resplit": resplit,
            "instalments": [{"payment_id": p.id, "instalment_no": p.instalment_no, "amount": p.amount,
                             "status": p.status} for p in insts]}


# --------------------------------------------------------------------------- badge and status
def _reconcile_badge(s: Session, case: Case, settled: bool, owed: bool, was_paid: bool) -> Optional[str]:
    e = s.get(Employer, case.employer_id)
    if e is None:
        return None
    mine = list(s.exec(select(FairBadgeGrant).where(FairBadgeGrant.case_id == case.id,
                                                    FairBadgeGrant.case_token == case.employer_token,
                                                    FairBadgeGrant.active == True)))  # noqa: E712
    if settled and float(case.total_due or 0) > 0:
        if not mine:
            s.add(FairBadgeGrant(employer_id=e.id, case_id=case.id, case_token=case.employer_token))
        if not e.fair_employer:
            e.fair_employer = True
            s.add(e)
            return "granted"
        return None
    if not owed:
        return None
    revoked = False
    for g in mine:
        g.active, g.revoked_at = False, db.now_iso()
        s.add(g)
        revoked = True
    if not revoked and was_paid and e.fair_employer:
        # badge from before the ledger: this paid case is the only thing that could have turned it on
        any_grant = s.exec(select(FairBadgeGrant).where(FairBadgeGrant.employer_id == e.id)).first()
        revoked = any_grant is None
    if not revoked or not e.fair_employer or e.kaam_patta_signed:
        return None
    s.flush()
    others = s.exec(select(FairBadgeGrant).where(FairBadgeGrant.employer_id == e.id,
                                                 FairBadgeGrant.active == True)).first()  # noqa: E712
    if others is None:
        e.fair_employer = False
        s.add(e)
        return "removed"
    return None


def _open_status(s: Session, case: Case, has_plan: bool) -> str:
    if has_plan:
        return "plan"
    sent = s.exec(select(Message).where(Message.case_id == case.id, Message.direction == "to_employer",
                                        Message.step.in_(OPEN_STEPS),  # type: ignore[attr-defined]
                                        Message.status.in_(("sent", "played", "replied")))).first()  # type: ignore[attr-defined]
    # a case that was paid or on a plan is past intake: it never falls back to "draft"
    return "sent" if sent is not None else "confirmed"


def reconcile(s: Session, case: Case) -> dict[str, Any]:
    """Derive status, badge, plan and overpaid from the balance. Writes to the session; never commits."""
    s.flush()
    pays = _payments(s, case)
    total = round(float(case.total_due or 0), 2)
    paid = round(float(case.amount_paid or 0), 2)
    owed = case.balance > TOL
    settled = not owed and (total > 0 or paid > 0)
    old = case.status
    plan = _reconcile_plan(s, case, pays, owed)
    has_open_plan = bool(plan and plan["status"] == "active")
    if settled:
        if old != "closed":
            case.status = "paid"
        for r in s.exec(select(Message).where(Message.case_id == case.id, Message.step == "reminder",
                                              Message.status == "scheduled")):
            r.status = "cancelled"
            s.add(r)
    elif owed and old == "paid":
        case.status = _open_status(s, case, has_open_plan)
    elif owed and old == "plan" and not has_open_plan:
        case.status = _open_status(s, case, False)
    badge = _reconcile_badge(s, case, settled, owed, old == "paid")
    if case.status != old:
        case.updated_at = db.now_iso()
    s.add(case)
    s.flush()
    return {"status": case.status, "status_before": old, "reopened": old == "paid" and case.status != "paid",
            "total_due": total, "amount_paid": paid, "balance": case.balance, "overpaid": overpaid(s, case),
            "fully_paid": settled, "badge": badge, "plan": plan}


# --------------------------------------------------------------------------- message snapshots (GAP #9)
def snapshot_message(s: Session, m: Message, case: Case) -> MessageSnapshot:
    snap = s.get(MessageSnapshot, m.id)
    if snap is None:
        snap = MessageSnapshot(message_id=m.id, case_id=case.id, case_token=case.employer_token,
                               balance_at_make=case.balance, total_at_make=round(float(case.total_due or 0), 2))
        s.add(snap)
    return snap


def get_snapshot(s: Session, m: Message, case: Case) -> Optional[MessageSnapshot]:
    snap = s.get(MessageSnapshot, m.id) if m.id is not None else None
    if snap is None or snap.case_token != case.employer_token or snap.case_id != case.id:
        return None
    return snap


def staleness(s: Session, m: Message, case: Case) -> dict[str, Any]:
    """{"stale": bool, "balance_at_make": float|None}: stale when the note was made for a different balance."""
    snap = get_snapshot(s, m, case)
    if snap is None:
        return {"stale": False, "balance_at_make": None}
    return {"stale": abs(snap.balance_at_make - case.balance) > 0.004, "balance_at_make": snap.balance_at_make}


def same_balance(s: Session, m: Message, case: Case) -> bool:
    """Reuse rule: only a note whose snapshot balance equals today's balance exactly."""
    snap = get_snapshot(s, m, case)
    return snap is not None and round(snap.balance_at_make, 2) == round(case.balance, 2)


__all__ = ["LedgerError", "PaymentResult", "record_payment", "reconcile", "create_plan", "split_amount",
           "reminder_texts", "paid_alert_texts", "money_view", "overpaid", "snapshot_message", "staleness",
           "same_balance", "get_snapshot", "TOL", "REMINDER", "PAID_ALERT"]
