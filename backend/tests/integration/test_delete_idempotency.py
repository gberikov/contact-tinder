"""Integration: delete execution is idempotent and retry-safe (US3 / FR-022, D8/D10)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient, TransientError
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db, n=2):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    wc = seed_working_copy(
        db, account, [dup_person(i, name=f"N{i} L{i}", phone=f"+{i}") for i in range(n)]
    )
    ts, _ = triage_service.open_session(db, wc.id)
    contacts = list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )
    for c in contacts:
        triage_service.set_decision(db, ts.id, c.id, outcome="delete")
    batch = delete_batch_service.create_batch(db, wc.id)
    delete_batch_service.confirm(db, batch.id)
    return batch, contacts


def test_reprocess_does_not_redelete(db):
    batch, contacts = _setup(db, 2)
    delete_batch_service.process_batch(db, batch.id, FakePeopleWriteClient())

    # A second pass (e.g. worker restart) must not call Google again.
    second = FakePeopleWriteClient()
    delete_batch_service.process_batch(db, batch.id, second)
    assert second.deleted == []  # idempotent


class _FlakyClient(FakePeopleWriteClient):
    """Fails one resource on EVERY attempt (outlasting the retry ceiling → failed)."""

    def __init__(self, fail_resource):
        super().__init__()
        self._fail_resource = fail_resource

    def delete_contact(self, resource_name):
        if resource_name == self._fail_resource:
            raise TransientError()
        super().delete_contact(resource_name)


def test_partial_failure_then_retry_completes(db):
    batch, contacts = _setup(db, 2)
    flaky = _FlakyClient(contacts[0].origin_resource_name)
    # sleep injected so the backoff retries don't actually wait.
    delete_batch_service.process_batch(db, batch.id, flaky, sleep=lambda _: None)
    db.refresh(batch)
    assert batch.status == "failed" and batch.failed_count == 1

    # Retry with a healthy client finishes only the outstanding record.
    delete_batch_service.process_batch(db, batch.id, FakePeopleWriteClient(), sleep=lambda _: None)
    db.refresh(batch)
    assert batch.status == "committed" and batch.failed_count == 0 and batch.deleted_count == 2
