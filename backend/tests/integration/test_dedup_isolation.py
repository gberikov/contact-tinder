"""Integration: per-account / per-working-copy isolation (US3 / FR-022, Principle I)."""
from __future__ import annotations

import pytest

from src.core.errors import ConflictError, NotFoundError
from src.integrations.dedup_engine import FakeDedupEngine
from src.services import cluster_service, dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy

PEOPLE = [
    dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
    dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
]


def test_runs_and_clusters_isolated_between_accounts(db):
    acct_a = seed_account(db, gid="g-A", email="a@example.com")
    acct_b = seed_account(db, gid="g-B", email="b@example.com")
    wc_a = seed_working_copy(db, acct_a, PEOPLE, label="A")
    wc_b = seed_working_copy(db, acct_b, PEOPLE, label="B")

    run_a = dedup_service.create_run(db, wc_a.id)
    dedup_service.run_dedup_job(db, run_a.id, FakeDedupEngine())

    # Account B's working copy has no runs and cannot see A's run.
    assert dedup_service.list_runs(db, wc_b.id) == []
    runs_a = dedup_service.list_runs(db, wc_a.id)
    assert len(runs_a) == 1 and runs_a[0].working_copy_id == wc_a.id

    # A's clusters belong only to A's working copy.
    clusters_a = cluster_service.list_clusters(db, run_a.id)
    assert all(c.working_copy_id == wc_a.id for c in clusters_a)


def test_unknown_ids_not_found(db):
    import uuid

    with pytest.raises(NotFoundError):
        dedup_service.get_run(db, uuid.uuid4())
    with pytest.raises(NotFoundError):
        cluster_service.get_cluster(db, uuid.uuid4())
    with pytest.raises(NotFoundError):
        cluster_service.undo_merge(db, uuid.uuid4())


def test_merge_across_accounts_does_not_leak(db):
    acct_a = seed_account(db, gid="g-A", email="a@example.com")
    acct_b = seed_account(db, gid="g-B", email="b@example.com")
    wc_a = seed_working_copy(db, acct_a, PEOPLE, label="A")
    seed_working_copy(db, acct_b, PEOPLE, label="B")

    run_a = dedup_service.create_run(db, wc_a.id)
    dedup_service.run_dedup_job(db, run_a.id, FakeDedupEngine())
    cluster_a = cluster_service.list_clusters(db, run_a.id)[0]

    record = cluster_service.merge_cluster(db, cluster_a.id)
    # The merge only affected account A's working copy.
    assert record.working_copy_id == wc_a.id
