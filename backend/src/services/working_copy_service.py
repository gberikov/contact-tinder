"""Working copy creation (deep, independent copy) and reads (US3, FR-011/012/013)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.dedup import DedupRun
from src.models.export import ExportRun, LabelBatch
from src.models.snapshot import Snapshot, SnapshotContact
from src.models.triage import DeleteBatch, StagedEdit, TriageSession
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service


def create_working_copy(session: Session, snapshot_id: uuid.UUID, label: str | None = None) -> WorkingCopy:
    snapshot = session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise NotFoundError("snapshot not found")
    if snapshot.status != "complete":
        raise ConflictError("snapshot is not complete")

    copy = WorkingCopy(snapshot_id=snapshot_id, label=label or "Working copy", status="creating")
    session.add(copy)
    session.flush()

    # Deep copy: independent rows, never sharing with the snapshot (FR-011/FR-012).
    contacts = session.scalars(
        select(SnapshotContact).where(SnapshotContact.snapshot_id == snapshot_id)
    )
    for c in contacts:
        session.add(
            WorkingCopyContact(
                working_copy_id=copy.id,
                origin_resource_name=c.resource_name,
                payload=dict(c.payload),
            )
        )
    copy.status = "ready"
    session.flush()

    audit_service.record(
        session,
        action="working_copy.created",
        target_type="working_copy",
        target_id=copy.id,
        source_ref=snapshot_id,
        details={"label": copy.label},
    )
    session.commit()
    return copy


def contact_count(session: Session, working_copy_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(WorkingCopyContact).where(
                WorkingCopyContact.working_copy_id == working_copy_id
            )
        )
        or 0
    )


def list_working_copies(session: Session) -> list[tuple[WorkingCopy, int]]:
    copies = list(session.scalars(select(WorkingCopy).order_by(WorkingCopy.created_at.desc())))
    return [(c, contact_count(session, c.id)) for c in copies]


def get_working_copy(session: Session, working_copy_id: uuid.UUID) -> WorkingCopy:
    copy = session.get(WorkingCopy, working_copy_id)
    if copy is None:
        raise NotFoundError("working copy not found")
    return copy


def list_contacts(
    session: Session, working_copy_id: uuid.UUID, *, page: int = 1, page_size: int = 50
) -> tuple[list[WorkingCopyContact], int]:
    get_working_copy(session, working_copy_id)
    base = select(WorkingCopyContact).where(WorkingCopyContact.working_copy_id == working_copy_id)
    total = int(session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = list(
        session.scalars(base.offset((page - 1) * page_size).limit(page_size))
    )
    return rows, total


def delete_working_copy(session: Session, working_copy_id: uuid.UUID, *, confirm: bool) -> None:
    """Delete a draft and every dedup/triage/export row derived from it (US3 cleanup).

    Cascade runs in the service layer (not via DB FK) so it fires identically on SQLite (tests)
    and Postgres. Order is FK-safe: rows that reference others (export runs; the batches/sessions)
    are deleted before their targets, and merge records (which hard-reference working_copy_contact)
    are removed via the dedup-run ORM cascade before the contacts themselves.
    """
    copy = get_working_copy(session, working_copy_id)  # 404 if missing
    if not confirm:
        raise ConflictError(
            "deletion requires explicit confirmation",
            code="confirmation_required",
            status_code=400,
        )
    label = copy.label
    n_contacts = contact_count(session, working_copy_id)

    def _purge(model) -> None:
        for obj in session.scalars(
            select(model).where(model.working_copy_id == working_copy_id)
        ):
            session.delete(obj)  # per-object delete triggers ORM "all, delete-orphan" cascade
        session.flush()

    _purge(ExportRun)
    _purge(LabelBatch)  # → label_assignment
    _purge(DeleteBatch)  # → deletion_record
    _purge(TriageSession)  # → triage_decision, processing_item
    _purge(StagedEdit)
    _purge(DedupRun)  # → duplicate_cluster → cluster_member, merge_record

    audit_service.record(
        session,
        action="working_copy.deleted",
        target_type="working_copy",
        target_id=copy.id,
        source_ref=copy.snapshot_id,
        details={"label": label, "contact_count": n_contacts},
    )
    session.delete(copy)  # → working_copy_contact (ORM cascade)
    session.commit()
