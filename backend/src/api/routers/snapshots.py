"""Snapshots router: create + import status (US1), read (US2), delete (Phase 6)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    ContactOut,
    ContactPage,
    CreateBody,
    ImportJobOut,
    SnapshotOut,
    WorkingCopyOut,
)
from src.core.db import get_session
from src.services import snapshot_service, working_copy_service

router = APIRouter(prefix="/api", tags=["snapshots"])


def _snapshot_out(snapshot, wc_count: int) -> SnapshotOut:
    return SnapshotOut(
        id=snapshot.id,
        accountId=snapshot.account_id,
        accountEmail=snapshot.account.email if snapshot.account else None,
        status=snapshot.status,
        source=snapshot.source,
        contactCount=snapshot.contact_count,
        workingCopyCount=wc_count,
        label=snapshot.label,
        createdAt=snapshot.created_at,
        finalizedAt=snapshot.finalized_at,
    )


@router.post("/accounts/{account_id}/snapshots", response_model=SnapshotOut, status_code=202)
def create_snapshot(
    account_id: uuid.UUID, body: CreateBody | None = None, session: Session = Depends(get_session)
) -> SnapshotOut:
    snapshot = snapshot_service.create_snapshot(
        session, account_id, label=body.label if body else None
    )
    return _snapshot_out(snapshot, 0)


@router.get("/snapshots", response_model=list[SnapshotOut])
def list_snapshots(session: Session = Depends(get_session)) -> list[SnapshotOut]:
    return [_snapshot_out(s, n) for s, n in snapshot_service.list_snapshots(session)]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(snapshot_id: uuid.UUID, session: Session = Depends(get_session)) -> SnapshotOut:
    snapshot = snapshot_service.get_snapshot(session, snapshot_id)
    return _snapshot_out(snapshot, snapshot_service.working_copy_count(session, snapshot_id))


@router.get("/snapshots/{snapshot_id}/import", response_model=ImportJobOut)
def get_import(snapshot_id: uuid.UUID, session: Session = Depends(get_session)) -> ImportJobOut:
    job = snapshot_service.get_import_job(session, snapshot_id)
    return ImportJobOut(
        snapshotId=snapshot_id,
        status=job.status,
        fetchedCount=job.fetched_count,
        totalEstimate=job.total_estimate,
        lastError=job.last_error,
        startedAt=job.started_at,
        finishedAt=job.finished_at,
    )


@router.get("/snapshots/{snapshot_id}/contacts", response_model=ContactPage)
def list_snapshot_contacts(
    snapshot_id: uuid.UUID,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
    session: Session = Depends(get_session),
) -> ContactPage:
    rows, total = snapshot_service.list_contacts(
        session, snapshot_id, page=page, page_size=pageSize, q=q
    )
    items = [
        ContactOut(
            id=c.id,
            resourceName=c.resource_name,
            displayName=c.display_name,
            primaryEmail=c.primary_email,
            primaryPhone=c.primary_phone,
            payload=c.payload,
        )
        for c in rows
    ]
    return ContactPage(items=items, page=page, pageSize=pageSize, total=total)


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(
    snapshot_id: uuid.UUID,
    confirm: bool = Query(...),
    session: Session = Depends(get_session),
) -> None:
    snapshot_service.delete_snapshot(session, snapshot_id, confirm=confirm)


@router.post(
    "/snapshots/{snapshot_id}/working-copies", response_model=WorkingCopyOut, status_code=201
)
def create_working_copy(
    snapshot_id: uuid.UUID, body: CreateBody | None = None, session: Session = Depends(get_session)
) -> WorkingCopyOut:
    copy = working_copy_service.create_working_copy(
        session, snapshot_id, label=body.label if body else None
    )
    return WorkingCopyOut(
        id=copy.id,
        snapshotId=copy.snapshot_id,
        label=copy.label,
        status=copy.status,
        contactCount=working_copy_service.contact_count(session, copy.id),
        createdAt=copy.created_at,
    )
