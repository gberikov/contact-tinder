"""Unit: deck ordering + cursor paging and the completion predicate (US1 / D1, D3, D4)."""
from __future__ import annotations

from sqlalchemy import select

from src.models.working_copy import WorkingCopyContact
from src.services import triage_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _wc(db, names):
    account = seed_account(db)
    people = [dup_person(i, name=n, phone=f"+{i}") for i, n in enumerate(names)]
    return seed_working_copy(db, account, people)


def _contacts(db, wc):
    return list(
        db.scalars(select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == wc.id))
    )


def test_deck_orders_by_name_then_pages_by_cursor(db):
    wc = _wc(db, ["Zoe Last", "Alan Last", "Mona Last"])
    ts, _ = triage_service.open_session(db, wc.id)

    page1, cursor = triage_service.deck(db, ts.id, limit=2)
    assert [triage_service.contact_detail(c)["displayName"] for c in page1] == [
        "Alan Last",
        "Mona Last",
    ]
    assert cursor is not None
    page2, cursor2 = triage_service.deck(db, ts.id, cursor=cursor, limit=2)
    assert [triage_service.contact_detail(c)["displayName"] for c in page2] == ["Zoe Last"]
    assert cursor2 is None


def test_processing_blocks_completion_until_done(db):
    wc = _wc(db, ["Solo Person"])
    ts, _ = triage_service.open_session(db, wc.id)
    c = _contacts(db, wc)[0]
    triage_service.set_decision(db, ts.id, c.id, outcome="process")
    db.refresh(ts)
    # Decided but a pending ProcessingItem keeps the session open (D4).
    assert ts.status == "in_progress"
