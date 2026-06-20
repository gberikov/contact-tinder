"""Integration: re-decide any contact (latest wins) + audit history (US1 / FR-006, D3)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.audit import AuditEntry
from src.models.triage import TriageDecision
from src.models.working_copy import WorkingCopyContact
from src.services import triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _wc(db):
    account = seed_account(db)
    people = [dup_person(i, name=f"P{i} Q{i}", phone=f"+{i}") for i in range(3)]
    return seed_working_copy(db, account, people)


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_redecide_updates_single_row_and_audits(db):
    wc = _wc(db)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contacts(db, wc)[0]

    triage_service.set_decision(db, ts.id, c.id, outcome="keep")
    triage_service.set_decision(db, ts.id, c.id, outcome="delete")

    rows = list(
        db.scalars(
            select(TriageDecision).where(
                TriageDecision.session_id == ts.id,
                TriageDecision.working_copy_contact_id == c.id,
            )
        )
    )
    assert len(rows) == 1 and rows[0].outcome == "delete"  # latest wins, one row

    audits = list(
        db.scalars(
            select(AuditEntry).where(AuditEntry.target_id == c.id).order_by(AuditEntry.occurred_at)
        )
    )
    actions = [a.action for a in audits]
    assert "contact.kept" in actions and "contact.queued_delete" in actions  # navigable history


def test_undo_returns_to_undecided(db):
    wc = _wc(db)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contacts(db, wc)[0]
    triage_service.set_decision(db, ts.id, c.id, outcome="keep")
    triage_service.undo_decision(db, ts.id, c.id)
    remaining = {x.id for x in triage_service.deck(db, ts.id, limit=10)[0]}
    assert c.id in remaining
