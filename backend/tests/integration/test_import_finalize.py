from src.models.snapshot import SnapshotContact
from sqlalchemy import select
from tests.helpers import seed_account, seed_complete_snapshot


def test_import_finalizes_with_exact_count(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=5)

    assert snapshot.status == "complete"
    assert snapshot.contact_count == 5
    assert snapshot.finalized_at is not None
    assert snapshot.next_sync_token == "SYNC123"
    assert snapshot.import_job.status == "completed"


def test_payload_retains_full_fidelity(db):
    """FR-004: addresses, organizations, notes, memberships, photo refs survive in payload."""
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1, full=True)

    contact = db.scalars(
        select(SnapshotContact).where(SnapshotContact.snapshot_id == snapshot.id)
    ).first()
    payload = contact.payload
    assert payload["addresses"][0]["formattedValue"]
    assert payload["organizations"][0]["name"]
    assert payload["biographies"][0]["value"]
    assert payload["memberships"][0]["contactGroupMembership"]["contactGroupId"] == "friends"
    assert payload["photos"][0]["url"]
