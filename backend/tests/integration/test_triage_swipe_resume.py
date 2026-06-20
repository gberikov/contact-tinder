"""Integration: swipe decisions persist, resume, and summarize; no Google calls (US1)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from src.services import triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _wc(db, n=4):
    account = seed_account(db)
    people = [dup_person(i, name=f"Name{i} Last{i}", phone=f"+{i}") for i in range(n)]
    return seed_working_copy(db, account, people)


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_decisions_persist_and_resume(db):
    wc = _wc(db, 4)
    ts, created = triage_service.open_session(db, wc.id)
    assert created
    contacts = _contacts(db, wc)

    triage_service.set_decision(db, ts.id, contacts[0].id, outcome="keep")
    triage_service.set_decision(db, ts.id, contacts[1].id, outcome="delete")

    # Resume: deck returns the remaining undecided in stable order.
    cards, _ = triage_service.deck(db, ts.id, limit=10)
    remaining_ids = {c.id for c in cards}
    assert remaining_ids == {contacts[2].id, contacts[3].id}

    s = triage_service.summary(db, ts)
    assert s == {"total": 4, "decided": 2, "keep": 1, "delete": 1, "processing": 0, "remaining": 2}


def test_session_completes_when_all_decided(db):
    wc = _wc(db, 2)
    ts, _ = triage_service.open_session(db, wc.id)
    for c in _contacts(db, wc):
        triage_service.set_decision(db, ts.id, c.id, outcome="keep")
    db.refresh(ts)
    assert ts.status == "complete" and ts.finished_at is not None


def test_no_google_write_on_swipe(db):
    # There is no PeopleWriteClient used anywhere in the swipe path; deciding only touches the DB.
    wc = _wc(db, 1)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contacts(db, wc)[0]
    decision = triage_service.set_decision(db, ts.id, c.id, outcome="delete")
    assert decision.outcome == "delete"
    # The contact stays active (staged only) — nothing deleted in Google.
    db.refresh(c)
    assert c.status == "active"
