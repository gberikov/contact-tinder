"""Label-batch lifecycle (feature 004): build, ensure the `Process` group, assign/remove members.

Mirrors delete_batch_service for the additive, reversible `Process` contact-group write (research D3).
The `Process` group is ensured once per account and cached in ContactLabel (D5). Member assignment is
idempotent and `404 → skipped_absent = success` (FR-012/012a); undo removes membership (FR-014). All
Google I/O goes through the injected PeopleWriteClient seam so CI drives the fake (Principle IV).
Staged edits/transliterations are NEVER written here — label only (FR-013/D4).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import backoff
from src.core.config import get_settings
from src.core.errors import ConflictError, NotFoundError
from src.integrations.people_client import (
    ContactNotFoundError,
    PeopleWriteClient,
    RateLimitedError,
    TransientError,
)
from src.models.export import ContactLabel, LabelAssignment, LabelBatch
from src.models.working_copy import WorkingCopyContact
from src.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_batch(session: Session, batch_id: uuid.UUID) -> LabelBatch:
    batch = session.get(LabelBatch, batch_id)
    if batch is None:
        raise NotFoundError("label batch not found")
    return batch


def create_batch(
    session: Session,
    *,
    working_copy_id: uuid.UUID,
    account_id: uuid.UUID,
    contacts: list[WorkingCopyContact],
    session_id: uuid.UUID | None = None,
) -> LabelBatch:
    """Build a staged batch with one LabelAssignment per contact in the (already-derived) label set."""
    if not contacts:
        raise ConflictError("no contacts are queued for labeling")
    batch = LabelBatch(
        working_copy_id=working_copy_id,
        session_id=session_id,
        account_id=account_id,
        status="staged",
        total_count=len(contacts),
    )
    batch.assignments = [
        LabelAssignment(
            working_copy_contact_id=c.id,
            origin_resource_name=c.origin_resource_name,
        )
        for c in contacts
    ]
    session.add(batch)
    session.flush()
    session.commit()
    return batch


def _ensure_group(session: Session, batch: LabelBatch, client: PeopleWriteClient) -> ContactLabel:
    """Resolve-or-create the `Process` group once per account; cache it in ContactLabel (D5)."""
    if batch.contact_label_id is not None:
        cached = session.get(ContactLabel, batch.contact_label_id)
        if cached is not None:
            return cached

    name = get_settings().process_label_name
    label = session.scalar(
        select(ContactLabel).where(
            ContactLabel.account_id == batch.account_id, ContactLabel.name == name
        )
    )
    if label is None:
        group_resource_name = client.ensure_label(name)
        label = ContactLabel(
            account_id=batch.account_id,
            name=name,
            group_resource_name=group_resource_name,
        )
        session.add(label)
        session.flush()
        audit_service.record(
            session,
            action="label.group.created",
            target_type="contact_label",
            target_id=label.id,
            source_ref=batch.id,
            details={"name": name},
        )
    batch.contact_label_id = label.id
    session.flush()
    return label


def _recount(batch: LabelBatch) -> None:
    batch.labeled_count = sum(
        1 for a in batch.assignments if a.status in ("labeled", "skipped_absent")
    )
    batch.failed_count = sum(1 for a in batch.assignments if a.status == "failed")


def process_batch(
    session: Session, batch_id: uuid.UUID, client: PeopleWriteClient, *, sleep=time.sleep
) -> LabelBatch:
    """Assign the `Process` group to pending/failed members idempotently (FR-012). Worker or tests.

    Retries each member on a rate-limit/transient error with backoff before marking it failed, and
    commits progress every ``export_commit_chunk_size`` members so `labeled_count` advances live and
    a crash never loses more than one chunk.
    """
    settings = get_settings()
    chunk, max_attempts = settings.export_commit_chunk_size, settings.export_max_attempts
    batch = get_batch(session, batch_id)
    label = _ensure_group(session, batch, client)
    since_commit = 0
    for asn in batch.assignments:
        if asn.status in ("labeled", "skipped_absent"):
            continue  # idempotent: never re-label
        try:
            backoff.retry_call(
                lambda rn=asn.origin_resource_name: client.add_label_members(
                    label.group_resource_name, [rn]
                ),
                max_attempts=max_attempts,
                retry_on=(RateLimitedError, TransientError),
                sleep=sleep,
            )
        except ContactNotFoundError:
            asn.status = "skipped_absent"  # gone in Google = success (FR-012a)
            asn.labeled_at = _now()
        except (RateLimitedError, TransientError) as exc:
            asn.status = "failed"  # retries exhausted
            asn.error = type(exc).__name__  # redacted
            since_commit = _maybe_commit(session, batch, since_commit + 1, chunk)
            continue
        else:
            asn.status = "labeled"
            asn.labeled_at = _now()
        audit_service.record(
            session,
            action="contact.labeled",
            target_type="working_copy_contact",
            target_id=asn.working_copy_contact_id or asn.id,
            source_ref=batch.id,
            details={"assignment": str(asn.id), "result": asn.status},
        )
        since_commit = _maybe_commit(session, batch, since_commit + 1, chunk)

    _recount(batch)
    if batch.failed_count:
        batch.status = "failed"
    else:
        batch.status = "committed"
        batch.committed_at = _now()
        audit_service.record(
            session,
            action="label.batch.committed",
            target_type="label_batch",
            target_id=batch.id,
            source_ref=batch.working_copy_id,
            details={"labeled": batch.labeled_count},
        )
    session.commit()
    return batch


def _maybe_commit(session: Session, batch: LabelBatch, since_commit: int, chunk: int) -> int:
    """Commit a chunk of progress (refreshing the live counts) and reset the counter."""
    if since_commit >= chunk:
        _recount(batch)
        session.commit()
        return 0
    return since_commit


def process_undo(
    session: Session, batch_id: uuid.UUID, client: PeopleWriteClient, *, sleep=time.sleep
) -> LabelBatch:
    """Remove `Process` membership for every labeled assignment (FR-014). Worker or tests."""
    settings = get_settings()
    chunk, max_attempts = settings.export_commit_chunk_size, settings.export_max_attempts
    batch = get_batch(session, batch_id)
    label = session.get(ContactLabel, batch.contact_label_id) if batch.contact_label_id else None
    since_commit = 0
    for asn in batch.assignments:
        if asn.status != "labeled":
            continue
        if label is not None:
            try:
                backoff.retry_call(
                    lambda rn=asn.origin_resource_name: client.remove_label_members(
                        label.group_resource_name, [rn]
                    ),
                    max_attempts=max_attempts,
                    retry_on=(RateLimitedError, TransientError),
                    sleep=sleep,
                )
            except ContactNotFoundError:
                pass  # already gone = already-satisfied (undo is idempotent)
        asn.status = "removed"
        asn.removed_at = _now()
        audit_service.record(
            session,
            action="contact.unlabeled",
            target_type="working_copy_contact",
            target_id=asn.working_copy_contact_id or asn.id,
            source_ref=batch.id,
            details={"assignment": str(asn.id)},
        )
        since_commit += 1
        if since_commit >= chunk:
            session.commit()
            since_commit = 0
    batch.status = "undone"
    batch.undone_at = _now()
    session.commit()
    return batch
