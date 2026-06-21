from tests.helpers import seed_account, seed_complete_snapshot


def test_delete_without_confirm_is_rejected(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    resp = client.delete(f"/api/snapshots/{snapshot.id}", params={"confirm": "false"})
    assert resp.status_code == 400


def test_delete_cascades_through_working_copies(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    client.post(f"/api/snapshots/{snapshot.id}/working-copies", json={})
    resp = client.delete(f"/api/snapshots/{snapshot.id}", params={"confirm": "true"})
    assert resp.status_code == 204
    assert client.get(f"/api/snapshots/{snapshot.id}").status_code == 404
    assert client.get("/api/working-copies").json() == []


def test_delete_succeeds_with_confirm(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=1)
    resp = client.delete(f"/api/snapshots/{snapshot.id}", params={"confirm": "true"})
    assert resp.status_code == 204
    assert client.get(f"/api/snapshots/{snapshot.id}").status_code == 404
