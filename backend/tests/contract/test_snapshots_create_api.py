from tests.helpers import seed_account


def test_create_snapshot_returns_importing(client, db):
    account = seed_account(db)
    resp = client.post(f"/api/accounts/{account.id}/snapshots", json={"label": "first"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "importing"
    assert body["source"] == "personal_connections"
    assert body["label"] == "first"

    snapshot_id = body["id"]
    job = client.get(f"/api/snapshots/{snapshot_id}/import").json()
    assert job["status"] in ("queued", "running")
    assert job["fetchedCount"] == 0


def test_create_snapshot_unknown_account_404(client):
    import uuid

    resp = client.post(f"/api/accounts/{uuid.uuid4()}/snapshots", json={})
    assert resp.status_code == 404


def test_second_concurrent_import_conflicts(client, db):
    account = seed_account(db)
    assert client.post(f"/api/accounts/{account.id}/snapshots", json={}).status_code == 202
    # first import still queued -> second is rejected
    resp = client.post(f"/api/accounts/{account.id}/snapshots", json={})
    assert resp.status_code == 409
