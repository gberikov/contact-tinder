"""T033 (US2) — queue one item per uncertain/broken finding; resolve & skip.

website_unsafe is produced WITHOUT any outbound request. Both invalid_email (syntax) and
dead_email_domain (no MX) are exercised as distinct cases. DNS is monkeypatched.
"""
from __future__ import annotations

import pytest

from src.models.validation import ValidationItem
from src.services import email_validator_service as ev
from src.services import validation_service
from src.services.website_checker import WebsiteResult
from tests.helpers import seed_account, seed_working_copy


@pytest.fixture(autouse=True)
def _mx(monkeypatch):
    # gmial.com has no MX; everything else does.
    monkeypatch.setattr(ev, "domain_has_mx", lambda domain: domain != "gmial.com")


def _person(i, **fields):
    p = {"resourceName": f"people/c{i}", "etag": f"e{i}",
         "names": [{"displayName": f"C{i}", "metadata": {"primary": True}}]}
    p.update(fields)
    return p


def _fake_web(url, **_):
    # Mirrors website_checker's verdicts; the "no outbound request for unsafe" guarantee is proven
    # at the unit level (test_website_checker), so here we only model the classification.
    if "127.0.0.1" in url or "169.254" in url:
        return WebsiteResult(status="unsafe")
    if "dead." in url:
        return WebsiteResult(status="unreachable")
    return WebsiteResult(status="reachable", final_url=url)


def _run(db, wc):
    run = validation_service.start_run(db, wc.id, default_region="KZ")
    validation_service.run_validation_job(db, run.id, website_check=_fake_web)
    return run


def test_each_issue_type_is_queued(db):
    account = seed_account(db)
    people = [
        _person(0, phoneNumbers=[{"value": "+7 70"}]),                     # invalid_phone
        _person(1, phoneNumbers=[{"value": "+7 727 250 1234"}]),          # unclear_type (fixed line)
        _person(2, emailAddresses=[{"value": "bob@@example"}]),           # invalid_email (syntax)
        _person(3, emailAddresses=[{"value": "mail@gmial.com"}]),         # dead_email_domain
        _person(4, urls=[{"value": "http://dead.example/"}]),             # website_unreachable
        _person(5, urls=[{"value": "http://127.0.0.1/"}]),                # website_unsafe (no fetch)
    ]
    wc = seed_working_copy(db, account, people)
    run = _run(db, wc)

    items = db.query(ValidationItem).filter_by(validation_run_id=run.id).all()
    by_issue = {i.issue_type for i in items}
    assert by_issue == {
        "invalid_phone", "unclear_type", "invalid_email",
        "dead_email_domain", "website_unreachable", "website_unsafe",
    }
    # unclear_type carries the E.164 suggestion.
    unclear = next(i for i in items if i.issue_type == "unclear_type")
    assert unclear.suggested_value == "+77272501234"


def test_resolve_set_type_creates_staged_edit(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [_person(1, phoneNumbers=[{"value": "+7 727 250 1234"}])])
    run = _run(db, wc)
    item = db.query(ValidationItem).filter_by(issue_type="unclear_type").one()

    resolved = validation_service.resolve_item(db, item.id, action="set_type", type="work")
    assert resolved.status == "resolved"
    assert resolved.staged_edit_id is not None
    contact = next(c for c in wc.contacts if c.id == item.working_copy_contact_id)
    db.refresh(contact)
    assert contact.payload["phoneNumbers"][0]["type"] == "work"


def test_skip_leaves_value_unchanged(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [_person(4, urls=[{"value": "http://dead.example/"}])])
    run = _run(db, wc)
    item = db.query(ValidationItem).filter_by(issue_type="website_unreachable").one()

    skipped = validation_service.skip_item(db, item.id)
    assert skipped.status == "skipped"
    assert skipped.staged_edit_id is None
    contact = next(c for c in wc.contacts if c.id == item.working_copy_contact_id)
    db.refresh(contact)
    assert contact.payload["urls"][0]["value"] == "http://dead.example/"
