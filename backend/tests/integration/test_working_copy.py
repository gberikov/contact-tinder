import pytest

from src.core.errors import ConflictError
from src.services import snapshot_service, working_copy_service
from tests.helpers import seed_account, seed_complete_snapshot


def test_working_copy_is_independent_deep_copy(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=3)

    copy = working_copy_service.create_working_copy(db, snapshot.id, "wc1")
    assert working_copy_service.contact_count(db, copy.id) == 3

    # Mutating a working-copy contact must not touch the snapshot.
    wc_rows, _ = working_copy_service.list_contacts(db, copy.id, page_size=100)
    wc_rows[0].payload = {"names": [{"displayName": "EDITED"}]}
    db.commit()

    snap_rows, _ = snapshot_service.list_contacts(db, snapshot.id, page_size=100)
    assert all(r.display_name != "EDITED" for r in snap_rows)
    assert snapshot.contact_count == 3  # snapshot unchanged (FR-011)


def test_multiple_working_copies_from_same_snapshot(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=2)
    c1 = working_copy_service.create_working_copy(db, snapshot.id, "a")
    c2 = working_copy_service.create_working_copy(db, snapshot.id, "b")
    assert c1.id != c2.id
    assert snapshot_service.working_copy_count(db, snapshot.id) == 2


def test_cannot_copy_incomplete_snapshot(db):
    account = seed_account(db)
    snapshot = snapshot_service.create_snapshot(db, account.id)  # status importing
    with pytest.raises(ConflictError):
        working_copy_service.create_working_copy(db, snapshot.id, "x")
