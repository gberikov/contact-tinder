"""Integration: delete batch — snapshot before any delete, preview, confirm, commit (US3)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _grant_write_scope(db, account):
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()


def _setup(db, n=2):
    account = seed_account(db)
    _grant_write_scope(db, account)
    wc = seed_working_copy(
        db, account, [dup_person(i, name=f"N{i} L{i}", phone=f"+{i}") for i in range(n)]
    )
    ts, _ = triage_service.open_session(db, wc.id)
    contacts = list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )
    for c in contacts:
        triage_service.set_decision(db, ts.id, c.id, outcome="delete")
    return wc, contacts


def test_snapshot_captured_before_any_delete(db):
    wc, contacts = _setup(db, 2)
    batch = delete_batch_service.create_batch(db, wc.id)
    assert batch.status == "staged" and batch.total_count == 2
    # Every record has a restorable snapshot and nothing has been deleted yet (SC-002).
    for rec in batch.records:
        assert rec.status == "pending"
        assert rec.payload_before  # full payload captured


def test_preview_then_commit(db):
    wc, contacts = _setup(db, 2)
    batch = delete_batch_service.create_batch(db, wc.id)
    records = delete_batch_service.preview(db, batch.id)
    assert len(records) == 2
    db.refresh(batch)
    assert batch.status == "previewed"

    delete_batch_service.confirm(db, batch.id)
    client = FakePeopleWriteClient()
    delete_batch_service.process_batch(db, batch.id, client)

    db.refresh(batch)
    assert batch.status == "committed" and batch.deleted_count == 2
    assert sorted(client.deleted) == sorted(c.origin_resource_name for c in contacts)
    for c in contacts:
        db.refresh(c)
        assert c.status == "retired"


def test_absent_contact_counts_as_success(db):
    wc, contacts = _setup(db, 1)
    batch = delete_batch_service.create_batch(db, wc.id)
    delete_batch_service.confirm(db, batch.id)
    # Google reports the contact already gone.
    client = FakePeopleWriteClient(absent={contacts[0].origin_resource_name})
    delete_batch_service.process_batch(db, batch.id, client)
    db.refresh(batch)
    assert batch.status == "committed" and batch.deleted_count == 1
    assert batch.records[0].status == "skipped_absent"
