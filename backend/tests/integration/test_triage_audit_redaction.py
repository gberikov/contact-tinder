"""Integration: every triage mutation is audited with no PII/secrets in details (Polish / SC-007)."""
from __future__ import annotations

import json

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.audit import AuditEntry
from src.models.working_copy import WorkingCopyContact
from src.services import delete_batch_service, processing_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy

SECRET_TOKENS = ("Boris", "Petrov", "boris@", "+700", "refresh", "access")


def test_full_flow_is_audited_and_redacted(db):
    account = seed_account(db)
    account.granted_scopes += " " + get_settings().google_contacts_write_scope
    db.commit()
    wc = seed_working_copy(
        db, account,
        [dup_person(0, name="Boris Petrov", phone="+700", email="boris@x.com"),
         dup_person(1, name="Other Person", phone="+2")],
    )
    contacts = list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )
    ts, _ = triage_service.open_session(db, wc.id)

    # process + transliterate one, delete the other
    triage_service.set_decision(db, ts.id, contacts[0].id, outcome="process",
                                wants_transliterate=True)
    sug = processing_service.transliteration_suggestion(db, contacts[0].id)
    edit = processing_service.accept_transliteration(db, contacts[0].id, sug["fields"])
    processing_service.undo_staged_edit(db, edit.id)
    triage_service.set_decision(db, ts.id, contacts[1].id, outcome="delete")

    batch = delete_batch_service.create_batch(db, wc.id)
    delete_batch_service.confirm(db, batch.id)
    delete_batch_service.process_batch(db, batch.id, FakePeopleWriteClient())

    actions = {a.action for a in db.scalars(select(AuditEntry))}
    assert {
        "triage.session.started",
        "contact.sent_processing",
        "contact.transliterated",
        "edit.undone",
        "contact.queued_delete",
        "delete.batch.committed",
        "contact.deleted",
    } <= actions

    # No audit detail may contain contact PII or secret material (SC-007, FR-026).
    for entry in db.scalars(select(AuditEntry)):
        blob = json.dumps(entry.details or {})
        for token in SECRET_TOKENS:
            assert token not in blob
