"""The letter annex's chain check must not report a broken link when other homes' entries sit between this
employer's entries, and must still catch an edited entry."""
from sqlmodel import Session, SQLModel, create_engine

from app.letter import diary_chain_check
from app.models import DiaryEntry, Employer, Worker
from app.routes.cases import add_diary_entry


def _session():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return Session(eng)


def test_interleaved_homes_and_consent_are_not_a_broken_link():
    with _session() as s:
        w = Worker(name="Lakshmi", language="te-IN")
        a, b = Employer(name="Sharma ji", language="hi-en"), Employer(name="Reddy garu", language="te-IN")
        s.add_all([w, a, b]); s.flush()
        add_diary_entry(s, w.id, "Sharma ji, 2 h", employer_id=a.id)
        add_diary_entry(s, w.id, "Reddy garu, 3 h", employer_id=b.id)
        add_diary_entry(s, w.id, "Voice consent given", kind="consent")
        add_diary_entry(s, w.id, "Sharma ji, 2 h", employer_id=a.id)
        s.commit()
        shown = [e for e in s.query(DiaryEntry).order_by(DiaryEntry.id) if e.employer_id == a.id]
        assert len(shown) == 2
        assert diary_chain_check(shown) == (True, None)


def test_edited_entry_is_caught():
    with _session() as s:
        w = Worker(name="Lakshmi", language="te-IN")
        a = Employer(name="Sharma ji", language="hi-en")
        s.add_all([w, a]); s.flush()
        add_diary_entry(s, w.id, "Sharma ji, 2 h", employer_id=a.id)
        e2 = add_diary_entry(s, w.id, "Sharma ji, 2 h", employer_id=a.id)
        s.commit()
        e2.text = "Sharma ji, 8 h"  # changed after the fact
        shown = list(s.query(DiaryEntry).order_by(DiaryEntry.id))
        assert diary_chain_check(shown) == (False, 2)
