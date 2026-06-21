"""Unit: label-set derivation — processing-routed, not-deleted, active; disjoint from delete (FR-002, D2)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from src.services import export_service, triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _contacts(db, wc):
    return list(
        db.scalars(
            select(WorkingCopyContact)
            .where(WorkingCopyContact.working_copy_id == wc.id)
            .order_by(WorkingCopyContact.origin_resource_name)
        )
    )


def _wc(db):
    account = seed_account(db)
    people = [dup_person(i, name=f"C {i}", phone=f"+{i}") for i in range(3)]
    return seed_working_copy(db, account, people)


def test_label_set_is_processing_and_not_deleted(db):
    wc = _wc(db)
    c = _contacts(db, wc)
    ts, _ = triage_service.open_session(db, wc.id)
    triage_service.set_decision(db, ts.id, c[0].id, outcome="process")
    triage_service.set_decision(db, ts.id, c[1].id, outcome="delete")
    triage_service.set_decision(db, ts.id, c[2].id, outcome="keep")

    sets = export_service.derive_sets(db, wc.id)
    assert {x.id for x in sets.label_contacts} == {c[0].id}  # only the processing-routed one
    assert {x.id for x in sets.delete_contacts} == {c[1].id}


def test_retired_contact_excluded_from_label_set(db):
    wc = _wc(db)
    c = _contacts(db, wc)
    ts, _ = triage_service.open_session(db, wc.id)
    triage_service.set_decision(db, ts.id, c[0].id, outcome="process")
    # Contact goes inactive after triage (e.g. merged away) → excluded from the label set (FR-003).
    c[0].status = "retired"
    db.commit()

    sets = export_service.derive_sets(db, wc.id)
    assert sets.label_contacts == []
