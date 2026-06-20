"""Integration: worker-built Google credentials carry the fields needed to refresh mid-run.

Long batches outlive the ~1h access token; without client_id/client_secret google-auth raises
RefreshError and the batch stalls. These guard against that regression in both workers.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.workers import delete_worker, label_worker
from tests.helpers import seed_account


def _google_settings():
    return SimpleNamespace(
        people_write_client="google",
        google_oauth_client_id="cid-123",
        google_oauth_client_secret="csec-456",
    )


def _assert_refreshable(creds):
    # All four fields google-auth requires to refresh an expired access token.
    assert creds.refresh_token == "refresh-token"
    assert creds.token_uri.endswith("/token")
    assert creds.client_id == "cid-123"
    assert creds.client_secret == "csec-456"


def test_delete_worker_credentials_can_refresh(db, monkeypatch):
    account = seed_account(db)
    monkeypatch.setattr(delete_worker, "get_settings", _google_settings)
    client = delete_worker.build_write_client(db, SimpleNamespace(account_id=account.id))
    _assert_refreshable(client._credentials)


def test_label_worker_credentials_can_refresh(db, monkeypatch):
    account = seed_account(db)
    monkeypatch.setattr(label_worker, "get_settings", _google_settings)
    client = label_worker.build_write_client(db, SimpleNamespace(account_id=account.id))
    _assert_refreshable(client._credentials)
