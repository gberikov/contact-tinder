"""Postgres-only: exercise the real worker queue (FOR UPDATE SKIP LOCKED). Skipped on SQLite."""
from __future__ import annotations

import pytest

from src.workers import import_worker
from tests.fakes.fake_people_client import FakePeopleClient, make_person
from tests.helpers import seed_account
from src.services import snapshot_service


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL (FOR UPDATE SKIP LOCKED)")


def test_worker_claims_and_runs_job(db, monkeypatch):
    account = seed_account(db)
    snapshot = snapshot_service.create_snapshot(db, account.id)

    # Claim uses with_for_update(skip_locked=True) — must execute on real Postgres.
    claimed = import_worker.claim_next_job(db)
    assert claimed is not None
    assert claimed.snapshot_id == snapshot.id
    db.rollback()  # release the row lock from the claim probe

    # Patch the Google client builder so run_once uses a deterministic fake.
    monkeypatch.setattr(
        import_worker, "build_client",
        lambda session, snap: FakePeopleClient([make_person(i) for i in range(4)], page_size=2),
    )
    assert import_worker.run_once(db) is True

    db.refresh(snapshot)
    assert snapshot.status == "complete"
    assert snapshot.contact_count == 4
    assert import_worker.run_once(db) is False  # no more queued jobs
