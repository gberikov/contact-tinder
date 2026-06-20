from tests.helpers import seed_account, seed_complete_snapshot


def test_list_and_detail(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=3)

    listed = client.get("/api/snapshots").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "complete"
    assert listed[0]["contactCount"] == 3
    assert listed[0]["workingCopyCount"] == 0
    assert listed[0]["accountEmail"] == account.email

    detail = client.get(f"/api/snapshots/{snapshot.id}").json()
    assert detail["id"] == str(snapshot.id)


def test_browse_contacts_paginated(client, db):
    account = seed_account(db)
    snapshot = seed_complete_snapshot(db, account, count=5)
    page = client.get(
        f"/api/snapshots/{snapshot.id}/contacts", params={"page": 1, "pageSize": 2}
    ).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["items"][0]["resourceName"].startswith("people/c")
    assert page["items"][0]["payload"]["names"][0]["displayName"].startswith("Contact")
