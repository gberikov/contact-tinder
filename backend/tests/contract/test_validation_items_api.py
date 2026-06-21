"""T034 (US2) — validation-item endpoints contract (list / resolve / skip / undo)."""
from __future__ import annotations

import uuid

import pytest

from src.services import email_validator_service as ev
from src.services import validation_service
from src.services.website_checker import WebsiteResult
from tests.helpers import seed_account, seed_working_copy


@pytest.fixture(autouse=True)
def _mx(monkeypatch):
    monkeypatch.setattr(ev, "domain_status", lambda domain: "no_mx" if domain == "gmial.com" else "ok")


def _seed_run(db):
    account = seed_account(db)
    people = [
        {"resourceName": "people/c1", "etag": "e1",
         "names": [{"displayName": "C1", "metadata": {"primary": True}}],
         "phoneNumbers": [{"value": "+7 727 250 1234"}]},        # unclear_type
        {"resourceName": "people/c2", "etag": "e2",
         "names": [{"displayName": "C2", "metadata": {"primary": True}}],
         "emailAddresses": [{"value": "mail@gmial.com"}]},       # dead_email_domain
    ]
    wc = seed_working_copy(db, account, people)
    run = validation_service.start_run(db, wc.id, default_region="KZ")
    validation_service.run_validation_job(
        db, run.id, website_check=lambda url, **_: WebsiteResult(status="reachable", final_url=url)
    )
    return run


def test_list_resolve_skip(db, client):
    run = _seed_run(db)

    items = client.get(f"/api/validation-runs/{run.id}/items").json()
    assert len(items) == 2
    assert {i["issueType"] for i in items} == {"unclear_type", "dead_email_domain"}

    unclear = next(i for i in items if i["issueType"] == "unclear_type")
    r = client.post(f"/api/validation-items/{unclear['id']}/resolve",
                    json={"action": "set_type", "type": "work"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    assert r.json()["stagedEditId"] is not None

    # re-resolving the same item conflicts
    r2 = client.post(f"/api/validation-items/{unclear['id']}/resolve",
                     json={"action": "set_type", "type": "home"})
    assert r2.status_code == 409

    dead = next(i for i in items if i["issueType"] == "dead_email_domain")
    s = client.post(f"/api/validation-items/{dead['id']}/skip")
    assert s.status_code == 200
    assert s.json()["status"] == "skipped"

    # pending now empty
    assert client.get(f"/api/validation-runs/{run.id}/items").json() == []


def test_resolve_unknown_item_404(client):
    assert client.post(f"/api/validation-items/{uuid.uuid4()}/skip").status_code == 404
