"""Unit: the Google contacts WRITE scope is opt-in only — never in the default scopes (Principle I)."""
from __future__ import annotations

from src.core.config import get_settings


def test_write_scope_not_in_default_scopes():
    s = get_settings()
    # Read-only by default; the write scope is requested only via incremental consent (D9).
    assert s.google_contacts_write_scope not in s.google_scopes
    assert all("contacts.readonly" in sc or "openid" in sc or "userinfo" in sc for sc in s.google_scopes)


def test_default_write_client_is_fake():
    # CI / default never reaches the live Google write path (Principle IV).
    assert get_settings().people_write_client == "fake"
