"""Export-to-Google router (feature 004): one Export screen + label-batch endpoints.

Mirrors contracts/openapi.yaml. Drives the reused delete path (feature 003) and the new label path
through `export_service`. Deletion keeps its explicit, scope-gated confirmation; labeling rides
alongside without a separate confirm (FR-015). All access is scoped to a working copy / account.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.api.schemas import ExportPreviewOut, ExportRunOut, StartExportBody
from src.core.db import get_session
from src.services import export_service

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/working-copies/{working_copy_id}/export/preview", response_model=ExportPreviewOut)
def preview_export(
    working_copy_id: uuid.UUID,
    sessionId: uuid.UUID | None = Query(None),
    session: Session = Depends(get_session),
) -> ExportPreviewOut:
    return export_service.preview(session, working_copy_id, session_id=sessionId)


@router.post(
    "/working-copies/{working_copy_id}/export", response_model=ExportRunOut, status_code=201
)
def start_export(
    working_copy_id: uuid.UUID,
    body: StartExportBody | None = None,
    session: Session = Depends(get_session),
) -> ExportRunOut:
    body = body or StartExportBody()
    return export_service.start(session, working_copy_id, session_id=body.sessionId)


@router.get("/export-runs/{export_run_id}", response_model=ExportRunOut)
def get_export_run(
    export_run_id: uuid.UUID, session: Session = Depends(get_session)
) -> ExportRunOut:
    return export_service.get_run(session, export_run_id)


@router.post("/export-runs/{export_run_id}/confirm-delete", response_model=ExportRunOut, status_code=202)
def confirm_export_delete(
    export_run_id: uuid.UUID, session: Session = Depends(get_session)
) -> ExportRunOut:
    return export_service.confirm_delete(session, export_run_id)


@router.post("/export-runs/{export_run_id}/undo-delete", response_model=ExportRunOut, status_code=202)
def undo_export_delete(
    export_run_id: uuid.UUID, session: Session = Depends(get_session)
) -> ExportRunOut:
    return export_service.undo_delete(session, export_run_id)


@router.post("/export-runs/{export_run_id}/undo-label", response_model=ExportRunOut, status_code=202)
def undo_export_label(
    export_run_id: uuid.UUID, session: Session = Depends(get_session)
) -> ExportRunOut:
    return export_service.undo_label(session, export_run_id)
