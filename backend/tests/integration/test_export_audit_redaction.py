"""Integration: every export mutation is audited and no audit/report/log carries PII (FR-022/023, SC-007)."""
from __future__ import annotations

import json

from sqlalchemy import select

from src.core.config import get_settings
from src.models.audit import AuditEntry
from src.models.working_copy import WorkingCopyContact
from src.services import export_service, triage_service
from src.workers import delete_worker, label_worker
from tests.helpers import dup_person, seed_account, seed_working_copy

# Identifiable contact data that must NEVER appear in audit details / report.
_PII = ("Boris Petrov", "boris@example.com", "+79990001122")


def _setup(db):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    people = [
        dup_person(0, name="Boris Petrov", phone="+79990001122", email="boris@example.com"),
        dup_person(1, name="Proc Two", phone="+700"),
    ]
    wc = seed_working_copy(db, account, people)
    ts, _ = triage_service.open_session(db, wc.id)
    c = list(
        db.scalars(
            select(WorkingCopyContact)
            .where(WorkingCopyContact.working_copy_id == wc.id)
            .order_by(WorkingCopyContact.origin_resource_name)
        )
    )
    triage_service.set_decision(db, ts.id, c[0].id, outcome="delete")
    triage_service.set_decision(db, ts.id, c[1].id, outcome="process")
    return wc


def test_every_export_mutation_audited_and_redacted(db):
    wc = _setup(db)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    for _ in range(10):
        if not (delete_worker.run_once(db) or label_worker.run_once(db)):
            break
    export_service.get_run(db, run.id)  # triggers export.run.completed

    actions = set(
        db.scalars(select(AuditEntry.action)).all()
    )
    for expected in (
        "export.run.started",
        "export.run.completed",
        "label.group.created",
        "label.batch.committed",
        "contact.labeled",
        "contact.deleted",
    ):
        assert expected in actions, f"missing audit action {expected}"

    # No audit `details` blob may contain a contact's name / email / phone (FR-023).
    for entry in db.scalars(select(AuditEntry)).all():
        blob = json.dumps(entry.details or {})
        for pii in _PII:
            assert pii not in blob


def test_report_carries_no_pii(db):
    wc = _setup(db)
    run = export_service.start(db, wc.id)
    out = export_service.get_run(db, run.id)
    blob = out.model_dump_json()
    for pii in _PII:
        assert pii not in blob
