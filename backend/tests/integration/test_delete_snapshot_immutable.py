"""Integration: the source snapshot is never mutated by a delete batch or undo (US3 / Principle II)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.snapshot import SnapshotContact
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _snapshot_payloads(db, snapshot_id):
    rows = db.scalars(
        select(SnapshotContact).where(SnapshotContact.snapshot_id == snapshot_id)
    )
    return {r.resource_name: dict(r.payload) for r in rows}


def test_snapshot_byte_identical_through_commit_and_undo(db):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    wc = seed_working_copy(
        db, account, [dup_person(i, name=f"N{i} L{i}", phone=f"+{i}") for i in range(2)]
    )
    before = _snapshot_payloads(db, wc.snapshot_id)

    ts, _ = triage_service.open_session(db, wc.id)
    for c in db.scalars(
        select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id)
    ):
        triage_service.set_decision(db, ts.id, c.id, outcome="delete")

    batch = delete_batch_service.create_batch(db, wc.id)
    delete_batch_service.confirm(db, batch.id)
    delete_batch_service.process_batch(db, batch.id, FakePeopleWriteClient())
    delete_batch_service.request_undo(db, batch.id)
    delete_batch_service.process_undo(db, batch.id, FakePeopleWriteClient())

    assert _snapshot_payloads(db, wc.snapshot_id) == before  # untouched
