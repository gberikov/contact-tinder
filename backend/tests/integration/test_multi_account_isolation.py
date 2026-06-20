"""FR-018 / SC-009: per-account isolation — no cross-account leakage."""
from src.services import snapshot_service
from tests.helpers import seed_account, seed_complete_snapshot


def test_snapshots_scoped_to_their_account(db):
    a = seed_account(db, gid="g-a", email="a@example.com")
    b = seed_account(db, gid="g-b", email="b@example.com")
    snap_a = seed_complete_snapshot(db, a, count=3)
    snap_b = seed_complete_snapshot(db, b, count=2)

    assert snap_a.account_id == a.id
    assert snap_b.account_id == b.id

    # Each snapshot's contacts belong only to its own account's capture.
    contacts_a, total_a = snapshot_service.list_contacts(db, snap_a.id, page_size=100)
    contacts_b, total_b = snapshot_service.list_contacts(db, snap_b.id, page_size=100)
    assert total_a == 3
    assert total_b == 2
    assert {c.snapshot_id for c in contacts_a} == {snap_a.id}
    assert {c.snapshot_id for c in contacts_b} == {snap_b.id}


def test_listing_labels_each_snapshot_with_its_account(db):
    a = seed_account(db, gid="g-a", email="a@example.com")
    b = seed_account(db, gid="g-b", email="b@example.com")
    seed_complete_snapshot(db, a, count=1)
    seed_complete_snapshot(db, b, count=1)

    listed = snapshot_service.list_snapshots(db)
    account_ids = {snap.account_id for snap, _ in listed}
    assert account_ids == {a.id, b.id}
