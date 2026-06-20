"""Swipe-triage sessions: open/resume, deck, record/re-decide, undo, summary (feature 003 US1).

The deck is the `active` working_copy_contact survivors in a stable order (D1), computed from current
rows each load so a working-copy change is reflected/surfaced (FR-027). One live decision per contact
(re-decide updates in place; history lives in the audit log, D3). No Google calls here (FR-008).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.triage import ProcessingItem, StagedEdit, TriageDecision, TriageSession
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service, contact_fields, contact_flatten

_OUTCOMES = ("keep", "delete", "process")
_OUTCOME_AUDIT = {
    "keep": "contact.kept",
    "delete": "contact.queued_delete",
    "process": "contact.sent_processing",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_working_copy(session: Session, working_copy_id: uuid.UUID) -> WorkingCopy:
    copy = session.get(WorkingCopy, working_copy_id)
    if copy is None:
        raise NotFoundError("working copy not found")
    return copy


def contact_detail(contact: WorkingCopyContact) -> dict:
    """Display projection (+ full payload for the edit form)."""
    return {
        "displayName": contact_fields.display_name(contact.payload),
        "primaryEmail": contact_fields.primary_email(contact.payload),
        "primaryPhone": contact_fields.primary_phone(contact.payload),
        "organization": contact_flatten.organization(contact.payload),
        "status": contact.status,
        "payload": contact.payload,
    }


def _sort_key(contact: WorkingCopyContact) -> tuple:
    name = contact_fields.display_name(contact.payload)
    # NULLS LAST, then by lowercased name, then id for a total order (D1).
    return (name is None, (name or "").lower(), str(contact.id))


def _active_contacts(session: Session, working_copy_id: uuid.UUID) -> list[WorkingCopyContact]:
    rows = session.scalars(
        select(WorkingCopyContact).where(
            WorkingCopyContact.working_copy_id == working_copy_id,
            WorkingCopyContact.status == "active",
        )
    )
    return sorted(rows, key=_sort_key)


# ---- Sessions --------------------------------------------------------------------------------

def open_session(session: Session, working_copy_id: uuid.UUID) -> tuple[TriageSession, bool]:
    """Return the in-progress session for the working copy, or open a new one. (created flag)."""
    copy = _require_working_copy(session, working_copy_id)
    if copy.status != "ready":
        raise ConflictError("working copy is not ready")

    existing = session.scalar(
        select(TriageSession).where(
            TriageSession.working_copy_id == working_copy_id,
            TriageSession.status == "in_progress",
        )
    )
    if existing is not None:
        return existing, False

    ts = TriageSession(working_copy_id=working_copy_id, status="in_progress")
    session.add(ts)
    try:
        session.flush()
    except IntegrityError:  # partial unique index lost the race (D11)
        session.rollback()
        existing = session.scalar(
            select(TriageSession).where(
                TriageSession.working_copy_id == working_copy_id,
                TriageSession.status == "in_progress",
            )
        )
        if existing is not None:
            return existing, False
        raise
    audit_service.record(
        session,
        action="triage.session.started",
        target_type="triage_session",
        target_id=ts.id,
        source_ref=working_copy_id,
    )
    session.commit()
    return ts, True


def list_sessions(
    session: Session, working_copy_id: uuid.UUID, *, status: str | None = None
) -> list[TriageSession]:
    _require_working_copy(session, working_copy_id)
    stmt = select(TriageSession).where(TriageSession.working_copy_id == working_copy_id)
    if status is not None:
        stmt = stmt.where(TriageSession.status == status)
    return list(session.scalars(stmt.order_by(TriageSession.created_at.desc())))


def get_session(session: Session, session_id: uuid.UUID) -> TriageSession:
    ts = session.get(TriageSession, session_id)
    if ts is None:
        raise NotFoundError("triage session not found")
    return ts


# ---- Deck ------------------------------------------------------------------------------------

def _decided_ids(session: Session, session_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        session.scalars(
            select(TriageDecision.working_copy_contact_id).where(
                TriageDecision.session_id == session_id
            )
        )
    )


def deck(
    session: Session,
    session_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = 10,
) -> tuple[list[WorkingCopyContact], str | None]:
    """Next undecided active contacts in stable order (FR-001/003/005, D1)."""
    ts = get_session(session, session_id)
    decided = _decided_ids(session, session_id)
    undecided = [c for c in _active_contacts(session, ts.working_copy_id) if c.id not in decided]

    start = 0
    if cursor:
        cursor_id = uuid.UUID(cursor)
        for i, c in enumerate(undecided):
            if c.id == cursor_id:
                start = i + 1
                break
    window = undecided[start : start + limit]
    next_cursor = str(window[-1].id) if window and (start + limit) < len(undecided) else None
    return window, next_cursor


# ---- Decisions -------------------------------------------------------------------------------

def set_decision(
    session: Session,
    session_id: uuid.UUID,
    contact_id: uuid.UUID,
    *,
    outcome: str,
    wants_edit: bool = False,
    wants_transliterate: bool = False,
) -> TriageDecision:
    if outcome not in _OUTCOMES:
        raise ConflictError("invalid outcome")
    ts = get_session(session, session_id)

    contact = session.get(WorkingCopyContact, contact_id)
    if (
        contact is None
        or contact.working_copy_id != ts.working_copy_id
        or contact.status != "active"
    ):
        # Not an active survivor of THIS working copy (isolation + FR-027 stale guard).
        raise ConflictError("contact is not an active survivor of this working copy")

    decision = session.scalar(
        select(TriageDecision).where(
            TriageDecision.session_id == session_id,
            TriageDecision.working_copy_contact_id == contact_id,
        )
    )
    if decision is None:
        decision = TriageDecision(
            session_id=session_id, working_copy_contact_id=contact_id, outcome=outcome
        )
        session.add(decision)
    else:
        decision.outcome = outcome
        decision.decided_at = _now()

    item = session.scalar(
        select(ProcessingItem).where(
            ProcessingItem.session_id == session_id,
            ProcessingItem.working_copy_contact_id == contact_id,
        )
    )
    if outcome == "process":
        if item is None:
            item = ProcessingItem(
                session_id=session_id,
                working_copy_contact_id=contact_id,
                wants_edit=wants_edit,
                wants_transliterate=wants_transliterate,
            )
            session.add(item)
        else:
            item.wants_edit = wants_edit or item.wants_edit
            item.wants_transliterate = wants_transliterate or item.wants_transliterate
            item.status = "pending"
            item.resolved_at = None
    elif item is not None:
        # Re-decided away from processing — drop the queue item.
        session.delete(item)

    session.flush()
    audit_service.record(
        session,
        action=_OUTCOME_AUDIT[outcome],
        target_type="working_copy_contact",
        target_id=contact_id,
        source_ref=session_id,
    )
    _refresh_completion(session, ts)
    session.commit()
    return decision


def undo_decision(session: Session, session_id: uuid.UUID, contact_id: uuid.UUID) -> None:
    ts = get_session(session, session_id)
    decision = session.scalar(
        select(TriageDecision).where(
            TriageDecision.session_id == session_id,
            TriageDecision.working_copy_contact_id == contact_id,
        )
    )
    if decision is None:
        raise NotFoundError("decision not found")
    session.delete(decision)
    item = session.scalar(
        select(ProcessingItem).where(
            ProcessingItem.session_id == session_id,
            ProcessingItem.working_copy_contact_id == contact_id,
        )
    )
    if item is not None:
        session.delete(item)
    session.flush()
    _refresh_completion(session, ts)
    session.commit()


def reset_session(session: Session, session_id: uuid.UUID) -> TriageSession:
    """Roll the session back to its initial stage — start triage over.

    Clears all decisions and processing items for the session and reverts active staged edits
    (transliterations/edits) on the working copy, restoring pristine contact payloads. Already
    committed Google deletions are NOT reversed here (each delete batch has its own undo path).
    """
    ts = get_session(session, session_id)

    # Revert content changes so cards return to their original state.
    edits = session.scalars(
        select(StagedEdit).where(
            StagedEdit.working_copy_id == ts.working_copy_id, StagedEdit.status == "active"
        )
    )
    reverted = 0
    for edit in edits:
        contact = session.get(WorkingCopyContact, edit.working_copy_contact_id)
        if contact is not None:
            contact.payload = dict(edit.payload_before)
        edit.status = "undone"
        edit.undone_at = _now()
        reverted += 1

    # Drop the triage classification (decisions) and the processing queue.
    for item in session.scalars(
        select(ProcessingItem).where(ProcessingItem.session_id == session_id)
    ):
        session.delete(item)
    for decision in session.scalars(
        select(TriageDecision).where(TriageDecision.session_id == session_id)
    ):
        session.delete(decision)

    ts.status = "in_progress"
    ts.finished_at = None
    session.flush()
    audit_service.record(
        session,
        action="triage.session.reset",
        target_type="triage_session",
        target_id=ts.id,
        source_ref=ts.working_copy_id,
        details={"reverted_edits": reverted},
    )
    session.commit()
    return ts


# ---- Summary / completion --------------------------------------------------------------------

def summary(session: Session, ts: TriageSession) -> dict:
    active = _active_contacts(session, ts.working_copy_id)
    total = len(active)
    active_ids = {c.id for c in active}

    decisions = list(
        session.scalars(
            select(TriageDecision).where(TriageDecision.session_id == ts.id)
        )
    )
    # Only count decisions for contacts still active (FR-027: stale ones excluded).
    counts = {"keep": 0, "delete": 0, "process": 0}
    decided_ids = set()
    for d in decisions:
        if d.working_copy_contact_id in active_ids:
            counts[d.outcome] = counts.get(d.outcome, 0) + 1
            decided_ids.add(d.working_copy_contact_id)
    decided = len(decided_ids)
    return {
        "total": total,
        "decided": decided,
        "keep": counts["keep"],
        "delete": counts["delete"],
        "processing": counts["process"],
        "remaining": total - decided,
    }


def _pending_processing(session: Session, session_id: uuid.UUID) -> int:
    return len(
        list(
            session.scalars(
                select(ProcessingItem.id).where(
                    ProcessingItem.session_id == session_id,
                    ProcessingItem.status == "pending",
                )
            )
        )
    )


def _refresh_completion(session: Session, ts: TriageSession) -> None:
    """Mark complete when every active contact is decided and no pending processing remains (D4)."""
    s = summary(session, ts)
    pending = _pending_processing(session, ts.id)
    should_complete = s["total"] > 0 and s["remaining"] == 0 and pending == 0
    if should_complete and ts.status != "complete":
        ts.status = "complete"
        ts.finished_at = _now()
        session.flush()
        audit_service.record(
            session,
            action="triage.session.completed",
            target_type="triage_session",
            target_id=ts.id,
            source_ref=ts.working_copy_id,
            details={k: s[k] for k in ("keep", "delete", "processing", "total")},
        )
    elif not should_complete and ts.status == "complete":
        ts.status = "in_progress"
        ts.finished_at = None
        session.flush()
