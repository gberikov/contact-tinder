"""Integration: the delete half of the export — confirm, commit, idempotent re-run, 404, undo, FR-024."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient, RateLimitedError
from src.models.export import ExportRun
from src.models.triage import DeleteBatch
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, export_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db, *, with_scope=True, count=2):
    account = seed_account(db)
    if with_scope:
        account.granted_scopes = (
            account.granted_scopes + " " + get_settings().google_contacts_write_scope
        ).strip()
        db.commit()
    people = [dup_person(i, name=f"Del {i}", phone=f"+{i}") for i in range(count)]
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
        triage_service.set_decision(db, ts.id, c.id, outcome="delete")
    return wc, contacts


def test_full_delete_flow_and_report(db):
    wc, contacts = _setup(db)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)

    batch_id = db.get(ExportRun, run.id).delete_batch_id
    delete_batch_service.process_batch(db, batch_id, FakePeopleWriteClient())

    out = export_service.get_run(db, run.id)
    assert out.status == "completed"
    assert out.report.deleted == 2 and out.report.failed == 0
    for c in contacts:
        db.refresh(c)
        assert c.status == "retired"


def test_404_is_skipped_absent_success(db):
    wc, contacts = _setup(db, count=1)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id

    client = FakePeopleWriteClient(absent={contacts[0].origin_resource_name})
    delete_batch_service.process_batch(db, batch_id, client)

    out = export_service.get_run(db, run.id)
    assert out.report.skippedAbsentDelete == 1 and out.report.failed == 0
    assert out.status == "completed"


def test_rate_limit_surfaced_then_retry_idempotent(db):
    """FR-024: a transient throttle is surfaced (run not silently dropped) and a retry completes it."""
    wc, contacts = _setup(db, count=2)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id

    # One record hits a 429 and is left failed; the run reports the failure (FR-024).
    class _Throttle(FakePeopleWriteClient):
        def __init__(self):
            super().__init__()
            self._calls = 0

        def delete_contact(self, resource_name):
            self._calls += 1
            if self._calls == 1:
                raise RateLimitedError()
            super().delete_contact(resource_name)

    delete_batch_service.process_batch(db, batch_id, _Throttle())
    out = export_service.get_run(db, run.id)
    assert out.status == "failed" and out.report.failed == 1

    # Retry with a healthy client — only the failed record is retried; no double-delete.
    client = FakePeopleWriteClient()
    delete_batch_service.process_batch(db, batch_id, client)
    out = export_service.get_run(db, run.id)
    assert out.status == "completed" and out.report.deleted == 2
    assert len(client.deleted) == 1  # only the previously-failed contact was re-attempted


def test_undo_delete_restores(db):
    wc, contacts = _setup(db, count=1)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id
    delete_batch_service.process_batch(db, batch_id, FakePeopleWriteClient())

    export_service.undo_delete(db, run.id)
    delete_batch_service.process_undo(db, batch_id, FakePeopleWriteClient())

    db.refresh(contacts[0])
    assert contacts[0].status == "active"
    assert db.get(DeleteBatch, batch_id).status == "undone"
