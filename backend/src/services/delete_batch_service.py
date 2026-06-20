"""Delete-batch lifecycle: build (snapshot first), preview, confirm (scope-gated), commit, undo.

The ONLY Google writes in the product. A restorable DeletionRecord.payload_before is captured for
every contact BEFORE any Google call (SC-002, FR-020); confirm is gated on the contacts write scope
(D9); execution is idempotent and undoable (FR-022/023/024). `process_batch`/`process_undo` take an
injected PeopleWriteClient so CI drives them with the fake (Principle IV).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import backoff
from src.core.config import get_settings
from src.core.errors import AppError, ConflictError, NotFoundError
from src.integrations.people_client import (
    ContactNotFoundError,
    PeopleWriteClient,
    RateLimitedError,
    TransientError,
)
from src.models.account import Account
from src.models.snapshot import Snapshot
from src.models.triage import DeleteBatch, DeletionRecord, TriageDecision, TriageSession
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _account_for_working_copy(session: Session, working_copy_id: uuid.UUID) -> Account:
    copy = session.get(WorkingCopy, working_copy_id)
    if copy is None:
        raise NotFoundError("working copy not found")
    snapshot = session.get(Snapshot, copy.snapshot_id)
    account = session.get(Account, snapshot.account_id) if snapshot else None
    if account is None:
        raise NotFoundError("account not found")
    return account


def account_has_write_scope(account: Account) -> bool:
    scope = get_settings().google_contacts_write_scope
    return scope in (account.granted_scopes or "").split()


def get_batch(session: Session, batch_id: uuid.UUID) -> DeleteBatch:
    batch = session.get(DeleteBatch, batch_id)
    if batch is None:
        raise NotFoundError("delete batch not found")
    return batch


def _resolve_session(
    session: Session, working_copy_id: uuid.UUID, session_id: uuid.UUID | None
) -> TriageSession:
    if session_id is not None:
        ts = session.get(TriageSession, session_id)
        if ts is None or ts.working_copy_id != working_copy_id:
            raise NotFoundError("triage session not found")
        return ts
    # The batch is normally built after triage completes, so accept the most recent session of
    # any status (a completed session still holds its `delete` decisions).
    ts = session.scalar(
        select(TriageSession)
        .where(TriageSession.working_copy_id == working_copy_id)
        .order_by(TriageSession.created_at.desc())
    )
    if ts is None:
        raise ConflictError("no triage session for this working copy")
    return ts


def create_batch(
    session: Session, working_copy_id: uuid.UUID, *, session_id: uuid.UUID | None = None
) -> DeleteBatch:
    """Build a staged batch from the session's `delete` decisions, snapshotting each contact (FR-018/020)."""
    account = _account_for_working_copy(session, working_copy_id)
    ts = _resolve_session(session, working_copy_id, session_id)

    decisions = session.scalars(
        select(TriageDecision).where(
            TriageDecision.session_id == ts.id, TriageDecision.outcome == "delete"
        )
    )
    records: list[DeletionRecord] = []
    for d in decisions:
        contact = session.get(WorkingCopyContact, d.working_copy_contact_id)
        # FR-027: only contacts still active are deletable; stale ones are excluded.
        if contact is None or contact.status != "active":
            continue
        records.append(
            DeletionRecord(
                working_copy_contact_id=contact.id,
                origin_resource_name=contact.origin_resource_name,
                payload_before=dict(contact.payload),  # snapshot BEFORE any Google call (SC-002)
            )
        )
    if not records:
        raise ConflictError("no contacts are queued for deletion")

    batch = DeleteBatch(
        working_copy_id=working_copy_id,
        session_id=ts.id,
        account_id=account.id,
        status="staged",
        total_count=len(records),
    )
    batch.records = records
    session.add(batch)
    session.flush()
    session.commit()
    return batch


def preview(session: Session, batch_id: uuid.UUID) -> list[DeletionRecord]:
    """Dry-run list of contacts that will be deleted; nothing is sent to Google (FR-019)."""
    batch = get_batch(session, batch_id)
    if batch.status == "staged":
        batch.status = "previewed"
        batch.previewed_at = _now()
        audit_service.record(
            session,
            action="delete.batch.previewed",
            target_type="delete_batch",
            target_id=batch.id,
            source_ref=batch.working_copy_id,
            details={"total": batch.total_count},
        )
        session.commit()
    return list(batch.records)


def confirm(session: Session, batch_id: uuid.UUID) -> DeleteBatch:
    """Confirm + enqueue deletion; rejected (403) if the account lacks the write scope (D9, FR-021)."""
    batch = get_batch(session, batch_id)
    if batch.status not in ("staged", "previewed"):
        raise ConflictError("batch is not in a confirmable state")
    account = session.get(Account, batch.account_id)
    if account is None or not account_has_write_scope(account):
        raise AppError(
            "google contacts write scope required — re-consent needed",
            code="write_scope_required",
            status_code=403,
        )
    batch.status = "committing"
    audit_service.record(
        session,
        action="delete.batch.committed",
        target_type="delete_batch",
        target_id=batch.id,
        source_ref=batch.working_copy_id,
        details={"total": batch.total_count},
    )
    session.commit()
    return batch


