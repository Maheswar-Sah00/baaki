"""V12 Case Replay: one case's stored events, merged read-only into a timeline.

Rules (NEXT_5.md, rank 9):
* Only events that have a STORED timestamp. Nothing is invented, interpolated or moved. `at` is the stored
  string exactly as it sits in the database (or the Listen-twice cache), and `at_field` names its column.
* Order: the stored time (parsed, so "...Z" and "...+00:00" compare correctly). Rows written in the same
  instant (a payment and its "Paisa aa gaya" alert share one `now`) are ordered by a fixed kind rank, then
  table and row id. One more same-second rule: her words and the read-back (case intake) come before
  anything else stamped in that second, because the seed writes `confirmed_at` a few microseconds before
  `created_at`. The labels always show the stored time, unchanged.
* Money: the running balance after each payment uses `Case.balance` (the property the case screen shows:
  max(0, round(total_due - amount_paid, 2))) on a detached copy of the case. No money maths lives here.

What has no stored time is left out of `events` and listed in `untimed` (the employer playing the voice
note is a status only, so "listened" is shown untimed; scheduled reminders have not happened yet).

Read-only: this module never writes to the database or to the Listen-twice cache.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlmodel import Session, select

from . import storage, verify_guard
from .exit_kit import ExitKit
from .inbox_models import InboxCard, InboxPromise
from .messages import CaseCtx, load_ctx
from .models import Case, Message, Payment

# --------------------------------------------------------------------------- labels (en / te / hi)
TITLES: dict[str, dict[str, str]] = {
    "spoke": {"en": "She spoke: the case began", "te": "ఆమె మాట్లాడింది: కేసు మొదలైంది",
              "hi": "उन्होंने बोला: केस शुरू हुआ"},
    "readback_confirmed": {"en": "Read back to her, she said yes", "te": "తిరిగి చదివి వినిపించాం, ఆమె సరే అంది",
                           "hi": "पढ़कर सुनाया, उन्होंने हाँ कहा"},
    "work_logged": {"en": "Work day saved in the diary", "te": "డైరీలో పని రోజు నమోదైంది",
                    "hi": "डायरी में काम का दिन दर्ज"},
    "absence_logged": {"en": "Day off saved in the diary", "te": "డైరీలో సెలవు రోజు నమోదైంది",
                       "hi": "डायरी में छुट्टी का दिन दर्ज"},
    "diary_payment": {"en": "Payment noted in the diary", "te": "డైరీలో చెల్లింపు నమోదైంది",
                      "hi": "डायरी में पैसे मिलने की बात दर्ज"},
    "diary_note": {"en": "Diary note saved", "te": "డైరీ నోట్ నమోదైంది", "hi": "डायरी में नोट दर्ज"},
    "evidence_saved": {"en": "Proof saved in the diary", "te": "రుజువు డైరీలో భద్రపరిచాం",
                       "hi": "सबूत डायरी में सहेजा"},
    "note_made": {"en": "Voice note made ({step})", "te": "వాయిస్ నోట్ తయారైంది ({step})",
                  "hi": "वॉइस नोट बना ({step})"},
    "listen_twice": {"en": "Listen-twice check: amounts heard", "te": "రెండోసారి విని చూశాం: మొత్తాలు వినిపించాయి",
                     "hi": "दोबारा सुनकर जाँचा: रकम सुनाई दी"},
    "listen_twice_warn": {"en": "Listen-twice check: please listen again", "te": "రెండోసారి విని చూశాం: మళ్ళీ వినండి",
                          "hi": "दोबारा सुनकर जाँचा: एक बार फिर सुनें"},
    "sent": {"en": "Sent to the employer ({step})", "te": "యజమానికి పంపారు ({step})",
             "hi": "मालिक को भेजा ({step})"},
    "employer_replied": {"en": "The employer replied", "te": "యజమాని జవాబు ఇచ్చారు", "hi": "मालिक ने जवाब दिया"},
    "reply_translated": {"en": "Reply read out in her language", "te": "జవాబు ఆమె భాషలో వినిపించాం",
                         "hi": "जवाब उनकी भाषा में सुनाया"},
    "plan_chosen": {"en": "The employer chose to pay in parts", "te": "యజమాని వాయిదాల్లో చెల్లిస్తామన్నారు",
                    "hi": "मालिक ने किस्तों में देना चुना"},
    "reply_saved": {"en": "Employer's WhatsApp reply saved", "te": "యజమాని వాట్సాప్ జవాబు భద్రపరిచాం",
                    "hi": "मालिक का WhatsApp जवाब सहेजा"},
    "promised": {"en": "Promise noted", "te": "మాట నమోదైంది", "hi": "वादा दर्ज"},
    "promise_kept": {"en": "Promise kept", "te": "మాట నిలబెట్టుకున్నారు", "hi": "वादा निभाया"},
    "promise_broken": {"en": "Promise broken", "te": "మాట తప్పారు", "hi": "वादा टूटा"},
    "paid": {"en": "Paid", "te": "చెల్లించారు", "hi": "पैसे दिए"},
    "paid_alert": {"en": "Paisa aa gaya!", "te": "డబ్బులు వచ్చేశాయి!", "hi": "पैसा आ गया!"},
    "exit_kit": {"en": "Exit Kit worked out", "te": "ఎగ్జిట్ కిట్ లెక్క వేశాం", "hi": "Exit Kit का हिसाब बना"},
    "employer_listened": {"en": "The employer listened (time not recorded)",
                          "te": "యజమాని విన్నారు (సమయం నమోదు కాలేదు)", "hi": "मालिक ने सुना (समय दर्ज नहीं)"},
}
STEP_NAMES: dict[str, dict[str, str]] = {
    "polite": {"en": "Polite", "te": "మర్యాదగా", "hi": "विनम्र"},
    "firm": {"en": "Firm", "te": "గట్టిగా", "hi": "सख़्त"},
    "formal": {"en": "Formal letter", "te": "అధికారిక లేఖ", "hi": "औपचारिक पत्र"},
}
LANGS = ("en", "te", "hi")

# Exact-same-instant tiebreak (rows written by one request share a timestamp). Lower comes first.
KIND_RANK = {k: i for i, k in enumerate((
    "work_logged", "absence_logged", "diary_note", "diary_payment", "evidence_saved",
    "spoke", "readback_confirmed", "exit_kit", "note_made", "listen_twice", "listen_twice_warn", "sent",
    "employer_replied", "reply_translated", "reply_saved", "promised", "plan_chosen",
    "promise_kept", "promise_broken", "paid", "paid_alert",
))}
# Within one second, the case intake comes first (see the module docstring).
INTAKE = {"spoke": 0, "readback_confirmed": 1}
TO_EMPLOYER_STEPS = ("polite", "firm", "formal")


def title(kind: str, step: str | None = None) -> dict[str, str]:
    t = TITLES[kind]
    names = STEP_NAMES.get(step or "", {})
    return {lg: t[lg].replace("{step}", names.get(lg, step or "")).replace(" ()", "") for lg in LANGS}


def parse_at(value: str | None) -> Optional[dt.datetime]:
    """Stored ISO string -> aware datetime (naive = UTC, a date alone = midnight UTC). None if unusable."""
    if not value or not isinstance(value, str):
        return None
    try:
        d = dt.datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def media_url(key: str | None) -> str | None:
    return f"/api/media/{key}" if key else None


def balance_after(case: Case, paid_so_far: float) -> float:
    """The case screen's balance (Case.balance) as if `paid_so_far` had been paid: a detached copy."""
    return Case(worker_id=case.worker_id, employer_id=case.employer_id, total_due=case.total_due,
                amount_paid=paid_so_far).balance


