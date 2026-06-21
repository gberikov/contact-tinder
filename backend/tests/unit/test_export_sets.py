"""Unit: export set derivation — delete vs label vs excluded, disjoint, undecided (FR-001/002/003/017a)."""
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
    people = [
        dup_person(0, name="Del One", phone="+1"),
        dup_person(1, name="Proc Two", phone="+2"),
        dup_person(2, name="Keep Three", phone="+3"),
        dup_person(3, name="Undecided Four", phone="+4"),
    ]
    return seed_working_copy(db, account, people)


def test_delete_label_undecided_partition(db):
    wc = _wc(db)
    c = _contacts(db, wc)
    ts, _ = triage_service.open_session(db, wc.id)
    triage_service.set_decision(db, ts.id, c[0].id, outcome="delete")
    triage_service.set_decision(db, ts.id, c[1].id, outcome="process")
    triage_service.set_decision(db, ts.id, c[2].id, outcome="keep")
    # c[3] left undecided

    sets = export_service.derive_sets(db, wc.id)
    delete_ids = {x.id for x in sets.delete_contacts}
    label_ids = {x.id for x in sets.label_contacts}

    assert delete_ids == {c[0].id}
    assert label_ids == {c[1].id}
    assert sets.undecided_count == 1  # c[3]
    # keep (c[2]) is in neither set; sets are disjoint.
    assert delete_ids.isdisjoint(label_ids)


def test_processing_redecided_to_delete_is_delete_only(db):
    wc = _wc(db)
    c = _contacts(db, wc)
    ts, _ = triage_service.open_session(db, wc.id)
    triage_service.set_decision(db, ts.id, c[1].id, outcome="process")
    # Re-decide the same contact to delete (drops the processing item, latest decision wins).
    triage_service.set_decision(db, ts.id, c[1].id, outcome="delete")

    sets = export_service.derive_sets(db, wc.id)
    assert {x.id for x in sets.delete_contacts} == {c[1].id}
    assert c[1].id not in {x.id for x in sets.label_contacts}


def test_processed_then_done_is_labeled_not_undecided(db):
    """A processed contact marked done flips its decision to keep but stays in the label set (D2)."""
    from src.services import processing_service

    wc = _wc(db)
    c = _contacts(db, wc)
    ts, _ = triage_service.open_session(db, wc.id)
    triage_service.set_decision(db, ts.id, c[1].id, outcome="process")
    item = processing_service.list_processing(db, ts.id)[0]
    processing_service.complete_processing_item(db, item.id)

    sets = export_service.derive_sets(db, wc.id)
    assert {x.id for x in sets.label_contacts} == {c[1].id}
    assert c[1].id not in {x.id for x in sets.delete_contacts}
