"""Swipe-triage router (feature 003): sessions/deck/decisions, processing queue + edits, delete batch.

Mirrors contracts/openapi.yaml. Swiping writes nothing to Google; the delete batch is the only path
that reaches Google, gated by a dry-run preview, a per-contact snapshot, and an explicit confirmation
that requires the contacts write scope. All access is scoped to a working copy.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import (
    ContactDetailOut,
    CreateDeleteBatchBody,
    DeckCardOut,
    DeckPageOut,
    DecisionRequest,
    DeleteBatchOut,
    DeletionRecordOut,
    EditRequest,
    ProcessingItemOut,
    SessionSummaryOut,
    StagedEditOut,
    TransliterationAcceptRequest,
    TransliterationSuggestionOut,
    TriageDecisionOut,
    TriageSessionOut,
)
from src.core.db import get_session
from src.models.triage import DeletionRecord, ProcessingItem
from src.models.working_copy import WorkingCopyContact
from src.services import (
    contact_fields,
    contact_flatten,
    delete_batch_service,
    processing_service,
    transliteration,
    triage_service,
)

router = APIRouter(prefix="/api", tags=["triage"])


# ---- Builders --------------------------------------------------------------------------------

def _session_out(session: Session, ts) -> TriageSessionOut:
    return TriageSessionOut(
        id=ts.id,
        workingCopyId=ts.working_copy_id,
        dedupRunId=ts.dedup_run_id,
        status=ts.status,
        createdAt=ts.created_at,
        finishedAt=ts.finished_at,
        summary=SessionSummaryOut(**triage_service.summary(session, ts)),
    )


def _contact_detail(contact: WorkingCopyContact) -> ContactDetailOut:
    return ContactDetailOut(**triage_service.contact_detail(contact))


def _detail_from_payload(payload: dict, status: str) -> ContactDetailOut:
    return ContactDetailOut(
        displayName=contact_fields.display_name(payload),
        primaryEmail=contact_fields.primary_email(payload),
        primaryPhone=contact_fields.primary_phone(payload),
        organization=contact_flatten.organization(payload),
        status=status,
        payload=payload,
    )


def _decision_out(session: Session, decision) -> TriageDecisionOut:
    item_id = None
    if decision.outcome == "process":
        item = session.scalar(
            select(ProcessingItem).where(
                ProcessingItem.session_id == decision.session_id,
                ProcessingItem.working_copy_contact_id == decision.working_copy_contact_id,
            )
        )
        item_id = item.id if item else None
    return TriageDecisionOut(
        id=decision.id,
        sessionId=decision.session_id,
        workingCopyContactId=decision.working_copy_contact_id,
        outcome=decision.outcome,
        decidedAt=decision.decided_at,
        processingItemId=item_id,
    )


def _processing_out(session: Session, item: ProcessingItem) -> ProcessingItemOut:
    contact = session.get(WorkingCopyContact, item.working_copy_contact_id)
    suggestion = None
    if contact is not None and item.wants_transliterate:
        suggestion = TransliterationSuggestionOut(
            **transliteration.suggest_for_payload(contact.payload)
        )
    return ProcessingItemOut(
        id=item.id,
        sessionId=item.session_id,
        workingCopyContactId=item.working_copy_contact_id,
        wantsEdit=item.wants_edit,
        wantsTransliterate=item.wants_transliterate,
        status=item.status,
        contact=_contact_detail(contact) if contact else _detail_from_payload({}, "retired"),
        transliterationSuggestion=suggestion,
    )


def _batch_out(batch) -> DeleteBatchOut:
    return DeleteBatchOut(
        id=batch.id,
        workingCopyId=batch.working_copy_id,
        sessionId=batch.session_id,
        accountId=batch.account_id,
        status=batch.status,
        totalCount=batch.total_count,
        deletedCount=batch.deleted_count,
        failedCount=batch.failed_count,
        lastError=batch.last_error,
        createdAt=batch.created_at,
        previewedAt=batch.previewed_at,
        committedAt=batch.committed_at,
        undoneAt=batch.undone_at,
    )


def _record_out(session: Session, rec: DeletionRecord) -> DeletionRecordOut:
    contact = (
        session.get(WorkingCopyContact, rec.working_copy_contact_id)
        if rec.working_copy_contact_id
        else None
    )
    detail = _contact_detail(contact) if contact else _detail_from_payload(rec.payload_before, "retired")
    return DeletionRecordOut(
        id=rec.id,
        workingCopyContactId=rec.working_copy_contact_id,
        status=rec.status,
        contact=detail,
        error=rec.error,
    )


# ---- Sessions & deck (US1) ------------------------------------------------------------------

@router.post("/working-copies/{working_copy_id}/triage-sessions", response_model=TriageSessionOut)
def open_triage_session(
    working_copy_id: uuid.UUID, response: Response, session: Session = Depends(get_session)
) -> TriageSessionOut:
    ts, created = triage_service.open_session(session, working_copy_id)
    response.status_code = 201 if created else 200
    return _session_out(session, ts)


@router.get(
    "/working-copies/{working_copy_id}/triage-sessions", response_model=list[TriageSessionOut]
)
def list_triage_sessions(
    working_copy_id: uuid.UUID,
    status: str | None = Query(None),
    session: Session = Depends(get_session),
) -> list[TriageSessionOut]:
    return [
        _session_out(session, ts)
        for ts in triage_service.list_sessions(session, working_copy_id, status=status)
    ]


@router.get("/triage-sessions/{session_id}", response_model=TriageSessionOut)
def get_triage_session(
    session_id: uuid.UUID, session: Session = Depends(get_session)
) -> TriageSessionOut:
    return _session_out(session, triage_service.get_session(session, session_id))


@router.post("/triage-sessions/{session_id}/reset", response_model=TriageSessionOut)
def reset_triage_session(
    session_id: uuid.UUID, session: Session = Depends(get_session)
) -> TriageSessionOut:
    return _session_out(session, triage_service.reset_session(session, session_id))


@router.get("/triage-sessions/{session_id}/deck", response_model=DeckPageOut)
def get_deck(
    session_id: uuid.UUID,
    cursor: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> DeckPageOut:
    cards, next_cursor = triage_service.deck(session, session_id, cursor=cursor, limit=limit)
    return DeckPageOut(
        cards=[
            DeckCardOut(workingCopyContactId=c.id, contact=_contact_detail(c), currentOutcome=None)
            for c in cards
        ],
        nextCursor=next_cursor,
    )


@router.put(
    "/triage-sessions/{session_id}/decisions/{contact_id}", response_model=TriageDecisionOut
)
def set_decision(
    session_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: DecisionRequest,
    session: Session = Depends(get_session),
) -> TriageDecisionOut:
    decision = triage_service.set_decision(
        session,
        session_id,
        contact_id,
        outcome=body.outcome,
        wants_edit=body.wantsEdit,
        wants_transliterate=body.wantsTransliterate,
    )
    return _decision_out(session, decision)


@router.delete("/triage-sessions/{session_id}/decisions/{contact_id}", status_code=204)
def undo_decision(
    session_id: uuid.UUID, contact_id: uuid.UUID, session: Session = Depends(get_session)
) -> Response:
    triage_service.undo_decision(session, session_id, contact_id)
    return Response(status_code=204)


# ---- Processing queue (US2) -----------------------------------------------------------------

@router.get("/triage-sessions/{session_id}/processing", response_model=list[ProcessingItemOut])
def list_processing(
    session_id: uuid.UUID,
    status: str = Query("pending"),
    session: Session = Depends(get_session),
) -> list[ProcessingItemOut]:
    return [
        _processing_out(session, item)
        for item in processing_service.list_processing(session, session_id, status=status)
    ]


@router.get("/processing-items/{item_id}", response_model=ProcessingItemOut)
def get_processing_item(
    item_id: uuid.UUID, session: Session = Depends(get_session)
) -> ProcessingItemOut:
    return _processing_out(session, processing_service.get_processing_item(session, item_id))


@router.post("/processing-items/{item_id}/done", response_model=ProcessingItemOut)
def complete_processing_item(
    item_id: uuid.UUID, session: Session = Depends(get_session)
) -> ProcessingItemOut:
    return _processing_out(
        session, processing_service.complete_processing_item(session, item_id)
    )


@router.get(
    "/working-copy-contacts/{contact_id}/transliteration-suggestion",
    response_model=TransliterationSuggestionOut,
)
def get_transliteration_suggestion(
    contact_id: uuid.UUID, session: Session = Depends(get_session)
) -> TransliterationSuggestionOut:
    return TransliterationSuggestionOut(
        **processing_service.transliteration_suggestion(session, contact_id)
    )


@router.put("/working-copy-contacts/{contact_id}/edits", response_model=StagedEditOut)
def apply_edit(
    contact_id: uuid.UUID, body: EditRequest, session: Session = Depends(get_session)
) -> StagedEditOut:
    edit = processing_service.apply_edit(session, contact_id, body.payload)
    return _staged_edit_out(edit)


@router.post("/working-copy-contacts/{contact_id}/transliteration", response_model=StagedEditOut)
def accept_transliteration(
    contact_id: uuid.UUID,
    body: TransliterationAcceptRequest,
    session: Session = Depends(get_session),
) -> StagedEditOut:
    edit = processing_service.accept_transliteration(session, contact_id, body.fields)
    return _staged_edit_out(edit)


@router.post("/staged-edits/{edit_id}/undo", response_model=StagedEditOut)
def undo_staged_edit(
    edit_id: uuid.UUID, session: Session = Depends(get_session)
) -> StagedEditOut:
    return _staged_edit_out(processing_service.undo_staged_edit(session, edit_id))


def _staged_edit_out(edit) -> StagedEditOut:
    return StagedEditOut(
        id=edit.id,
        workingCopyContactId=edit.working_copy_contact_id,
        kind=edit.kind,
        status=edit.status,
        createdAt=edit.created_at,
        undoneAt=edit.undone_at,
    )


# ---- Delete batch (US3) ---------------------------------------------------------------------

@router.post(
    "/working-copies/{working_copy_id}/delete-batches",
    response_model=DeleteBatchOut,
    status_code=201,
)
def create_delete_batch(
    working_copy_id: uuid.UUID,
    body: CreateDeleteBatchBody | None = None,
    session: Session = Depends(get_session),
) -> DeleteBatchOut:
    body = body or CreateDeleteBatchBody()
    batch = delete_batch_service.create_batch(session, working_copy_id, session_id=body.sessionId)
    return _batch_out(batch)


@router.get("/delete-batches/{batch_id}", response_model=DeleteBatchOut)
def get_delete_batch(
    batch_id: uuid.UUID, session: Session = Depends(get_session)
) -> DeleteBatchOut:
    return _batch_out(delete_batch_service.get_batch(session, batch_id))


@router.get("/delete-batches/{batch_id}/preview", response_model=list[DeletionRecordOut])
def preview_delete_batch(
    batch_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[DeletionRecordOut]:
    return [_record_out(session, r) for r in delete_batch_service.preview(session, batch_id)]


@router.post("/delete-batches/{batch_id}/confirm", response_model=DeleteBatchOut, status_code=202)
def confirm_delete_batch(
    batch_id: uuid.UUID, session: Session = Depends(get_session)
) -> DeleteBatchOut:
    return _batch_out(delete_batch_service.confirm(session, batch_id))


@router.post("/delete-batches/{batch_id}/undo", response_model=DeleteBatchOut, status_code=202)
def undo_delete_batch(
    batch_id: uuid.UUID, session: Session = Depends(get_session)
) -> DeleteBatchOut:
    return _batch_out(delete_batch_service.request_undo(session, batch_id))
