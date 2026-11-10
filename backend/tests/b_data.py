"""Synthetic demo rows for the messages / employer-side tests. Fictional people only."""
from __future__ import annotations

import hashlib

import httpx

from app import db
from app.models import Case, CaseItem, DiaryEntry, Employer, Worker


def make_case(worker_name="Lakshmi", worker_lang="te-IN", employer_name="Sharma ji", employer_lang="hi-en",
              monthly=4000, months=(("2026-08", "2026-09-07"), ("2026-09", "2026-10-07"), ("2026-10", "2026-11-07")),
              cut=1000.0, diary_days=5, shortfall_info=0.0, transcript="మూడు నెలల జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు.",
              upi="lakshmi.demo@upi") -> dict:
    with db.session() as s:
        w = Worker(name=worker_name, language=worker_lang, upi_vpa=upi)
        e = Employer(name=employer_name, language=employer_lang, locality="Banjara Hills")
        s.add(w)
        s.add(e)
        s.commit()
        total = monthly * len(months) + cut
        c = Case(worker_id=w.id, employer_id=e.id, monthly_wage=monthly, total_due=total, months_unpaid=len(months),
                 transcript=transcript, transcript_lang=worker_lang, status="confirmed")
        s.add(c)
        s.commit()
        for m, due in months:
            s.add(CaseItem(case_id=c.id, kind="unpaid_wage", label=f"Unpaid wages {m}", month=m, amount=monthly,
                           due_date=due, source="Code on Wages, 2019, s.17(1)"))
        if cut:
            s.add(CaseItem(case_id=c.id, kind="illegal_deduction", label="Sick-day cut", month="2026-07", amount=cut,
                           due_date="2026-08-07", source="Code on Wages, 2019, s.18, s.20(2)"))
        if shortfall_info:
            s.add(CaseItem(case_id=c.id, kind="min_wage_shortfall", label="Shortfall", amount=shortfall_info,
                           is_estimate=True, included_in_total=False, source="G.O.Ms.No.6 (estimate)"))
        prev = ""
        for i in range(diary_days):
            text = f"Sharma ji ke ghar, do ghante (day {i + 1})"
            h = hashlib.sha256(f"{prev}|{text}".encode()).hexdigest()
            s.add(DiaryEntry(worker_id=w.id, employer_id=e.id, case_id=c.id, text=text, prev_hash=prev, hash=h))
            prev = h
        s.commit()
        return {"worker_id": w.id, "employer_id": e.id, "case_id": c.id, "token": c.employer_token, "total": total}


def tts_ok(ogg: bytes):
    def handler(request):
        return httpx.Response(200, content=ogg, headers={"content-type": "audio/ogg"})
    return handler


def wav_ok(wav: bytes):
    def handler(request):
        return httpx.Response(200, content=wav, headers={"content-type": "audio/wav"})
    return handler
