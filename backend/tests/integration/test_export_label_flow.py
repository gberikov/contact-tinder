"""Integration: the label half — ensure-group-once, assign, idempotent, 404, undo (FR-010..014/012a)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.audit import AuditEntry
from src.models.export import ContactLabel, ExportRun, LabelBatch
from src.models.working_copy import WorkingCopyContact
from src.services import export_service, label_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _grant_write(db, account):
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()


def _setup(db, *, count=2):
    account = seed_account(db)
    _grant_write(db, account)
    people = [dup_person(i, name=f"Proc {i}", phone=f"+{i}") for i in range(count)]
    wc = seed_working_copy(db, account, people)
    ts, _ = triage_service.open_session(db, wc.id)
    contacts = list(
        db.scalars(
            select(WorkingCopyContact)
            .where(WorkingCopyContact.working_copy_id == wc.id)
            .order_by(WorkingCopyContact.origin_resource_name)
        )
    )
    for c in contacts:
        triage_service.set_decision(db, ts.id, c.id, outcome="process")
    return account, wc, contacts


def _label_batch_id(db, run_id):
    return db.get(ExportRun, run_id).label_batch_id


def test_ensure_group_once_and_assign(db):
    account, wc, contacts = _setup(db, count=2)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)  # label-only export: scope-gated, enqueues labeling

    client = FakePeopleWriteClient()
    batch_id = _label_batch_id(db, run.id)
    label_batch_service.process_batch(db, batch_id, client)

    # group ensured once, cached in contact_label, audited.
    assert len(client.created_groups) == 1
    label = db.scalar(select(ContactLabel).where(ContactLabel.account_id == account.id))
    assert label is not None and label.name == "Process"
    created = db.scalars(
        select(AuditEntry).where(AuditEntry.action == "label.group.created")
    ).all()
    assert len(created) == 1

    out = export_service.get_run(db, run.id)
    assert out.status == "completed" and out.report.labeled == 2
    assert client.group_members[label.group_resource_name] == {
        c.origin_resource_name for c in contacts
    }


def test_idempotent_rerun_no_duplicate_group_or_membership(db):
    account, wc, contacts = _setup(db, count=2)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = _label_batch_id(db, run.id)

    label_batch_service.process_batch(db, batch_id, FakePeopleWriteClient())
    # Re-run with a fresh client: group is NOT recreated (cached) and labeled rows are not re-applied.
    client2 = FakePeopleWriteClient()
    label_batch_service.process_batch(db, batch_id, client2)
    assert client2.created_groups == []  # group reused from contact_label cache

    created = db.scalars(
        select(AuditEntry).where(AuditEntry.action == "label.group.created")
    ).all()
    assert len(created) == 1


def test_404_member_is_skipped_absent(db):
    account, wc, contacts = _setup(db, count=2)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = _label_batch_id(db, run.id)

    client = FakePeopleWriteClient(absent={contacts[0].origin_resource_name})
    label_batch_service.process_batch(db, batch_id, client)

    out = export_service.get_run(db, run.id)
    assert out.report.skippedAbsentLabel == 1 and out.report.labeled == 1
    assert out.status == "completed"


def test_undo_label_removes_membership_and_audits(db):
    account, wc, contacts = _setup(db, count=2)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = _label_batch_id(db, run.id)

    client = FakePeopleWriteClient()
    label_batch_service.process_batch(db, batch_id, client)
    label = db.scalar(select(ContactLabel).where(ContactLabel.account_id == account.id))

    export_service.undo_label(db, run.id)
    label_batch_service.process_undo(db, batch_id, client)

    assert db.get(LabelBatch, batch_id).status == "undone"
    assert client.group_members[label.group_resource_name] == set()
    unlabeled = db.scalars(
        select(AuditEntry).where(AuditEntry.action == "contact.unlabeled")
    ).all()
    assert len(unlabeled) == 2


def test_undo_label_endpoint_contract(client, db):
    """undoExportLabel (POST /export-runs/{id}/undo-label) conforms to openapi.yaml (202 + run)."""
    account, wc, contacts = _setup(db, count=1)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = _label_batch_id(db, run.id)
    label_batch_service.process_batch(db, batch_id, FakePeopleWriteClient())

    resp = client.post(f"/api/export-runs/{run.id}/undo-label")
    assert resp.status_code == 202
    body = resp.json()
    assert body["id"] == str(run.id) and body["labelBatchId"] == str(batch_id)
