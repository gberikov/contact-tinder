"""Contract: merge-preview / merge / dismiss / undo (US3)."""
from __future__ import annotations

from tests.helpers import dup_person, seed_account, seed_working_copy


def _cluster(client, db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
    ]
    wc = seed_working_copy(db, account, people)
    run = client.post(f"/api/working-copies/{wc.id}/dedup-runs?background=false").json()
    return client.get(f"/api/dedup-runs/{run['id']}/clusters").json()[0]


def test_merge_preview_and_merge(client, db):
    cluster = _cluster(client, db)
    preview = client.get(f"/api/clusters/{cluster['id']}/merge-preview")
    assert preview.status_code == 200
    assert preview.json()["survivorContactId"]

    merged = client.post(f"/api/clusters/{cluster['id']}/merge", json={})
    assert merged.status_code == 200
    result = merged.json()
    assert len(result["retiredContactIds"]) == 1

    # Undo restores the cluster to pending.
    undone = client.post(f"/api/merge-records/{result['mergeRecordId']}/undo")
    assert undone.status_code == 200
    assert undone.json()["status"] == "pending"


def test_dismiss(client, db):
    cluster = _cluster(client, db)
    resp = client.post(f"/api/clusters/{cluster['id']}/dismiss")
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_merge_already_resolved_conflict(client, db):
    cluster = _cluster(client, db)
    client.post(f"/api/clusters/{cluster['id']}/merge", json={})
    again = client.post(f"/api/clusters/{cluster['id']}/merge", json={})
    assert again.status_code == 409
