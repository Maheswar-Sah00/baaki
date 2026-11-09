"""Demo seed (synthetic): Lakshmi's three homes and Rafiq's reverse case. POST /api/demo/reset rebuilds it.

Story (docs/BUILD_BRIEF.md), "today" = 9 Nov 2026:
* Lakshmi (Telugu maid, Hyderabad), 3 homes:
  - Sharma ji (Hinglish): Rs 4,000 a month for 2 hours a day; Aug, Sep, Oct 2026 unpaid (Rs 12,000) and Rs 1,000
    cut in July for 2 sick days. Under s.20(2) a cut for her own absence may be up to 2/26 of the month
    (Rs 308), so Baaki claims back the excess Rs 692: contractual baaki Rs 12,692. The meter shows what she
    SAID (Rs 13,000); the case shows what the law supports. Set SHARMA_CUT_REASON = "employer_away" (the
    family was away, which is not her absence) and the full Rs 1,000 is reclaimable: Rs 13,000.
  - Reddy garu (Telugu): pays Rs 5,000 for 2 hours a day in full, signed a Kaam Patta, Fair Employer.
  - Mehta madam (Hinglish): Rs 2,500 for 2 hours a day, paid, but below the estimated minimum (Rs 4,000):
    hidden baaki Rs 1,500 a month, Rs 7,500 for Jun-Oct 2026 (estimate, G.O.Ms.No.6).
* Rafiq (Hinglish cook) with Rao garu (Telugu employer): Rs 7,000 a month for 3 hours a day, Sep and Oct unpaid:
  Rs 14,000 (minimum for 3 hours as a cook is Rs 6,937.50, so no shortfall).
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, SQLModel, delete

from . import db
from .models import ALL_TABLES, Case, Employer, Payment, Worker
from .routes.cases import add_diary_entry, apply_calc

DEMO_TODAY = dt.date(2026, 11, 9)
SHARMA_CUT_REASON = "sick"  # brief: "Rs 1,000 cut for 2 sick days"

TRANSCRIPTS = {
    "sharma": ("శర్మ గారు మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు. జూలైలో రెండు రోజులు జ్వరం వచ్చిందని "
               "వెయ్యి రూపాయలు కట్ చేశారు. రోజుకు రెండు గంటల పని."),
    "reddy": "రెడ్డి గారు నెలకు ఐదు వేలు ఇస్తారు, ప్రతి నెల ఐదో తారీఖు లోపల. రోజుకు రెండు గంటలు.",
    "mehta": "మెహతా మేడమ్ ఇంట్లో రోజుకు రెండు గంటల పని, నెలకు రెండు వేల ఐదు వందలు ఇస్తారు.",
    "rao": "Rao garu ne do mahine ki salary nahi di, saat hazaar mahina, roz teen ghante khana banata hoon.",
}


def _months(a: str, b: str) -> list[str]:
    out, y, m = [], int(a[:4]), int(a[5:7])
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _wipe(s: Session) -> None:
    for t in reversed(ALL_TABLES):  # children first
        s.exec(delete(t))  # type: ignore[call-overload]
    s.commit()


def seed(s: Session, today: dt.date = DEMO_TODAY) -> dict[str, Any]:
    _wipe(s)
    lakshmi = Worker(name="Lakshmi", language="te-IN", phone="+91 90000 00001", category="unskilled",
                     work_type="housekeeping", upi_vpa="lakshmi.demo@upi")
    rafiq = Worker(name="Rafiq", language="hi-en", phone="+91 90000 00002", category="skilled", work_type="cooking",
                   upi_vpa="rafiq.demo@upi")
    sharma = Employer(name="Sharma ji", language="hi-en", locality="Ameerpet")
    reddy = Employer(name="Reddy garu", language="te-IN", locality="Kukatpally", fair_employer=True,
                     kaam_patta_signed=True)
    mehta = Employer(name="Mehta madam", language="hi-en", locality="Begumpet")
    rao = Employer(name="Rao garu", language="te-IN", locality="Madhapur")
    for o in (lakshmi, rafiq, sharma, reddy, mehta, rao):
        s.add(o)
    s.flush()

    def mk(worker: Worker, emp: Employer, key: str, facts: dict[str, Any], include_shortfall: bool = False,
           status: str = "confirmed") -> Case:
        c = Case(worker_id=worker.id, employer_id=emp.id, transcript=TRANSCRIPTS[key],
                 transcript_lang=worker.language, status=status, work_type=facts["work_type"],
                 readback_confirmed=status != "draft", confirmed_at=db.now_iso() if status != "draft" else None)
        s.add(c)
        s.flush()
        facts = {**facts, "extraction": {"source": "seed", "warnings": []}}
        apply_calc(s, c, facts, include_shortfall=include_shortfall, today=today)
        return c

    c_sharma = mk(lakshmi, sharma, "sharma", {
        "employer_name": "Sharma ji", "work_type": "housekeeping", "monthly_wage": 4000, "hours_per_day": 2,
        "days_per_week": 6, "months_unpaid": 3, "unpaid_months": ["2026-08", "2026-09", "2026-10"],
        "paid_months": {"2026-06": 4000, "2026-07": 4000},
        "deductions": [{"amount": 1000, "reason": SHARMA_CUT_REASON, "days_absent": 2, "month": "2026-07"}],
        "reasons": ["salary held back for three months", "Rs 1,000 cut for 2 sick days in July"],
    })
    c_reddy = mk(lakshmi, reddy, "reddy", {
        "employer_name": "Reddy garu", "work_type": "housekeeping", "monthly_wage": 5000, "hours_per_day": 2,
        "days_per_week": 6, "months_unpaid": 0, "paid_months": {m: 5000 for m in _months("2026-06", "2026-10")},
    }, status="paid")
    c_mehta = mk(lakshmi, mehta, "mehta", {
        "employer_name": "Mehta madam", "work_type": "housekeeping", "monthly_wage": 2500, "hours_per_day": 2,
        "days_per_week": 6, "months_unpaid": 0, "paid_months": {m: 2500 for m in _months("2026-06", "2026-10")},
    }, include_shortfall=False, status="draft")
    c_rao = mk(rafiq, rao, "rao", {
        "employer_name": "Rao garu", "work_type": "cooking", "monthly_wage": 7000, "hours_per_day": 3,
        "days_per_week": 6, "months_unpaid": 2, "unpaid_months": ["2026-09", "2026-10"],
        "paid_months": {"2026-07": 7000, "2026-08": 7000},
    })
    s.add(Payment(case_id=c_reddy.id, amount=5000, method="upi", status="paid", paid_at="2026-11-05T10:12:00Z",
                  note="October salary"))

    # Kaam Diary: hash-chained check-ins (evidence annex for the formal letter)
    for day, text in [("2026-10-27", "Aaj Sharma ji ke ghar, do ghante"), ("2026-10-28", "Aaj Sharma ji ke ghar, do ghante"),
                      ("2026-10-29", "ఈరోజు శర్మ గారి ఇంట్లో రెండు గంటలు"), ("2026-10-30", "Aaj Sharma ji ke ghar, do ghante"),
                      ("2026-10-31", "ఈరోజు శర్మ గారి ఇంట్లో రెండు గంటలు")]:
        add_diary_entry(s, lakshmi.id, text, employer_id=sharma.id, case_id=c_sharma.id,
                        timestamp=f"{day}T04:30:00.000000Z")
    add_diary_entry(s, lakshmi.id, "Reddy garu: October jeetham vachindi, ayidu velu", employer_id=reddy.id,
                    case_id=c_reddy.id, kind="payment", timestamp="2026-11-05T10:15:00.000000Z")
    s.commit()
    return {
        "today": today.isoformat(),
        "workers": {"lakshmi": lakshmi.id, "rafiq": rafiq.id},
        "employers": {"sharma": sharma.id, "reddy": reddy.id, "mehta": mehta.id, "rao": rao.id},
        "cases": {"sharma": c_sharma.id, "reddy": c_reddy.id, "mehta": c_mehta.id, "rao": c_rao.id},
        "employer_tokens": {"sharma": c_sharma.employer_token, "reddy": c_reddy.employer_token,
                            "mehta": c_mehta.employer_token, "rao": c_rao.employer_token},
        "totals": {"sharma": c_sharma.total_due, "reddy": c_reddy.total_due, "mehta_shortfall": c_mehta.shortfall_estimate,
                   "rao": c_rao.total_due},
    }


def reset() -> dict[str, Any]:
    eng = db.get_engine()
    db.init_db(eng)
    SQLModel.metadata.create_all(eng)
    with db.session() as s:
        return seed(s)


__all__ = ["seed", "reset", "DEMO_TODAY"]
