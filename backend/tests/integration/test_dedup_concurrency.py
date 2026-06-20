"""Integration: only one active run per working copy (US1 / FR-007)."""
from __future__ import annotations

import pytest

from src.core.errors import ConflictError
from src.services import dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def test_second_active_run_rejected(db):
    account = seed_account(db)
    wc = seed_working_copy(
        db, account, [dup_person(0, name="A B", phone="+1-202-555-0001")]
    )
    dedup_service.create_run(db, wc.id)  # stays queued (no worker in this test)
    with pytest.raises(ConflictError):
        dedup_service.create_run(db, wc.id)


def test_new_run_allowed_after_completion(db):
    from src.integrations.dedup_engine import FakeDedupEngine

    account = seed_account(db)
    wc = seed_working_copy(
        db, account, [dup_person(0, name="A B", phone="+1-202-555-0001")]
    )
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    # Completed → a fresh run is allowed.
    again = dedup_service.create_run(db, wc.id)
    assert again.id != run.id