def request_undo(session: Session, batch_id: uuid.UUID) -> DeleteBatch:
    batch = get_batch(session, batch_id)
    if batch.status != "committed":
        raise ConflictError("batch is not in an undoable state")
    batch.status = "undoing"
    session.commit()
    return batch


def _recount(batch: DeleteBatch) -> None:
    batch.deleted_count = sum(
        1 for r in batch.records if r.status in ("deleted", "skipped_absent")
    )
    batch.failed_count = sum(1 for r in batch.records if r.status == "failed")


def process_batch(
    session: Session, batch_id: uuid.UUID, client: PeopleWriteClient, *, sleep=time.sleep
) -> DeleteBatch:
    """Execute pending/failed deletions idempotently (FR-022/024). Callable by worker or tests.

    Retries each contact on a rate-limit/transient error with backoff before marking it failed, and
    commits progress every ``export_commit_chunk_size`` records so `deleted_count` advances live and
    a crash never loses more than one chunk (already-done records are skipped on re-run).
    """
    settings = get_settings()
    chunk, max_attempts = settings.export_commit_chunk_size, settings.export_max_attempts
    pace = settings.export_write_min_interval_seconds
    batch = get_batch(session, batch_id)
    since_commit = 0
    for rec in batch.records:
        if rec.status in ("deleted", "skipped_absent"):
            continue  # idempotent: never re-delete
        if pace:
            sleep(pace)  # stay under Google's per-minute write quota
        try:
            backoff.retry_call(
                lambda rn=rec.origin_resource_name: client.delete_contact(rn),
                max_attempts=max_attempts,
                retry_on=(RateLimitedError, TransientError),
                sleep=sleep,
            )
        except ContactNotFoundError:
            rec.status = "skipped_absent"  # already gone = success (FR-024)
            rec.deleted_at = _now()
        except (RateLimitedError, TransientError) as exc:
            rec.status = "failed"  # retries exhausted
            rec.error = type(exc).__name__  # redacted
            since_commit = _maybe_commit(session, batch, since_commit + 1, chunk)
            continue
        else:
            rec.status = "deleted"
            rec.deleted_at = _now()
        if rec.working_copy_contact_id is not None:
            contact = session.get(WorkingCopyContact, rec.working_copy_contact_id)
            if contact is not None:
                contact.status = "retired"  # gone in Google ⇒ not a live survivor
        audit_service.record(
            session,
            action="contact.deleted",
            target_type="working_copy_contact",
            target_id=rec.working_copy_contact_id or rec.id,
            source_ref=batch.id,
            details={"record": str(rec.id), "result": rec.status},
        )
        since_commit = _maybe_commit(session, batch, since_commit + 1, chunk)

    _recount(batch)
    batch.status = "failed" if batch.failed_count else "committed"
    batch.committed_at = _now()
    session.commit()
    return batch


def _maybe_commit(session: Session, batch: DeleteBatch, since_commit: int, chunk: int) -> int:
    """Commit a chunk of progress (refreshing the live counts) and reset the counter."""
    if since_commit >= chunk:
        _recount(batch)
        session.commit()
        return 0
    return since_commit


def process_undo(
    session: Session, batch_id: uuid.UUID, client: PeopleWriteClient, *, sleep=time.sleep
) -> DeleteBatch:
    """Re-create every deleted contact from its snapshot (FR-023). Callable by worker or tests."""
    settings = get_settings()
    chunk, max_attempts = settings.export_commit_chunk_size, settings.export_max_attempts
    pace = settings.export_write_min_interval_seconds
    batch = get_batch(session, batch_id)
    since_commit = 0
    for rec in batch.records:
        if rec.status not in ("deleted", "skipped_absent"):
            continue
        if pace:
            sleep(pace)
        new_rn = backoff.retry_call(
            lambda payload=rec.payload_before: client.create_contact(payload),
            max_attempts=max_attempts,
            retry_on=(RateLimitedError, TransientError),
            sleep=sleep,
        )
        rec.restored_resource_name = new_rn
        rec.status = "restored"
        rec.restored_at = _now()
        if rec.working_copy_contact_id is not None:
            contact = session.get(WorkingCopyContact, rec.working_copy_contact_id)
            if contact is not None:
                contact.status = "active"
        audit_service.record(
            session,
            action="contact.restored",
            target_type="working_copy_contact",
            target_id=rec.working_copy_contact_id or rec.id,
            source_ref=batch.id,
            details={"record": str(rec.id)},
        )
        since_commit += 1
        if since_commit >= chunk:
            session.commit()
            since_commit = 0
    batch.status = "undone"
    batch.undone_at = _now()
    session.commit()
    return batch
