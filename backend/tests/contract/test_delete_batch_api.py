"""Contract: delete-batch endpoints (US3)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _decide_deletes(client, db, account, *, label):
    wc = seed_working_copy(db, account, [dup_person(0, name="Del One", phone="+1")], label=label)
    cid = db.scalar(
        select(WorkingCopyContact.id).where(WorkingCopyContact.working_copy_id == wc.id)
    )
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    client.put(f"/api/triage-sessions/{sid}/decisions/{cid}", json={"outcome": "delete"})
    return wc


def test_create_preview_confirm(client, db):
    account = seed_account(db)
    account.granted_scopes += " " + get_settings().google_contacts_write_scope
    db.commit()
    wc = _decide_deletes(client, db, account, label="wc")

    created = client.post(f"/api/working-copies/{wc.id}/delete-batches")
    assert created.status_code == 201 and created.json()["status"] == "staged"
    bid = created.json()["id"]

    assert client.get(f"/api/delete-batches/{bid}").status_code == 200
    preview = client.get(f"/api/delete-batches/{bid}/preview")
    assert preview.status_code == 200 and len(preview.json()) == 1

    confirm = client.post(f"/api/delete-batches/{bid}/confirm")
    assert confirm.status_code == 202 and confirm.json()["status"] == "committing"


def test_create_with_no_deletions_409(client, db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [dup_person(0, name="Keep Me", phone="+1")])
    client.post(f"/api/working-copies/{wc.id}/triage-sessions")
    resp = client.post(f"/api/working-copies/{wc.id}/delete-batches")
    assert resp.status_code == 409


def test_confirm_without_scope_403(client, db):
    account = seed_account(db)  # no write scope
    wc = _decide_deletes(client, db, account, label="noscope")
    bid = client.post(f"/api/working-copies/{wc.id}/delete-batches").json()["id"]
    resp = client.post(f"/api/delete-batches/{bid}/confirm")
    assert resp.status_code == 403


def test_undo_requires_committed(client, db):
    account = seed_account(db)
    account.granted_scopes += " " + get_settings().google_contacts_write_scope
    db.commit()
    wc = _decide_deletes(client, db, account, label="undo")
    bid = client.post(f"/api/working-copies/{wc.id}/delete-batches").json()["id"]
    client.post(f"/api/delete-batches/{bid}/confirm")
    # committing (worker hasn't run) → not undoable yet
    assert client.post(f"/api/delete-batches/{bid}/undo").status_code == 409

    # drive the worker step, then undo is accepted
    import uuid as _uuid

    delete_batch_service.process_batch(db, _uuid.UUID(bid), FakePeopleWriteClient())
    assert client.post(f"/api/delete-batches/{bid}/undo").status_code == 202
