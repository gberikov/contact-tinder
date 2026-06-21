"""Export orchestration (feature 004): derive sets, preview, start, confirm, undo, report.

An ExportRun ties together the reused delete path (feature 003) and the new `Process` label path. It
derives both sets from the current terminal triage decisions over the working copy's active survivors,
warns & excludes undecided survivors (FR-017a), and aggregates both batches' per-record results into a
report (FR-018). Deletion keeps its explicit, scope-gated confirmation; labeling is enqueued alongside
without a separate confirm (FR-015). Sets are DISJOINT (FR-002): delete = latest decision `delete`;
label = routed to processing and latest decision ≠ `delete`. All access is scoped to a working copy /
account (FR-021). Staged edits are NEVER pushed — label only (FR-013).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import (
    ExportContactSummaryOut,
    ExportPreviewOut,
    ExportReportOut,
    ExportRunOut,
)
from src.core.config import get_settings
from src.core.errors import AppError, ConflictError, NotFoundError
from src.models.account import Account
from src.models.export import ExportRun, LabelBatch
from src.models.snapshot import Snapshot
from src.models.triage import DeleteBatch, ProcessingItem, TriageDecision, TriageSession
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import (
    audit_service,
    contact_fields,
    contact_flatten,
    delete_batch_service,
    label_batch_service,
)

_TERMINAL_OK = ("committed", "undone")
_ACTIVE_STATES = ("committing", "labeling", "undoing", "unlabeling")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- Helpers ---------------------------------------------------------------------------------

def _require_working_copy(session: Session, working_copy_id: uuid.UUID) -> WorkingCopy:
    copy = session.get(WorkingCopy, working_copy_id)
    if copy is None:
        raise NotFoundError("working copy not found")
    return copy


def _account_for_working_copy(session: Session, working_copy_id: uuid.UUID) -> Account:
    copy = _require_working_copy(session, working_copy_id)
    snapshot = session.get(Snapshot, copy.snapshot_id)
    account = session.get(Account, snapshot.account_id) if snapshot else None
    if account is None:
        raise NotFoundError("account not found")
    return account


def _resolve_session(
    session: Session, working_copy_id: uuid.UUID, session_id: uuid.UUID | None
) -> TriageSession:
    if session_id is not None:
        ts = session.get(TriageSession, session_id)
        if ts is None or ts.working_copy_id != working_copy_id:
            raise NotFoundError("triage session not found")
        return ts
    ts = session.scalar(
        select(TriageSession)
        .where(TriageSession.working_copy_id == working_copy_id)
        .order_by(TriageSession.created_at.desc())
    )
    if ts is None:
        raise ConflictError("no triage session for this working copy")
    return ts


@dataclass
class DerivedSets:
    ts: TriageSession
    delete_contacts: list[WorkingCopyContact] = field(default_factory=list)
    label_contacts: list[WorkingCopyContact] = field(default_factory=list)
    undecided_count: int = 0


def derive_sets(
    session: Session, working_copy_id: uuid.UUID, session_id: uuid.UUID | None = None
) -> DerivedSets:
    """Derive the (disjoint) delete and label sets + the undecided count (FR-001/002/003/017a)."""
    _require_working_copy(session, working_copy_id)
    ts = _resolve_session(session, working_copy_id, session_id)

    active = list(
        session.scalars(
            select(WorkingCopyContact).where(
                WorkingCopyContact.working_copy_id == working_copy_id,
                WorkingCopyContact.status == "active",
            )
        )
    )
    decisions = {
        d.working_copy_contact_id: d.outcome
        for d in session.scalars(
            select(TriageDecision).where(TriageDecision.session_id == ts.id)
        )
    }
    processing_ids = set(
        session.scalars(
            select(ProcessingItem.working_copy_contact_id).where(
                ProcessingItem.session_id == ts.id
            )
        )
    )

    result = DerivedSets(ts=ts)
    for c in active:
        outcome = decisions.get(c.id)
        if outcome == "delete":
            result.delete_contacts.append(c)
        elif c.id in processing_ids and outcome != "delete":
            result.label_contacts.append(c)
        elif outcome is None:
            result.undecided_count += 1
    return result


def _summary(contact: WorkingCopyContact) -> ExportContactSummaryOut:
    return ExportContactSummaryOut(
        workingCopyContactId=contact.id,
        displayName=contact_fields.display_name(contact.payload),
        primaryEmail=contact_fields.primary_email(contact.payload),
        primaryPhone=contact_fields.primary_phone(contact.payload),
        organization=contact_flatten.organization(contact.payload),
    )


# ---- Preview (US3) ---------------------------------------------------------------------------

def preview(
    session: Session, working_copy_id: uuid.UUID, *, session_id: uuid.UUID | None = None
) -> ExportPreviewOut:
    """Dry-run derivation of both sets; nothing is written to Google (FR-004)."""
    sets = derive_sets(session, working_copy_id, session_id)
    delete_count = len(sets.delete_contacts)
    label_count = len(sets.label_contacts)
    return ExportPreviewOut(
        workingCopyId=working_copy_id,
        sessionId=sets.ts.id,
        deleteCount=delete_count,
        labelCount=label_count,
        undecidedCount=sets.undecided_count,
        nothingToExport=(delete_count == 0 and label_count == 0),
        labelName=get_settings().process_label_name,
        deleteSet=[_summary(c) for c in sets.delete_contacts],
        labelSet=[_summary(c) for c in sets.label_contacts],
    )


# ---- Run lifecycle ---------------------------------------------------------------------------

def _get_run(session: Session, run_id: uuid.UUID) -> ExportRun:
    run = session.get(ExportRun, run_id)
    if run is None:
        raise NotFoundError("export run not found")
    return run


def start(
    session: Session, working_copy_id: uuid.UUID, *, session_id: uuid.UUID | None = None
) -> ExportRunOut:
    """Create an ExportRun with its staged delete and/or label batches (FR-016)."""
    sets = derive_sets(session, working_copy_id, session_id)
    if not sets.delete_contacts and not sets.label_contacts:
        raise ConflictError("nothing to export")
    account = _account_for_working_copy(session, working_copy_id)

    run = ExportRun(
        working_copy_id=working_copy_id,
        account_id=account.id,
        session_id=sets.ts.id,
        status="previewing",
        undecided_count=sets.undecided_count,
    )
    session.add(run)
    session.flush()

    if sets.delete_contacts:
        batch = delete_batch_service.create_batch(session, working_copy_id, session_id=sets.ts.id)
        run.delete_batch_id = batch.id
    if sets.label_contacts:
        label_batch = label_batch_service.create_batch(
            session,
            working_copy_id=working_copy_id,
            account_id=account.id,
            contacts=sets.label_contacts,
            session_id=sets.ts.id,
        )
        run.label_batch_id = label_batch.id

    audit_service.record(
        session,
        action="export.run.started",
        target_type="export_run",
        target_id=run.id,
        source_ref=working_copy_id,
        details={
            "delete": len(sets.delete_contacts),
            "label": len(sets.label_contacts),
            "undecided": sets.undecided_count,
        },
    )
    session.commit()
    return _run_out(session, run)


def confirm_delete(session: Session, run_id: uuid.UUID) -> ExportRunOut:
    """Confirm the delete half (scope-gated, 403 if no write scope) and enqueue both batches (FR-015)."""
    run = _get_run(session, run_id)
    if run.delete_batch_id is not None:
        # Scope-gated confirm; raises 403 write_scope_required when the account lacks the scope.
        delete_batch_service.confirm(session, run.delete_batch_id)
    else:
        # Label-only export still needs the write scope (labeling reuses it — research D1).
        account = session.get(Account, run.account_id)
        if account is None or not delete_batch_service.account_has_write_scope(account):
            raise AppError(
                "google contacts write scope required — re-consent needed",
                code="write_scope_required",
                status_code=403,
            )

    if run.label_batch_id is not None:
        label_batch = session.get(LabelBatch, run.label_batch_id)
        if label_batch is not None and label_batch.status == "staged":
            label_batch.status = "labeling"  # enqueue alongside, no separate confirm (FR-015)

    run.status = "running"
    session.commit()
    return _run_out(session, run)


def undo_delete(session: Session, run_id: uuid.UUID) -> ExportRunOut:
    run = _get_run(session, run_id)
    if run.delete_batch_id is None:
        raise ConflictError("this export has no deletion to undo")
    delete_batch_service.request_undo(session, run.delete_batch_id)  # requires committed
    return _run_out(session, run)


def undo_label(session: Session, run_id: uuid.UUID) -> ExportRunOut:
    run = _get_run(session, run_id)
    if run.label_batch_id is None:
        raise ConflictError("this export has no labeling to undo")
    label_batch = session.get(LabelBatch, run.label_batch_id)
    if label_batch is None or label_batch.status != "committed":
        raise ConflictError("label batch is not in an undoable state")
    label_batch.status = "unlabeling"
    session.commit()
    return _run_out(session, run)


def get_run(session: Session, run_id: uuid.UUID) -> ExportRunOut:
    return _run_out(session, _get_run(session, run_id))


# ---- Report & status reconciliation ----------------------------------------------------------

def _reconcile_status(
    run: ExportRun, delete_batch: DeleteBatch | None, label_batch: LabelBatch | None
) -> None:
    statuses = [b.status for b in (delete_batch, label_batch) if b is not None]
    if not statuses:
        return
    # Stay in `previewing` until something has been confirmed/enqueued.
    if run.status == "previewing" and all(s in ("staged", "previewed") for s in statuses):
        return
    if any(s == "failed" for s in statuses):
        run.status = "failed"
    elif all(s in _TERMINAL_OK for s in statuses):
        run.status = "completed"
        if run.completed_at is None:
            run.completed_at = _now()
    elif any(s in _ACTIVE_STATES for s in statuses) or run.status != "previewing":
        run.status = "running"


def _report(
    run: ExportRun, delete_batch: DeleteBatch | None, label_batch: LabelBatch | None
) -> ExportReportOut:
    deleted = skipped_delete = failed = 0
    if delete_batch is not None:
        for rec in delete_batch.records:
            if rec.status == "deleted":
                deleted += 1
            elif rec.status == "skipped_absent":
                skipped_delete += 1
            elif rec.status == "failed":
                failed += 1
    labeled = skipped_label = 0
    if label_batch is not None:
        for asn in label_batch.assignments:
            if asn.status == "labeled":
                labeled += 1
            elif asn.status == "skipped_absent":
                skipped_label += 1
            elif asn.status == "failed":
                failed += 1
    return ExportReportOut(
        deleted=deleted,
        skippedAbsentDelete=skipped_delete,
        labeled=labeled,
        skippedAbsentLabel=skipped_label,
        failed=failed,
        excluded=run.undecided_count,
        deleteStatus=delete_batch.status if delete_batch is not None else None,
        labelStatus=label_batch.status if label_batch is not None else None,
    )


def _run_out(session: Session, run: ExportRun) -> ExportRunOut:
    delete_batch = (
        session.get(DeleteBatch, run.delete_batch_id) if run.delete_batch_id else None
    )
    label_batch = session.get(LabelBatch, run.label_batch_id) if run.label_batch_id else None

    before = (run.status, run.completed_at)
    _reconcile_status(run, delete_batch, label_batch)
    if (run.status, run.completed_at) != before:
        if run.status == "completed":
            audit_service.record(
                session,
                action="export.run.completed",
                target_type="export_run",
                target_id=run.id,
                source_ref=run.working_copy_id,
                details={"status": run.status},
            )
        session.commit()

    return ExportRunOut(
        id=run.id,
        workingCopyId=run.working_copy_id,
        accountId=run.account_id,
        sessionId=run.session_id,
        deleteBatchId=run.delete_batch_id,
        labelBatchId=run.label_batch_id,
        status=run.status,
        undecidedCount=run.undecided_count,
        createdAt=run.created_at,
        completedAt=run.completed_at,
        report=_report(run, delete_batch, label_batch),
    )
