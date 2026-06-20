"""Contract: dedup run endpoints (US1 / FR-001, FR-007)."""
from __future__ import annotations

from tests.helpers import dup_person, seed_account, seed_working_copy


def _working_copy(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="John Smith", phone="+1-202-555-0100", email="john@x.com"),
        dup_person(1, name="Jon Smith", phone="(202) 555 0100", email="jon@y.com"),
        dup_person(2, name="Alice Brown", phone="+1-303-555-0199", email="alice@z.com"),
    ]
    return seed_working_copy(db, account, people)


def test_start_run_enqueues_then_completes_sync(client, db):
    wc = _working_copy(db)
    # Synchronous path runs the fake engine inline so the contract can assert a completed run.
    resp = client.post(f"/api/working-copies/{wc.id}/dedup-runs?background=false")
    assert resp.status_code == 202
    body = resp.json()
    assert body["workingCopyId"] == str(wc.id)
    assert body["status"] == "completed"
    assert body["clusterCount"] == 1  # John/Jon Smith share a phone


def test_second_active_run_conflicts(client, db):
    wc = _working_copy(db)
    first = client.post(f"/api/working-copies/{wc.id}/dedup-runs")  # background → stays queued
    assert first.status_code == 202
    second = client.post(f"/api/working-copies/{wc.id}/dedup-runs")
    assert second.status_code == 409


def test_get_and_list_runs(client, db):
    wc = _working_copy(db)
    created = client.post(f"/api/working-copies/{wc.id}/dedup-runs?background=false").json()
    got = client.get(f"/api/dedup-runs/{created['id']}")
    assert got.status_code == 200 and got.json()["id"] == created["id"]
    listed = client.get(f"/api/working-copies/{wc.id}/dedup-runs")
    assert listed.status_code == 200 and len(listed.json()) == 1


def test_run_missing_working_copy_404(client):
    import uuid

    resp = client.post(f"/api/working-copies/{uuid.uuid4()}/dedup-runs")
    assert resp.status_code == 404
