"""Contract: incremental-consent for the contacts write scope (feature 004 re-consent)."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service
from tests.helpers import dup_person, seed_working_copy

WRITE_SCOPE = "https://www.googleapis.com/auth/contacts"


def _connect(client):
    client.get("/api/accounts/callback", params={"code": "c", "state": "s"}, follow_redirects=False)


def test_grant_write_returns_authorization_url(client):
    resp = client.post("/api/accounts/grant-write", json={"returnTo": "/working-copies/x/export"})
    assert resp.status_code == 200
    assert resp.json()["authorizationUrl"].startswith("https://accounts.google.com/")


def test_reconsent_adds_write_scope_to_account(client):
    _connect(client)  # initial read-only connection
    before = client.get("/api/accounts").json()[0]["grantedScopes"]
    assert WRITE_SCOPE not in before

    # Operator clicks "grant write" → consents → callback stores the broadened scopes.
    client.post("/api/accounts/grant-write", json={})
    client.get("/api/accounts/callback", params={"code": "c2", "state": "s2"}, follow_redirects=False)

    after = client.get("/api/accounts").json()[0]["grantedScopes"]
    assert WRITE_SCOPE in after


def test_callback_redirects_back_to_return_to(client):
    _connect(client)
    url = client.post(
        "/api/accounts/grant-write", json={"returnTo": "/working-copies/abc/export"}
    ).json()["authorizationUrl"]
    state = parse_qs(urlparse(url).query)["state"][0]

    resp = client.get(
        "/api/accounts/callback", params={"code": "c2", "state": state}, follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/working-copies/abc/export")


def test_export_confirm_succeeds_after_reconsent(client, db):
    """End-to-end: 403 before consent → re-consent → confirm-delete passes the scope gate."""
    _connect(client)
    wc = seed_working_copy(db, _account(db), [dup_person(0, name="Del", phone="+1")], label="rc")
    cid = db.scalar(
        select(WorkingCopyContact.id).where(WorkingCopyContact.working_copy_id == wc.id)
    )
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    client.put(f"/api/triage-sessions/{sid}/decisions/{cid}", json={"outcome": "delete"})
    run = client.post(f"/api/working-copies/{wc.id}/export").json()

    # Without the write scope the destructive confirm is refused.
    assert client.post(f"/api/export-runs/{run['id']}/confirm-delete").status_code == 403

    # Re-consent, then the same confirm is accepted.
    client.post("/api/accounts/grant-write", json={})
    client.get("/api/accounts/callback", params={"code": "c2", "state": "s2"}, follow_redirects=False)
    assert client.post(f"/api/export-runs/{run['id']}/confirm-delete").status_code == 202

    # And the worker path can actually delete (fake seam) — sanity.
    delete_batch_service.process_batch(
        db, __import__("uuid").UUID(run["deleteBatchId"]), FakePeopleWriteClient()
    )


def _account(db):
    from src.models.account import Account

    return db.scalar(select(Account))
