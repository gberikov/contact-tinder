"""Validate & Normalize (Tidy) router (feature 006).

Start/list/get a validation run, work the manual queue (list/resolve/skip), and detect the initial
phone-parsing region from the client IP. Staged-edit undo reuses the existing
`POST /api/staged-edits/{id}/undo` route (feature 003). All access is scoped to the operator's own
Draft; nothing here writes to Google.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.api.schemas import (
    AutoFixOut,
    DetectRegionOut,
    ResolveValidationItemBody,
    StartValidationBody,
    ValidationItemOut,
    ValidationRunOut,
)
from src.core.db import get_session
from src.services import region_service, validation_service

router = APIRouter(prefix="/api", tags=["validation"])


@router.post(
    "/working-copies/{working_copy_id}/validation-runs",
    response_model=ValidationRunOut,
    status_code=201,
)
def start_validation_run(
    working_copy_id: uuid.UUID,
    body: StartValidationBody | None = None,
    session: Session = Depends(get_session),
) -> ValidationRunOut:
    body = body or StartValidationBody()
    run = validation_service.start_run(
        session, working_copy_id, session_id=body.sessionId, default_region=body.defaultRegion
    )
    return ValidationRunOut(**validation_service.run_out(session, run))


@router.get(
    "/working-copies/{working_copy_id}/validation-runs",
    response_model=list[ValidationRunOut],
)
def list_validation_runs(
    working_copy_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[ValidationRunOut]:
    runs = validation_service.list_runs(session, working_copy_id)
    return [ValidationRunOut(**validation_service.run_out(session, r)) for r in runs]


@router.get("/validation-runs/{run_id}", response_model=ValidationRunOut)
def get_validation_run(
    run_id: uuid.UUID, session: Session = Depends(get_session)
) -> ValidationRunOut:
    run = validation_service.get_run(session, run_id)
    return ValidationRunOut(**validation_service.run_out(session, run))


@router.get("/working-copies/{working_copy_id}/auto-fixes", response_model=list[AutoFixOut])
def list_auto_fixes(
    working_copy_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[AutoFixOut]:
    return [AutoFixOut(**f) for f in validation_service.list_auto_fixes(session, working_copy_id)]


@router.get("/validation-runs/{run_id}/items", response_model=list[ValidationItemOut])
def list_validation_items(
    run_id: uuid.UUID,
    status: str = Query("pending"),
    session: Session = Depends(get_session),
) -> list[ValidationItemOut]:
    items = validation_service.list_items(session, run_id, status=status)
    return [ValidationItemOut(**validation_service.item_out(session, i)) for i in items]


@router.post("/validation-items/{item_id}/resolve", response_model=ValidationItemOut)
def resolve_validation_item(
    item_id: uuid.UUID,
    body: ResolveValidationItemBody,
    session: Session = Depends(get_session),
) -> ValidationItemOut:
    item = validation_service.resolve_item(
        session, item_id, action=body.action, type=body.type, value=body.value
    )
    return ValidationItemOut(**validation_service.item_out(session, item))


@router.post("/validation-items/{item_id}/skip", response_model=ValidationItemOut)
def skip_validation_item(
    item_id: uuid.UUID, session: Session = Depends(get_session)
) -> ValidationItemOut:
    item = validation_service.skip_item(session, item_id)
    return ValidationItemOut(**validation_service.item_out(session, item))


@router.get("/settings/detect-region", response_model=DetectRegionOut)
def detect_region(request: Request) -> DetectRegionOut:
    client_ip = request.client.host if request.client else None
    region, source = region_service.detect_region(client_ip)
    return DetectRegionOut(region=region, source=source)
