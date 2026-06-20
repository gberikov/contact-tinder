"""Working copies router: list + paginated contacts (US3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.schemas import ContactOut, ContactPage, WorkingCopyOut
from src.core.db import get_session
from src.services import working_copy_service

router = APIRouter(prefix="/api/working-copies", tags=["working-copies"])


@router.get("", response_model=list[WorkingCopyOut])
def list_working_copies(session: Session = Depends(get_session)) -> list[WorkingCopyOut]:
    return [
        WorkingCopyOut(
            id=c.id,
            snapshotId=c.snapshot_id,
            label=c.label,
            status=c.status,
            contactCount=n,
            createdAt=c.created_at,
        )
        for c, n in working_copy_service.list_working_copies(session)
    ]


@router.get("/{working_copy_id}/contacts", response_model=ContactPage)
def list_contacts(
    working_copy_id: uuid.UUID,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> ContactPage:
    rows, total = working_copy_service.list_contacts(
        session, working_copy_id, page=page, page_size=pageSize
    )
    items = [
        ContactOut(
            id=c.id,
            resourceName=c.origin_resource_name,
            displayName=(c.payload.get("names") or [{}])[0].get("displayName"),
            payload=c.payload,
        )
        for c in rows
    ]
    return ContactPage(items=items, page=page, pageSize=pageSize, total=total)
