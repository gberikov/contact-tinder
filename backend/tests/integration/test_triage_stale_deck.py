"""Integration: working copy changes after a session starts (FR-027, D11)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from src.services import triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_retired_contact_excluded_from_deck_and_summary(db):
    account = seed_account(db)
    wc = seed_working_copy(
        db,
        account,
        [dup_person(i, name=f"N{i} L{i}", phone=f"+{i}") for i in range(3)],
    )
    ts, _ = triage_service.open_session(db, wc.id)
    contacts = _contacts(db, wc)

    triage_service.set_decision(db, ts.id, contacts[0].id, outcome="delete")

    # Simulate a dedup re-run retiring a decided contact underneath the session.
    contacts[0].status = "retired"
    db.commit()

    s = triage_service.summary(db, ts)
    assert s["total"] == 2  # only active survivors counted now
    assert s["delete"] == 0  # the stale decision is excluded (FR-027)

    deck_ids = {c.id for c in triage_service.deck(db, ts.id, limit=10)[0]}
    assert contacts[0].id not in deck_ids
