"""Contract: processing queue, transliteration, edits, undo (US2)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(client, db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [dup_person(0, name="Boris Petrov", phone="+1")])
    cid = db.scalar(
        select(WorkingCopyContact.id).where(WorkingCopyContact.working_copy_id == wc.id)
    )
    sid = client.post(f"/api/working-copies/{wc.id}/triage-sessions").json()["id"]
    client.put(
        f"/api/triage-sessions/{sid}/decisions/{cid}",
        json={"outcome": "process", "wantsTransliterate": True, "wantsEdit": True},
    )
    return sid, cid


def test_processing_queue_and_item(client, db):
    sid, cid = _setup(client, db)
    queue = client.get(f"/api/triage-sessions/{sid}/processing")
    assert queue.status_code == 200 and len(queue.json()) == 1
    item_id = queue.json()[0]["id"]

    item = client.get(f"/api/processing-items/{item_id}").json()
    assert item["transliterationSuggestion"]["hasSuggestion"] is True


def test_suggestion_edit_transliterate_and_undo(client, db):
    sid, cid = _setup(client, db)
    sug = client.get(f"/api/working-copy-contacts/{cid}/transliteration-suggestion").json()
    assert sug["hasSuggestion"] is True

    edit = client.post(
        f"/api/working-copy-contacts/{cid}/transliteration", json={"fields": sug["fields"]}
    )
    assert edit.status_code == 200 and edit.json()["kind"] == "transliterate"
    edit_id = edit.json()["id"]

    undo = client.post(f"/api/staged-edits/{edit_id}/undo")
    assert undo.status_code == 200 and undo.json()["status"] == "undone"
    again = client.post(f"/api/staged-edits/{edit_id}/undo")
    assert again.status_code == 409


def test_done_marks_item_done(client, db):
    sid, cid = _setup(client, db)
    item_id = client.get(f"/api/triage-sessions/{sid}/processing").json()[0]["id"]
    done = client.post(f"/api/processing-items/{item_id}/done")
    assert done.status_code == 200 and done.json()["status"] == "done"
