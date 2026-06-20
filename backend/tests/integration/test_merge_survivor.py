"""Integration: survivor-based merge (US3 / FR-016, SC-004)."""
from __future__ import annotations

import copy

from src.integrations.dedup_engine import FakeDedupEngine
from src.models.audit import AuditEntry
from src.models.working_copy import WorkingCopyContact
from src.services import cluster_service, dedup_service, snapshot_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _cluster(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
    ]
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    return wc, cluster_service.list_clusters(db, run.id)[0]


def test_merge_unions_fields_and_retires_others(db):
    wc, cluster = _cluster(db)
    snapshot_id = wc.snapshot_id
    snap_before = [copy.deepcopy(r.payload)
                   for r in snapshot_service.list_contacts(db, snapshot_id, page_size=100)[0]]

    record = cluster_service.merge_cluster(db, cluster.id)

    survivor = db.get(WorkingCopyContact, record.survivor_contact_id)
    assert survivor.status == "active"
    # Both emails unioned onto the survivor.
    emails = {e["value"] for e in survivor.payload.get("emailAddresses", [])}
    assert {"john@x.com", "jon@y.com"} <= emails

    retired = db.query(WorkingCopyContact).filter_by(working_copy_id=wc.id, status="retired").all()
    assert len(retired) == 1
    db.refresh(cluster)
    assert cluster.status == "merged"

    # Snapshot untouched (SC-004).
    snap_after = [copy.deepcopy(r.payload)
                  for r in snapshot_service.list_contacts(db, snapshot_id, page_size=100)[0]]
    assert snap_after == snap_before

    # Audit entry written.
    actions = {a.action for a in db.query(AuditEntry).all()}
    assert "cluster.merged" in actions


def test_active_set_shrinks_by_one(db):
    wc, cluster = _cluster(db)
    active_before = db.query(WorkingCopyContact).filter_by(
        working_copy_id=wc.id, status="active"
    ).count()
    cluster_service.merge_cluster(db, cluster.id)
    active_after = db.query(WorkingCopyContact).filter_by(
        working_copy_id=wc.id, status="active"
    ).count()
    assert active_after == active_before - 1
