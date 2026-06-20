"""Integration: the export labels but NEVER pushes staged edits to Google (FR-013, quickstart E)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.integrations.people_client import FakePeopleWriteClient
from src.models.export import ExportRun
from src.models.working_copy import WorkingCopyContact
from src.services import export_service, label_batch_service, processing_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def test_label_only_no_contact_writes(db):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    wc = seed_working_copy(db, account, [dup_person(0, name="Boris", phone="+700")])
    ts, _ = triage_service.open_session(db, wc.id)
    c = db.scalar(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))

    # Route to processing and stage an edit (feature 003) — this must NOT be pushed.
    triage_service.set_decision(db, ts.id, c.id, outcome="process", wants_edit=True)
    edited = dict(c.payload)
    edited["names"] = [{"displayName": "Boris EDITED", "metadata": {"primary": True}}]
    processing_service.apply_edit(db, c.id, edited)

    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    batch_id = db.get(ExportRun, run.id).label_batch_id

    client = FakePeopleWriteClient()
    label_batch_service.process_batch(db, batch_id, client)

    # The export added only group membership — no contact create/update was made to Google.
    assert client.created == {}  # no createContact (the only write besides delete/label-membership)
    assert client.deleted == []  # nothing deleted
    group = client.groups["Process"]
    assert client.group_members[group] == {c.origin_resource_name}  # labeled only
    # The staged edit still lives in the working copy (local), unsynced.
    db.refresh(c)
    assert c.payload["names"][0]["displayName"] == "Boris EDITED"
