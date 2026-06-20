"""Integration: worker durability — backoff retry on transient errors + chunked commits."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import (
    FakePeopleWriteClient,
    RateLimitedError,
    TransientError,
)
from src.models.export import ExportRun
from src.models.triage import DeletionRecord
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, export_service, label_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db, *, count, outcome):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    wc = seed_working_copy(db, account, [dup_person(i, name=f"C {i}", phone=f"+{i}") for i in range(count)])
    ts, _ = triage_service.open_session(db, wc.id)
    contacts = list(
        db.scalars(
            select(WorkingCopyContact)
            .where(WorkingCopyContact.working_copy_id == wc.id)
            .order_by(WorkingCopyContact.origin_resource_name)
        )
    )
    for c in contacts:
        triage_service.set_decision(db, ts.id, c.id, outcome=outcome)
    return wc, contacts


def test_delete_retries_transient_then_succeeds(db):
    wc, contacts = _setup(db, count=1, outcome="delete")
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id

    sleeps: list[float] = []

    class _Flaky(FakePeopleWriteClient):
        def __init__(self):
            super().__init__()
            self._left = 2  # fail twice, then succeed

        def delete_contact(self, resource_name):
            if self._left > 0:
                self._left -= 1
                raise TransientError()
            super().delete_contact(resource_name)

    delete_batch_service.process_batch(db, batch_id, _Flaky(), sleep=sleeps.append)
    out = export_service.get_run(db, run.id)
    assert out.status == "completed" and out.report.deleted == 1  # retried, not failed
    assert len(sleeps) == 2  # backed off twice before succeeding


def test_label_retries_transient_then_succeeds(db):
    wc, contacts = _setup(db, count=1, outcome="process")
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).label_batch_id

    class _Flaky(FakePeopleWriteClient):
        def __init__(self):
            super().__init__()
            self._left = 1

        def add_label_members(self, group, resource_names):
            if self._left > 0:
                self._left -= 1
                raise RateLimitedError()
            super().add_label_members(group, resource_names)

    label_batch_service.process_batch(db, batch_id, _Flaky(), sleep=lambda _: None)
    out = export_service.get_run(db, run.id)
    assert out.status == "completed" and out.report.labeled == 1


def test_write_pacing_sleeps_before_each_write(db, monkeypatch):
    """With pacing configured, the worker waits between writes to stay under Google's quota."""
    wc, contacts = _setup(db, count=3, outcome="delete")
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id

    monkeypatch.setattr(
        delete_batch_service,
        "get_settings",
        lambda: SimpleNamespace(
            export_commit_chunk_size=50,
            export_max_attempts=5,
            export_write_min_interval_seconds=0.5,
        ),
    )
    waits: list[float] = []
    delete_batch_service.process_batch(db, batch_id, FakePeopleWriteClient(), sleep=waits.append)

    out = export_service.get_run(db, run.id)
    assert out.report.deleted == 3
    assert waits == [0.5, 0.5, 0.5]  # paced once per record (no retries needed)


def test_chunked_commit_persists_progress_before_a_crash(db, monkeypatch):
    """A crash mid-batch keeps the already-committed chunk durable (records stay deleted)."""
    wc, contacts = _setup(db, count=5, outcome="delete")
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).delete_batch_id

    # Commit every 2 records; crash on the 3rd delete.
    monkeypatch.setattr(
        delete_batch_service,
        "get_settings",
        lambda: SimpleNamespace(
            export_commit_chunk_size=2,
            export_max_attempts=5,
            export_write_min_interval_seconds=0,
        ),
    )

    class _Crash(FakePeopleWriteClient):
        def __init__(self):
            super().__init__()
            self._n = 0

        def delete_contact(self, resource_name):
            self._n += 1
            if self._n == 3:
                raise RuntimeError("worker died")  # not a retryable error → propagates
            super().delete_contact(resource_name)

    with pytest.raises(RuntimeError):
        delete_batch_service.process_batch(db, batch_id, _Crash(), sleep=lambda _: None)

    # The first committed chunk (2 records) is durable; the rest are still pending → safe re-run.
    statuses = sorted(
        s for (s,) in db.execute(
            select(DeletionRecord.status).where(DeletionRecord.delete_batch_id == batch_id)
        )
    )
    assert statuses.count("deleted") == 2
    assert statuses.count("pending") == 3
