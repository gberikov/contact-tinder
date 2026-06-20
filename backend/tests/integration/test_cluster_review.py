"""Integration: cluster review is read-only with usable member details (US2 / FR-012, FR-013)."""
from __future__ import annotations

from src.integrations.dedup_engine import FakeDedupEngine
from src.services import cluster_service, dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _completed(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
    ]
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    return run


def test_members_carry_contact_summary(db):
    run = _completed(db)
    clusters = cluster_service.list_clusters(db, run.id)
    assert len(clusters) == 1
    pairs = cluster_service.member_contacts(db, clusters[0])
    summaries = [cluster_service.contact_summary(c) for _, c in pairs]
    assert all(s["displayName"] for s in summaries)
    assert all(s["primaryPhone"] for s in summaries)
    assert all(s["status"] == "active" for s in summaries)


def test_viewing_does_not_mutate(db):
    run = _completed(db)
    cluster = cluster_service.list_clusters(db, run.id)[0]
    status_before = cluster.status
    cluster_service.get_cluster(db, cluster.id)
    cluster_service.member_contacts(db, cluster)
    db.refresh(cluster)
    assert cluster.status == status_before == "pending"
