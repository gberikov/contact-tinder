"""Snapshot lifecycle: create (+import job), read, delete (guarded)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.account import Account
from src.models.snapshot import ImportJob, Snapshot, SnapshotContact
from src.models.working_copy import WorkingCopy
from src.services import audit_service, working_copy_service

_ACTIVE_IMPORT_STATES = ("queued", "running")


def _has_active_import(session: Session, account_id: uuid.UUID) -> bool:
    stmt = (
        select(func.count())
        .select_from(ImportJob)
        .join(Snapshot, Snapshot.id == ImportJob.snapshot_id)
        .where(Snapshot.account_id == account_id, ImportJob.status.in_(_ACTIVE_IMPORT_STATES))
    )
    return bool(session.scalar(stmt))


def create_snapshot(session: Session, account_id: uuid.UUID, label: str | None = None) -> Snapshot:
    account = session.get(Account, account_id)
    if account is None:
        raise NotFoundError("account not found")
    if account.status != "connected":
        raise ConflictError("account requires re-authorization", code="reauth_required")
    if _has_active_import(session, account_id):
        raise ConflictError("an import is already in progress for this account")

    snapshot = Snapshot(account_id=account_id, status="importing", label=label)
    session.add(snapshot)
    session.flush()
    snapshot.import_job = ImportJob(snapshot_id=snapshot.id, status="queued")
    session.flush()

    audit_service.record(
        session,
        action="snapshot.created",
        target_type="snapshot",
        target_id=snapshot.id,
        source_ref=account_id,
        details={"label": label},
    )
    session.commit()
    return snapshot


def working_copy_count(session: Session, snapshot_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(WorkingCopy).where(
                WorkingCopy.snapshot_id == snapshot_id
            )
        )
        or 0
    )


def list_snapshots(session: Session) -> list[tuple[Snapshot, int]]:
    snapshots = list(session.scalars(select(Snapshot).order_by(Snapshot.created_at.desc())))
    return [(s, working_copy_count(session, s.id)) for s in snapshots]


def get_snapshot(session: Session, snapshot_id: uuid.UUID) -> Snapshot:
    snapshot = session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise NotFoundError("snapshot not found")
    return snapshot


def get_import_job(session: Session, snapshot_id: uuid.UUID) -> ImportJob:
    snapshot = get_snapshot(session, snapshot_id)
    return snapshot.import_job


def list_contacts(
    session: Session,
    snapshot_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
) -> tuple[list[SnapshotContact], int]:
    get_snapshot(session, snapshot_id)  # 404 if missing
    base = select(SnapshotContact).where(SnapshotContact.snapshot_id == snapshot_id)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(
            func.lower(func.coalesce(SnapshotContact.display_name, "")).like(like)
            | func.lower(func.coalesce(SnapshotContact.primary_email, "")).like(like)
        )
    total = int(
        session.scalar(select(func.count()).select_from(base.subquery())) or 0
    )
    rows = list(
        session.scalars(
            base.order_by(SnapshotContact.display_name).offset((page - 1) * page_size).limit(
                page_size
            )
        )
    )
    return rows, total


def delete_snapshot(session: Session, snapshot_id: uuid.UUID, *, confirm: bool) -> None:
    snapshot = get_snapshot(session, snapshot_id)
    if not confirm:
        raise ConflictError("deletion requires explicit confirmation", code="confirmation_required",
                            status_code=400)
    # Cascade: remove each working copy (and all its derived dedup/triage/export data) first,
    # so the snapshot's RESTRICT child constraint is satisfied (US Backup cleanup).
    for wc in session.scalars(
        select(WorkingCopy.id).where(WorkingCopy.snapshot_id == snapshot_id)
    ).all():
        working_copy_service.delete_working_copy(session, wc, confirm=True)

    snapshot = get_snapshot(session, snapshot_id)  # re-fetch after child commits
    snapshot.status = "deleting"
    session.flush()
    audit_service.record(
        session,
        action="snapshot.deleted",
        target_type="snapshot",
        target_id=snapshot.id,
        source_ref=snapshot.account_id,
        details={"contact_count": snapshot.contact_count},
    )
    session.delete(snapshot)
    session.commit()


def finalize_import(session: Session, snapshot: Snapshot, contact_count: int,
                    sync_token: str | None) -> None:
    snapshot.status = "complete"
    snapshot.contact_count = contact_count
    snapshot.next_sync_token = sync_token
    snapshot.finalized_at = datetime.now(timezone.utc)
    session.flush()
