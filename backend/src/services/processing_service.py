"""Post-swipe processing queue: edit a card, accept a Cyrillic transliteration, mark done, undo.

Edits/transliterations are staged against the working copy as reversible StagedEdit rows (D6) and are
NOT pushed to Google here (D7). Marking an item done defaults the contact's decision to keep (D4).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.triage import ProcessingItem, StagedEdit, TriageDecision, TriageSession
from src.models.working_copy import WorkingCopyContact
from src.services import audit_service, transliteration, triage_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_contact(session: Session, contact_id: uuid.UUID) -> WorkingCopyContact:
    contact = session.get(WorkingCopyContact, contact_id)
    if contact is None:
        raise NotFoundError("contact not found")
    return contact


def list_processing(
    session: Session, session_id: uuid.UUID, *, status: str = "pending"
) -> list[ProcessingItem]:
    triage_service.get_session(session, session_id)
    return list(
        session.scalars(
            select(ProcessingItem)
            .where(ProcessingItem.session_id == session_id, ProcessingItem.status == status)
            .order_by(ProcessingItem.created_at)
        )
    )


def get_processing_item(session: Session, item_id: uuid.UUID) -> ProcessingItem:
    item = session.get(ProcessingItem, item_id)
    if item is None:
        raise NotFoundError("processing item not found")
    return item


def transliteration_suggestion(session: Session, contact_id: uuid.UUID) -> dict:
    contact = _require_contact(session, contact_id)
    return transliteration.suggest_for_payload(contact.payload)


def _stage(
    session: Session, contact: WorkingCopyContact, *, kind: str, new_payload: dict, action: str
) -> StagedEdit:
    edit = StagedEdit(
        working_copy_contact_id=contact.id,
        working_copy_id=contact.working_copy_id,
        kind=kind,
        payload_before=dict(contact.payload),
        payload_after=new_payload,
    )
    session.add(edit)
    contact.payload = new_payload
    session.flush()
    audit_service.record(
        session,
        action=action,
        target_type="working_copy_contact",
        target_id=contact.id,
        details={"kind": kind, "edit": str(edit.id)},
    )
    session.commit()
    return edit


def apply_edit(session: Session, contact_id: uuid.UUID, payload: dict) -> StagedEdit:
    contact = _require_contact(session, contact_id)
    return _stage(session, contact, kind="edit", new_payload=payload, action="contact.edited")


def accept_transliteration(
    session: Session, contact_id: uuid.UUID, fields: dict[str, str]
) -> StagedEdit:
    contact = _require_contact(session, contact_id)
    if not fields:
        raise ConflictError("no transliteration fields provided")
    new_payload = transliteration.apply_to_payload(contact.payload, fields)
    return _stage(
        session, contact, kind="transliterate", new_payload=new_payload,
        action="contact.transliterated",
    )


def complete_processing_item(session: Session, item_id: uuid.UUID) -> ProcessingItem:
    item = get_processing_item(session, item_id)
    item.status = "done"
    item.resolved_at = _now()

    # Terminal disposition defaults to keep (D4), unless the operator already re-decided.
    decision = session.scalar(
        select(TriageDecision).where(
            TriageDecision.session_id == item.session_id,
            TriageDecision.working_copy_contact_id == item.working_copy_contact_id,
        )
    )
    if decision is not None and decision.outcome == "process":
        decision.outcome = "keep"
        decision.decided_at = _now()
        audit_service.record(
            session,
            action="contact.kept",
            target_type="working_copy_contact",
            target_id=item.working_copy_contact_id,
            source_ref=item.session_id,
        )
    session.flush()

    ts = session.get(TriageSession, item.session_id)
    if ts is not None:
        triage_service._refresh_completion(session, ts)
    session.commit()
    return item


def undo_staged_edit(session: Session, edit_id: uuid.UUID) -> StagedEdit:
    edit = session.get(StagedEdit, edit_id)
    if edit is None:
        raise NotFoundError("staged edit not found")
    if edit.status != "active":
        raise ConflictError("edit already undone")
    contact = session.get(WorkingCopyContact, edit.working_copy_contact_id)
    if contact is not None:
        contact.payload = dict(edit.payload_before)
    edit.status = "undone"
    edit.undone_at = _now()
    session.flush()
    audit_service.record(
        session,
        action="edit.undone",
        target_type="working_copy_contact",
        target_id=edit.working_copy_contact_id,
        details={"edit": str(edit.id)},
    )
    session.commit()
    return edit
