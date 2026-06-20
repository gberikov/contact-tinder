import uuid

import pytest
from sqlalchemy import func, select

from src.core.errors import ConflictError
from src.models.audit import AuditEntry
from src.services import snapshot_service, working_copy_service
from tests.helpers import seed_account, seed_complete_snapshot


def test_delete_requires_confirmation(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    with pytest.raises(ConflictError) as exc:
        snapshot_service.delete_snapshot(db, snapshot.id, confirm=False)
    assert exc.value.status_code == 400


def test_delete_blocked_while_working_copies_exist(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    working_copy_service.create_working_copy(db, snapshot.id, "wc")
    with pytest.raises(ConflictError):
        snapshot_service.delete_snapshot(db, snapshot.id, confirm=True)
    # snapshot still present
    assert snapshot_service.get_snapshot(db, snapshot.id) is not None


def test_delete_succeeds_and_audits(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    sid = snapshot.id
    snapshot_service.delete_snapshot(db, sid, confirm=True)

    from src.core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        snapshot_service.get_snapshot(db, sid)

    deleted_events = db.scalar(
        select(func.count()).select_from(AuditEntry).where(
            AuditEntry.action == "snapshot.deleted", AuditEntry.target_id == sid
        )
    )
    assert deleted_events == 1
