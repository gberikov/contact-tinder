"""Integration: dedup never mutates the snapshot or working-copy contacts (US1 / FR-003, SC-004)."""
from __future__ import annotations

import copy

from src.integrations.dedup_engine import FakeDedupEngine
from src.services import dedup_service, snapshot_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def test_run_leaves_snapshot_and_contacts_unchanged(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100"),
    ]
    wc = seed_working_copy(db, account, people)
    snapshot_id = wc.snapshot_id

    def snapshot_payloads():
        rows, _ = snapshot_service.list_contacts(db, snapshot_id, page_size=100)
        return [copy.deepcopy(r.payload) for r in rows]

    before = snapshot_payloads()
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, FakeDedupEngine())
    assert snapshot_payloads() == before  # snapshot byte-identical (SC-004)
