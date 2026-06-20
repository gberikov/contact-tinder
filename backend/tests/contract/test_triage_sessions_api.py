"""Contract: triage session / deck / decision endpoints (US1 / FR-001..007)."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from tests.helpers import dup_person, seed_account, seed_working_copy


def _wc(db):
    account = seed_account(db)
    people = [
        dup_person(0, name="Boris Petrov", phone="+1", email="b@x.com"),
        dup_person(1, name="Anna Ivanova", phone="+2", email="a@x.com"),
        dup_person(2, name="Carl Young", phone="+3", email="c@x.com"),
    ]
    return seed_working_copy(db, account, people)


def _contact_ids(db, wc):
    rows = list(
        db.scalars(
            select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id)
        )
    )
    return [r.id for r in rows]


def test_open_session_201_then_200(client, db):
    wc = _wc(db)
    first = client.post(f"/api/working-copies/{wc.id}/triage-sessions")
    assert first.status_code == 201
    body = first.json()
    assert body["status"] == "in_progress"
    assert body["summary"]["total"] == 3
    assert body["summary"]["remaining"] == 3
    second = client.post(f"/api/working-copies/{wc.id}/triage-sessions")
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]


def test_deck_stable_order_and_decisions(client, db):
    wc = _wc(db)
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    deck = client.get(f"/api/triage-sessions/{sid}/deck?limit=10").json()
    names = [c["contact"]["displayName"] for c in deck["cards"]]
    assert names == ["Anna Ivanova", "Boris Petrov", "Carl Young"]  # stable by name

    first_contact = deck["cards"][0]["workingCopyContactId"]
    put = client.put(
        f"/api/triage-sessions/{sid}/decisions/{first_contact}", json={"outcome": "keep"}
    )
    assert put.status_code == 200 and put.json()["outcome"] == "keep"

    summary = client.get(f"/api/triage-sessions/{sid}").json()["summary"]
    assert summary["keep"] == 1 and summary["remaining"] == 2


def test_decision_then_undo(client, db):
    wc = _wc(db)
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    cid = _contact_ids(db, wc)[0]
    client.put(f"/api/triage-sessions/{sid}/decisions/{cid}", json={"outcome": "delete"})
    undo = client.delete(f"/api/triage-sessions/{sid}/decisions/{cid}")
    assert undo.status_code == 204
    assert client.get(f"/api/triage-sessions/{sid}").json()["summary"]["remaining"] == 3


def test_decision_on_foreign_contact_409(client, db):
    wc = _wc(db)
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    resp = client.put(
        f"/api/triage-sessions/{sid}/decisions/{uuid.uuid4()}", json={"outcome": "keep"}
    )
    assert resp.status_code == 409


def test_missing_working_copy_404(client):
    resp = client.post(f"/api/working-copies/{uuid.uuid4()}/triage-sessions")
    assert resp.status_code == 404
