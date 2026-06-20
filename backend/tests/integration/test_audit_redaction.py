"""Integration: dedup actions are audited with no secrets (T042 / FR-021, SC-006)."""
from __future__ import annotations

import json

from src.integrations.dedup_engine import FakeDedupEngine
from src.models.audit import AuditEntry
from src.services import cluster_service, dedup_service
from tests.helpers import dup_person, seed_account, seed_working_copy

_FORBIDDEN = ("refresh", "access-token", "token", "password", "secret")


def test_run_merge_undo_dismiss_all_audited_without_secrets(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
        dup_person(2, name="Sam Lee", phone="+1-303-555-0001", email="sam@z.com"),
        dup_person(3, name="Samuel Lee", phone="+1-303-555-0001", email="samuel@z.com"),
    ]
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())

    clusters = cluster_service.list_clusters(db, run.id)
    record = cluster_service.merge_cluster(db, clusters[0].id)
    cluster_service.undo_merge(db, record.id)
    cluster_service.dismiss_cluster(db, clusters[1].id)

    actions = {a.action for a in db.query(AuditEntry).all()}
    assert {
        "dedup.run.started",
        "dedup.run.completed",
        "cluster.merged",
        "merge.undone",
        "cluster.dismissed",
    } <= actions

    # No audit detail blob may contain a secret/token (SC-006).
    for entry in db.query(AuditEntry).all():
        blob = json.dumps(entry.details or {}).lower()
        assert not any(word in blob for word in _FORBIDDEN)
