"""Integration: confirm is scope-gated (D9) and committed deletes are undoable (US3 / FR-023)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from src.core.config import get_settings
from src.core.errors import AppError
from src.integrations.people_client import FakePeopleWriteClient
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db, *, with_scope: bool):
    account = seed_account(db)
    if with_scope:
        account.granted_scopes = (
            account.granted_scopes + " " + get_settings().google_contacts_write_scope
        ).strip()
        db.commit()
    wc = seed_working_copy(db, account, [dup_person(0, name="Del One", phone="+1")])
    ts, _ = triage_service.open_session(db, wc.id)
    c = db.scalar(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    triage_service.set_decision(db, ts.id, c.id, outcome="delete")
    return wc, c


def test_confirm_without_write_scope_is_rejected(db):
    wc, _ = _setup(db, with_scope=False)
    batch = delete_batch_service.create_batch(db, wc.id)
    with pytest.raises(AppError) as exc:
        delete_batch_service.confirm(db, batch.id)
    assert exc.value.status_code == 403


def test_undo_recreates_and_reactivates(db):
    wc, c = _setup(db, with_scope=True)
    batch = delete_batch_service.create_batch(db, wc.id)
    delete_batch_service.confirm(db, batch.id)
    delete_batch_service.process_batch(db, batch.id, FakePeopleWriteClient())
    db.refresh(c)
    assert c.status == "retired"

    delete_batch_service.request_undo(db, batch.id)
    client = FakePeopleWriteClient()
    delete_batch_service.process_undo(db, batch.id, client)

    db.refresh(batch)
    assert batch.status == "undone"
    assert batch.records[0].status == "restored"
    assert batch.records[0].restored_resource_name in client.created
    db.refresh(c)
    assert c.status == "active"  # reactivated in the working copy
