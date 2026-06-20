"""Integration: process → edit / transliterate → keep, reversible (US2 / FR-011..016, D4/D6)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.triage import TriageDecision
from src.models.working_copy import WorkingCopyContact
from src.services import processing_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _wc(db):
    account = seed_account(db)
    return seed_working_copy(db, account, [dup_person(0, name="Boris Petrov", phone="+700")])


def _contact(db, wc):
    return db.scalar(
        select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id)
    )


def test_process_creates_pending_item_without_editing(db):
    wc = _wc(db)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contact(db, wc)
    before = dict(c.payload)
    triage_service.set_decision(db, ts.id, c.id, outcome="process", wants_transliterate=True)
    items = processing_service.list_processing(db, ts.id)
    assert len(items) == 1 and items[0].status == "pending"
    db.refresh(c)
    assert c.payload == before  # swipe did not edit the contact (FR-011)


def test_transliteration_changes_only_name_and_is_reversible(db):
    wc = _wc(db)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contact(db, wc)
    triage_service.set_decision(db, ts.id, c.id, outcome="process", wants_transliterate=True)

    suggestion = processing_service.transliteration_suggestion(db, c.id)
    assert suggestion["hasSuggestion"] is True
    edit = processing_service.accept_transliteration(db, c.id, suggestion["fields"])

    db.refresh(c)
    assert c.payload["names"][0]["givenName"] == "Борис"
    assert c.payload["phoneNumbers"] == [{"value": "+700", "metadata": {"primary": True}}]

    processing_service.undo_staged_edit(db, edit.id)
    db.refresh(c)
    assert c.payload["names"][0]["givenName"] == "Boris"  # restored exactly


def test_edit_then_done_defaults_to_keep(db):
    wc = _wc(db)
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contact(db, wc)
    triage_service.set_decision(db, ts.id, c.id, outcome="process", wants_edit=True)

    new_payload = dict(c.payload)
    new_payload["names"] = [{"displayName": "Boris P.", "metadata": {"primary": True}}]
    processing_service.apply_edit(db, c.id, new_payload)

    item = processing_service.list_processing(db, ts.id)[0]
    processing_service.complete_processing_item(db, item.id)

    decision = db.scalar(
        select(TriageDecision).where(
            TriageDecision.session_id == ts.id, TriageDecision.working_copy_contact_id == c.id
        )
    )
    assert decision.outcome == "keep"  # D4: defaults to keep once processed
    db.refresh(ts)
    assert ts.status == "complete"  # single contact, now terminal
