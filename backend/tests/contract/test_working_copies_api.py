from tests.helpers import seed_account, seed_complete_snapshot


def test_create_and_list_working_copy(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=3)

    created = client.post(
        f"/api/snapshots/{snapshot.id}/working-copies", json={"label": "wc1"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["label"] == "wc1"
    assert body["status"] == "ready"
    assert body["contactCount"] == 3

    listed = client.get("/api/working-copies").json()
    assert len(listed) == 1

    contacts = client.get(f"/api/working-copies/{body['id']}/contacts").json()
    assert contacts["total"] == 3


def test_snapshot_reports_working_copy_count(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={})
    detail = client.get(f"/api/snapshots/{snapshot.id}").json()
    assert detail["workingCopyCount"] == 1
