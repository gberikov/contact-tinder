"""T009 — email syntax + MX (feature 006, FR-011/012). DNS is monkeypatched (no network)."""
from __future__ import annotations

import pytest

from src.services import email_validator_service as ev


@pytest.fixture(autouse=True)
def _mx_present(monkeypatch):
    # Default: every domain has MX, so only syntax decides — individual tests override.
    monkeypatch.setattr(ev, "domain_status", lambda domain: "ok")


def test_valid_email_with_mx_is_ok():
    r = ev.analyze("Bob@Example.com")
    assert r.issue is None
    assert r.valid_syntax is True
    assert r.has_mx is True
    assert r.normalized == "Bob@example.com"  # domain lower-cased by the validator


def test_syntactically_invalid_is_invalid_email():
    r = ev.analyze("bob@@example")
    assert r.issue == "invalid_email"
    assert r.valid_syntax is False


def test_not_an_email_is_invalid_email():
    r = ev.analyze("not-an-email")
    assert r.issue == "invalid_email"


def test_valid_syntax_but_no_mx_is_dead_domain(monkeypatch):
    monkeypatch.setattr(ev, "domain_status", lambda domain: "no_mx")
    r = ev.analyze("mail@gmial.com")
    assert r.issue == "dead_email_domain"
    assert r.valid_syntax is True
    assert r.has_mx is False
    assert "MX" in (r.detail or "")


def test_nonexistent_domain_says_does_not_exist(monkeypatch):
    monkeypatch.setattr(ev, "domain_status", lambda domain: "no_domain")
    r = ev.analyze("mail@no-such-domain-xyz.tld")
    assert r.issue == "dead_email_domain"
    assert "does not exist" in (r.detail or "")
