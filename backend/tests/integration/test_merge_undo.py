"""Integration: merge undo restores exact pre-merge state (US3 / FR-018, SC-003)."""
from __future__ import annotations

import copy

from src.integrations.dedup_engine import FakeDedupEngine
from src.models.working_copy import WorkingCopyContact
from src.services import cluster_service, dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
        dup_person(2, name="Alice Brown", phone="+1-303-555-0199", email="alice@z.com"),
    ]
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    return wc, cluster_service.list_clusters(db, run.id)[0]


def _active_payloads(db, wc_id):
    rows = db.query(WorkingCopyContact).filter_by(working_copy_id=wc_id, status="active").all()
    return sorted((copy.deepcopy(r.payload) for r in rows), key=lambda p: str(p))


def test_undo_restores_active_set(db):
    wc, cluster = _setup(db)
    before = _active_payloads(db, wc.id)

    record = cluster_service.merge_cluster(db, cluster.id)
    assert _active_payloads(db, wc.id) != before  # changed by merge

    restored_cluster = cluster_service.undo_merge(db, record.id)
    assert restored_cluster.status == "pending"
    assert _active_payloads(db, wc.id) == before  # exact restore (SC-003)


def test_repeated_merge_undo_cycles_are_stable(db):
    wc, cluster = _setup(db)
    before = _active_payloads(db, wc.id)
    for _ in range(3):
        record = cluster_service.merge_cluster(db, cluster.id)
        cluster_service.undo_merge(db, record.id)
        db.refresh(cluster)
    assert _active_payloads(db, wc.id) == before


def test_double_undo_conflicts(db):
    import pytest

    from src.core.errors import ConflictError

    wc, cluster = _setup(db)
    record = cluster_service.merge_cluster(db, cluster.id)
    cluster_service.undo_merge(db, record.id)
    with pytest.raises(ConflictError):
        cluster_service.undo_merge(db, record.id)
