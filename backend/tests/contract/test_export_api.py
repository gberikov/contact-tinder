"""Contract: export endpoints conform to contracts/openapi.yaml (feature 004)."""
from __future__ import annotations

import uuid as _uuid

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _grant_write(db, account):
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()


def _triaged_wc(client, db, account, *, label):
    """A working copy with one `delete` and one `process` contact."""
    wc = seed_working_copy(
        db,
        account,
        [dup_person(0, name="Del One", phone="+1"), dup_person(1, name="Proc Two", phone="+2")],
        label=label,
    )
    contacts = list(
        db.scalars(
            select(WorkingCopyContact)
            .where(WorkingCopyContact.working_copy_id == wc.id)
            .order_by(WorkingCopyContact.origin_resource_name)
        )
    )
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    client.put(f"/api/triage-sessions/{sid}/decisions/{contacts[0].id}", json={"outcome": "delete"})
    client.put(f"/api/triage-sessions/{sid}/decisions/{contacts[1].id}", json={"outcome": "process"})
    return wc


def test_preview_shape(client, db):
    account = seed_account(db)
    wc = _triaged_wc(client, db, account, label="prev")
    resp = client.get(f"/api/working-copies/{wc.id}/export/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleteCount"] == 1 and body["labelCount"] == 1
    assert body["undecidedCount"] == 0 and body["nothingToExport"] is False
    assert body["labelName"] == "Process"
    assert len(body["deleteSet"]) == 1 and "workingCopyContactId" in body["deleteSet"][0]


def test_start_creates_run_with_both_batches(client, db):
    account = seed_account(db)
    wc = _triaged_wc(client, db, account, label="start")
    resp = client.post(f"/api/working-copies/{wc.id}/export")
    assert resp.status_code == 201
    run = resp.json()
    assert run["status"] == "previewing"
    assert run["deleteBatchId"] and run["labelBatchId"]
    assert run["report"]["deleted"] == 0  # nothing written yet

    got = client.get(f"/api/export-runs/{run['id']}")
    assert got.status_code == 200 and got.json()["id"] == run["id"]


def test_confirm_delete_requires_write_scope(client, db):
    account = seed_account(db)  # no write scope
    wc = _triaged_wc(client, db, account, label="noscope")
    run = client.post(f"/api/working-copies/{wc.id}/export").json()
    resp = client.post(f"/api/export-runs/{run['id']}/confirm-delete")
    assert resp.status_code == 403
    assert resp.json()["code"] == "write_scope_required"


def test_confirm_delete_then_undo(client, db):
    account = seed_account(db)
    _grant_write(db, account)
    wc = _triaged_wc(client, db, account, label="confirm")
    run = client.post(f"/api/working-copies/{wc.id}/export").json()

    confirm = client.post(f"/api/export-runs/{run['id']}/confirm-delete")
    assert confirm.status_code == 202 and confirm.json()["status"] == "running"

    # Drive the delete worker step so the batch is committed (undoable).
    delete_batch_service.process_batch(
        db, _uuid.UUID(run["deleteBatchId"]), FakePeopleWriteClient()
    )
    undo = client.post(f"/api/export-runs/{run['id']}/undo-delete")
    assert undo.status_code == 202


def test_start_with_nothing_to_export_409(client, db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [dup_person(0, name="Keep", phone="+1")])
    client.post(f"/api/working-copies/{wc.id}/triage-sessions")
    resp = client.post(f"/api/working-copies/{wc.id}/export")
    assert resp.status_code == 409


def test_unknown_run_404(client, db):
    assert client.get(f"/api/export-runs/{_uuid.uuid4()}").status_code == 404
