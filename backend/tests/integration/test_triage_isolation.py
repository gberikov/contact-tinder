"""Integration: per-working-copy isolation — one session can't act on another's contacts (US1)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from src.core.errors import ConflictError
from src.models.working_copy import WorkingCopyContact
from src.services import triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_decision_across_working_copies_is_blocked(db):
    acc_a = seed_account(db, gid="g-A", email="a@x.com")
    acc_b = seed_account(db, gid="g-B", email="b@x.com")
    wc_a = seed_working_copy(db, acc_a, [dup_person(0, name="A One", phone="+1")], label="A")
    wc_b = seed_working_copy(db, acc_b, [dup_person(1, name="B One", phone="+2")], label="B")

    ts_a, _ = triage_service.open_session(db, wc_a.id)
    foreign_contact = _contacts(db, wc_b)[0]

    # A contact from working copy B is not an active survivor of session A's working copy.
    with pytest.raises(ConflictError):
        triage_service.set_decision(db, ts_a.id, foreign_contact.id, outcome="keep")

    # Session A's summary still reflects only its own working copy.
    assert triage_service.summary(db, ts_a)["total"] == 1
