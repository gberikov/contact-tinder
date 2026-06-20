from src.services import snapshot_service, working_copy_service
from tests.helpers import seed_account, seed_complete_snapshot


def test_list_newest_first_with_working_copy_count(db):
    account = seed_account(db)
    s1 = seed_complete_snapshot(db, account, count=2)
    s2 = seed_complete_snapshot(db, account, count=3)
    working_copy_service.create_working_copy(db, s1.id, "wc")

    listed = snapshot_service.list_snapshots(db)
    assert [s.id for s, _ in listed] == [s2.id, s1.id]  # newest first
    counts = {s.id: n for s, n in listed}
    assert counts[s1.id] == 1
    assert counts[s2.id] == 0


def test_contacts_readonly_zero_drift(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=4)

    rows1, total1 = snapshot_service.list_contacts(db, snapshot.id, page_size=100)
    rows2, total2 = snapshot_service.list_contacts(db, snapshot.id, page_size=100)
    assert total1 == total2 == 4
    assert [c.resource_name for c in rows1] == [c.resource_name for c in rows2]


def test_contacts_search_filter(db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=5)
    rows, total = snapshot_service.list_contacts(db, snapshot.id, q="contact 1")
    assert total == 1
    assert rows[0].display_name == "Contact 1"
