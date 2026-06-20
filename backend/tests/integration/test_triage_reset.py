"""Integration: reset a session back to the initial stage — start triage over (US1)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.triage import ProcessingItem, TriageDecision
from src.models.working_copy import WorkingCopyContact
from src.services import processing_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_reset_clears_decisions_and_reverts_edits(db):
    account = seed_account(db)
    wc = seed_working_copy(
        db, account, [dup_person(i, name=f"Boris{i} Petrov{i}", phone=f"+{i}") for i in range(2)]
    )
    ts, _ = triage_service.open_session(db, wc.id)
    c0, c1 = _contacts(db, wc)

    triage_service.set_decision(db, ts.id, c0.id, outcome="delete")
    triage_service.set_decision(db, ts.id, c1.id, outcome="process", wants_transliterate=True)
    sug = processing_service.transliteration_suggestion(db, c1.id)
    processing_service.accept_transliteration(db, c1.id, sug["fields"])
    db.refresh(c1)
    assert c1.payload["names"][0]["givenName"].startswith("Б")  # transliterated

    triage_service.reset_session(db, ts.id)

    # Decisions and processing queue are gone; everything is undecided again.
    assert db.scalars(select(TriageDecision).where(TriageDecision.session_id == ts.id)).all() == []
    assert db.scalars(select(ProcessingItem).where(ProcessingItem.session_id == ts.id)).all() == []
    s = triage_service.summary(db, ts)
    assert s["decided"] == 0 and s["remaining"] == 2

    # Staged edit reverted: the card is pristine again.
    db.refresh(c1)
    assert c1.payload["names"][0]["givenName"] == "Boris1"
    db.refresh(ts)
    assert ts.status == "in_progress"