def _listen_twice(m: Message) -> Optional[dict[str, Any]]:
    """The stored Listen-twice result for this message's CURRENT audio (cache file, read only)."""
    if not m.audio_path or m.id is None:
        return None
    try:
        p = storage.get_storage().local_path(m.audio_path)
    except (ValueError, OSError):
        return None
    if p is None:
        return None
    try:
        sha = verify_guard.audio_sha256(p.read_bytes())
    except OSError:
        return None
    hit = verify_guard.read_cache(m.id, sha)
    return hit if hit and hit.get("checked_at") else None


# --------------------------------------------------------------------------- builder
class _Timeline:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.skipped: list[dict[str, Any]] = []

    def add(self, kind: str, at: str | None, at_field: str, table: str, row_id: int | None, *,
            step: str | None = None, **extra: Any) -> None:
        when = parse_at(at)
        if when is None:
            if at:
                self.skipped.append({"kind": kind, "source_table": table, "source_id": row_id,
                                     "reason": f"unreadable {at_field}"})
            return
        ev: dict[str, Any] = {"at": at, "at_field": at_field, "kind": kind, "title": title(kind, step),
                              "source_table": table, "source_id": row_id}
        if step:
            ev["step"] = step
        ev.update({k: v for k, v in extra.items() if v is not None})
        self.rows.append({"_t": when, "_r": KIND_RANK.get(kind, 99), **ev})

    def sorted(self) -> list[dict[str, Any]]:
        rows = sorted(self.rows, key=lambda r: (r["_t"].replace(microsecond=0), INTAKE.get(r["kind"], 9), r["_t"],
                                                r["_r"], r["source_table"], r["source_id"] or 0))
        return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def _diary_kind(kind: str) -> str:
    return {"checkin": "work_logged", "absence": "absence_logged", "payment": "diary_payment",
            "note": "diary_note", "evidence": "evidence_saved"}.get(kind, "diary_note")


