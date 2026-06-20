"""Integration: engine output → clusters (US1 / FR-005, D5)."""
from __future__ import annotations

from src.integrations.dedup_engine import FakeDedupEngine
from src.models.dedup import ClusterMember, DuplicateCluster
from src.services import dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _run(db, people):
    account = seed_account(db)
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    db.refresh(run)
    return wc, run


def test_duplicates_grouped_with_confidence(db):
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="(202) 555-0100", email="jon@y.com"),
        dup_person(2, name="Alice Brown", phone="+1-303-555-0199", email="alice@z.com"),
    ]
    wc, run = _run(db, people)
    assert run.status == "completed"
    assert run.cluster_count == 1

    clusters = db.query(DuplicateCluster).filter_by(working_copy_id=wc.id).all()
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.size == 2
    assert cluster.confidence > 0.9  # phone match scores high
    members = db.query(ClusterMember).filter_by(cluster_id=cluster.id).all()
    assert len(members) == 2


def test_no_duplicates_zero_clusters(db):
    people = [
        dup_person(0, name="A B", phone="+1-202-555-0001", email="a@x.com"),
        dup_person(1, name="C D", phone="+1-202-555-0002", email="c@x.com"),
    ]
    _, run = _run(db, people)
    assert run.status == "completed"
    assert run.cluster_count == 0
    assert db.query(DuplicateCluster).count() == 0


def test_email_only_match_clusters(db):
    people = [
        dup_person(0, name="Bob R", phone="+1-202-555-1000", email="shared@x.com"),
        dup_person(1, name="Bobby R", phone="+1-202-555-2000", email="shared@x.com"),
    ]
    _, run = _run(db, people)
    assert run.cluster_count == 1
