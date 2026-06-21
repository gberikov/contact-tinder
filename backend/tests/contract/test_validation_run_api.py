"""T024 (US1) — validation-run endpoints contract."""
from __future__ import annotations

from tests.helpers import seed_account, seed_working_copy


def _wc(db):
    account = seed_account(db)
    person = {"resourceName": "people/c0", "etag": "e0",
              "names": [{"displayName": "C0", "metadata": {"primary": True}}],
              "phoneNumbers": [{"value": "+7 (701) 722-15-02"}]}
    return seed_working_copy(db, account, [person])


def test_start_list_get_run(db, client):
    # The POST only creates a queued run (the worker processes it separately), so no checks run here.
    wc = _wc(db)

    r = client.post(f"/api/working-copies/{wc.id}/validation-runs", json={"defaultRegion": "KZ"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] in ("queued", "running", "completed")
    assert run["workingCopyId"] == str(wc.id)
    assert run["pendingCount"] == 0 and run["queuedCount"] == 0
    run_id = run["id"]

    # second active run is rejected
    r2 = client.post(f"/api/working-copies/{wc.id}/validation-runs", json={})
    assert r2.status_code == 409

    lst = client.get(f"/api/working-copies/{wc.id}/validation-runs")
    assert lst.status_code == 200
    assert lst.json()[0]["id"] == run_id  # newest-first

    got = client.get(f"/api/validation-runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["id"] == run_id


def test_get_unknown_run_404(client):
    import uuid
    assert client.get(f"/api/validation-runs/{uuid.uuid4()}").status_code == 404
