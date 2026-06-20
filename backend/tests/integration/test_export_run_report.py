"""Integration: unified export run + report driven by the workers (FR-018/019, SC-004)."""
from __future__ import annotations

from sqlalchemy import select

from src.core.config import get_settings
from src.models.working_copy import WorkingCopyContact
from src.services import export_service, triage_service
from src.workers import delete_worker, label_worker
from tests.helpers import dup_person, seed_account, seed_working_copy


def _setup(db):
    account = seed_account(db)
    account.granted_scopes = (
        account.granted_scopes + " " + get_settings().google_contacts_write_scope
    ).strip()
    db.commit()
    people = [dup_person(i, name=f"C {i}", phone=f"+{i}") for i in range(3)]
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
    triage_service.set_decision(db, ts.id, c[2].id, outcome="keep")
    return wc


def _drain_workers(db):
    # Default PEOPLE_WRITE_CLIENT is the fake (CI), so the workers use it.
    for _ in range(10):
        worked = delete_worker.run_once(db) or label_worker.run_once(db)
        if not worked:
            break


def test_full_run_to_completed_with_report(db):
    wc = _setup(db)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    _drain_workers(db)

    out = export_service.get_run(db, run.id)
    assert out.status == "completed"
    assert out.completedAt is not None
    assert out.report.deleted == 1
    assert out.report.labeled == 1
    assert out.report.failed == 0
    assert out.report.deleteStatus == "committed"
    assert out.report.labelStatus == "committed"


def test_rerun_after_completion_changes_nothing(db):
    wc = _setup(db)
    run = export_service.start(db, wc.id)
    export_service.confirm_delete(db, run.id)
    _drain_workers(db)
    first = export_service.get_run(db, run.id)

    # The workers have nothing left to claim (terminal batches); re-draining is a no-op.
    _drain_workers(db)
    second = export_service.get_run(db, run.id)
    assert (second.report.deleted, second.report.labeled) == (
        first.report.deleted,
        first.report.labeled,
    )
    assert second.status == "completed"
