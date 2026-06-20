"""Integration: resolution guards — FR-019 (per-run dismiss), FR-020, FR-008, SC-005."""
from __future__ import annotations

import pytest

from src.core.errors import ConflictError
from src.integrations.dedup_engine import FakeDedupEngine
from src.models.dedup import DuplicateCluster
from src.services import cluster_service, dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy

PEOPLE = [
    dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
    dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
]


def _run(db, wc):
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    return run


def test_no_cluster_resolved_without_action(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, PEOPLE)
    run = _run(db, wc)
    # Right after a completed run, every cluster is still pending (SC-005).
    assert all(c.status == "pending" for c in db.query(DuplicateCluster).all())
    assert run.cluster_count == 1


def test_dismiss_is_per_run_and_redetected(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, PEOPLE)
    run1 = _run(db, wc)
    c1 = cluster_service.list_clusters(db, run1.id)[0]
    cluster_service.dismiss_cluster(db, c1.id)
    assert cluster_service.list_clusters(db, run1.id, status="pending") == []

    # A new run re-detects the same pair as a fresh pending cluster (FR-019, per-run only).
    run2 = _run(db, wc)
    fresh = cluster_service.list_clusters(db, run2.id, status="pending")
    assert len(fresh) == 1


def test_resolving_with_retired_member_blocked(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, PEOPLE)
    run = _run(db, wc)
    cluster = cluster_service.list_clusters(db, run.id)[0]
    cluster_service.merge_cluster(db, cluster.id)  # retires a member
    # Re-merging a non-pending cluster is blocked (FR-020 / not pending).
    with pytest.raises(ConflictError):
        cluster_service.merge_cluster(db, cluster.id)


def test_resolving_superseded_cluster_blocked(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, PEOPLE)
    run1 = _run(db, wc)
    old_cluster = cluster_service.list_clusters(db, run1.id)[0]
    _run(db, wc)  # second run supersedes run1's pending clusters (FR-008)
    db.refresh(old_cluster)
    assert old_cluster.status == "superseded"
    with pytest.raises(ConflictError):
        cluster_service.merge_cluster(db, old_cluster.id)
    with pytest.raises(ConflictError):
        cluster_service.dismiss_cluster(db, old_cluster.id)
