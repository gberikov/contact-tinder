"""Contract: cluster review endpoints (US2 / FR-010, FR-011)."""
from __future__ import annotations

from tests.helpers import dup_person, seed_account, seed_working_copy


def _completed_run(client, db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="+1-202-555-0100", email="jon@y.com"),
        dup_person(2, name="Sam Lee", phone="+1-303-555-0001", email="sam@z.com"),
        dup_person(3, name="Samuel Lee", phone="+1-303-555-0001", email="samuel@z.com"),
    ]
    wc = seed_working_copy(db, account, people)
    return client.post(f"/api/working-copies/{wc.id}/dedup-runs?background=false").json()


def test_list_clusters_ordered_and_filtered(client, db):
    run = _completed_run(client, db)
    resp = client.get(f"/api/dedup-runs/{run['id']}/clusters")
    assert resp.status_code == 200
    clusters = resp.json()
    assert len(clusters) == 2
    confidences = [c["confidence"] for c in clusters]
    assert confidences == sorted(confidences, reverse=True)  # FR-011
    assert all(c["size"] == 2 for c in clusters)
    assert all(len(c["members"]) == 2 for c in clusters)

    high = client.get(
        f"/api/dedup-runs/{run['id']}/clusters", params={"minConfidence": 0.99}
    ).json()
    assert len(high) <= len(clusters)


def test_get_cluster(client, db):
    run = _completed_run(client, db)
    cluster_id = client.get(f"/api/dedup-runs/{run['id']}/clusters").json()[0]["id"]
    got = client.get(f"/api/clusters/{cluster_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["members"][0]["contact"]["displayName"]


def test_list_clusters_run_not_completed_conflict(client, db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [dup_person(0, name="A B", phone="+1-202-555-1")])
    run = client.post(f"/api/working-copies/{wc.id}/dedup-runs").json()  # queued
    resp = client.get(f"/api/dedup-runs/{run['id']}/clusters")
    assert resp.status_code == 409