def build_story(s: Session, case_id: int) -> Optional[dict[str, Any]]:
    ctx: CaseCtx | None = load_ctx(s, case_id)
    if ctx is None:
        return None
    case = ctx.case
    tl = _Timeline()
    untimed: list[dict[str, Any]] = []

    # the case: her words, then the read-back she confirmed
    tl.add("spoke", case.created_at, "case.created_at", "case", case.id,
           text=(case.transcript or None), text_lang=case.transcript_lang if case.transcript else None)
    if case.readback_confirmed:
        tl.add("readback_confirmed", case.confirmed_at, "case.confirmed_at", "case", case.id)

    # messages (the ladder, replies, alerts). Scheduled reminders have not happened: left out.
    msgs = list(s.exec(select(Message).where(Message.case_id == case.id).order_by(Message.id)))
    for m in msgs:
        if m.direction == "to_employer" and m.step in TO_EMPLOYER_STEPS:
            tl.add("note_made", m.created_at, "message.created_at", "message", m.id, step=m.step,
                   audio_url=media_url(m.audio_path), pdf_url=media_url(m.pdf_path), language=m.language)
            lt = _listen_twice(m)
            if lt is not None:
                ok = bool(lt.get("verified"))
                tl.add("listen_twice" if ok else "listen_twice_warn", lt["checked_at"], "verify_cache.checked_at",
                       "message", m.id, step=m.step, verified=ok,
                       amounts_heard=lt.get("amounts_heard"), disclosure_heard=lt.get("disclosure_heard"))
            if m.sent_at:
                tl.add("sent", m.sent_at, "message.sent_at", "message", m.id, step=m.step,
                       audio_url=media_url(m.audio_path))
            if m.status == "played":
                untimed.append({"kind": "employer_listened", "title": title("employer_listened"),
                                "source_table": "message", "source_id": m.id, "step": m.step,
                                "reason": "message.status is 'played'; no time is stored"})
        elif m.direction == "from_employer" and m.step == "reply":
            tl.add("employer_replied", m.sent_at or m.created_at, "message.sent_at" if m.sent_at else
                   "message.created_at", "message", m.id, audio_url=media_url(m.audio_path), text=m.text,
                   text_worker_lang=m.text_worker_lang, language=m.language)
        elif m.direction == "to_worker" and m.step == "reply":
            tl.add("reply_translated", m.sent_at or m.created_at, "message.sent_at" if m.sent_at else
                   "message.created_at", "message", m.id, audio_url=media_url(m.audio_path), text=m.text,
                   language=m.language)
        elif m.direction == "to_worker" and m.step == "plan":
            tl.add("plan_chosen", m.sent_at or m.created_at, "message.sent_at" if m.sent_at else
                   "message.created_at", "message", m.id, text=m.text, language=m.language)
        elif m.direction == "to_worker" and m.step == "paid_alert":
            tl.add("paid_alert", m.sent_at or m.created_at, "message.sent_at" if m.sent_at else
                   "message.created_at", "message", m.id, audio_url=media_url(m.audio_path), text=m.text,
                   language=m.language)

    # payments actually received (planned / settled instalments are a plan, not money in hand)
    pays = list(s.exec(select(Payment).where(Payment.case_id == case.id).order_by(Payment.id)))
    for p in pays:
        if p.status != "paid":
            continue
        tl.add("paid", p.paid_at or p.created_at, "payment.paid_at" if p.paid_at else "payment.created_at",
               "payment", p.id, amount=round(float(p.amount), 2), amount_delta=-round(float(p.amount), 2),
               method=p.method, note=p.note)

    # Feature tables outside the core (inbox, exit kit) are not wiped by POST /api/demo/reset, and SQLite
    # reuses case ids, so a row stamped before this case existed belongs to an older case with the same id.
    born = parse_at(case.created_at)
    born = born.replace(microsecond=0) if born else None

    def older_than_case(at: str | None, table: str, row_id: int | None) -> bool:
        when = parse_at(at)
        if born is None or when is None or when.replace(microsecond=0) >= born:
            return False
        tl.skipped.append({"kind": table, "source_table": table, "source_id": row_id,
                           "reason": "stamped before this case was created (left from an older case with this id)"})
        return True

    # WhatsApp replies she saved (Share to Baaki) and the promises in them
    cards = [c for c in s.exec(select(InboxCard).where(InboxCard.case_id == case.id).order_by(InboxCard.id))
             if not older_than_case(c.created_at, "inboxcard", c.id)]
    card_ids = {c.id for c in cards}
    card_diary = {c.diary_entry_id for c in cards if c.diary_entry_id}
    for c in cards:
        tl.add("reply_saved", c.created_at, "inboxcard.created_at", "inboxcard", c.id,
               audio_url=media_url(c.audio_path), original_audio_url=media_url(c.original_audio_path),
               text=c.transcript or None, text_worker_lang=c.translation or None, said_on=c.said_on or None)
    for pr in s.exec(select(InboxPromise).where(InboxPromise.case_id == case.id).order_by(InboxPromise.id)):
        if pr.card_id not in card_ids:
            continue
        tl.add("promised", pr.created_at, "inboxpromise.created_at", "inboxpromise", pr.id,
               amount=pr.amount, is_rest=pr.is_rest or None, due_date=pr.due_date or None, quote=pr.quote or None,
               confirmed=pr.confirmed)
        if pr.status in ("kept", "broken"):
            tl.add(f"promise_{pr.status}", pr.status_at, "inboxpromise.status_at", "inboxpromise", pr.id,
                   amount=pr.amount, due_date=pr.due_date or None)

    # the hash-chained diary (check-ins against this case, or this worker + employer before it existed)
    for d in ctx.diary:
        if d.id in card_diary:
            continue  # the saved-reply card above is the same event
        tl.add(_diary_kind(d.kind), d.timestamp, "diaryentry.timestamp", "diaryentry", d.id,
               text=d.text or None, hash=(d.hash[:12] if d.hash else None))

    for k in s.exec(select(ExitKit).where(ExitKit.case_id == case.id).order_by(ExitKit.id)):
        if older_than_case(k.created_at, "exit_kit", k.id):
            continue
        tl.add("exit_kit", k.created_at, "exit_kit.created_at", "exit_kit", k.id, total=k.total, due_by=k.due_by)

    events = tl.sorted()

    # the meter: starts at the case total, falls with each payment (Case.balance logic)
    paid_so_far = 0.0
    for i, ev in enumerate(events):
        ev["seq"] = i + 1
        if ev["kind"] == "paid":
            paid_so_far = round(paid_so_far + ev["amount"], 2)
            ev["balance_after"] = balance_after(case, paid_so_far)

    paid_rows_total = round(sum(float(p.amount) for p in pays if p.status == "paid"), 2)
    return {
        "case": {
            "id": case.id, "status": case.status,
            "worker": {"name": ctx.worker.name, "language": ctx.worker.language},
            "employer": {"name": ctx.employer.name, "language": ctx.employer.language,
                         "fair_employer": ctx.employer.fair_employer},
            "created_at": case.created_at,
        },
        "total_due": ctx.total_due,
        "amount_paid": ctx.paid,
        "balance": ctx.balance,
        "paid_in_full": ctx.total_due > 0 and ctx.balance <= 0,
        "payments_match_case": abs(paid_rows_total - ctx.paid) < 0.01,
        "events": events,
        "untimed": untimed,
        "skipped": tl.skipped,
        "notes": [
            "Times are the stored times, unchanged. Events without a stored time are listed under 'untimed'.",
            "The meter starts at today's case total; if the total was recalculated, earlier totals are not stored.",
        ],
    }


__all__ = ["build_story", "balance_after", "parse_at", "title", "TITLES", "KIND_RANK"]
