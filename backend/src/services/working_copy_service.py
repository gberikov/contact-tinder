"""Working copy creation (deep, independent copy) and reads (US3, FR-011/012/013)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.snapshot import Snapshot, SnapshotContact
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
