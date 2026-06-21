"""Validate & Normalize orchestration (feature 006).

One ValidationRun over a Draft's *kept* contacts: auto-apply unambiguous fixes (phone E.164, mobile
type, http→https) as reversible StagedEdits (kind="normalize"), and queue everything uncertain/broken
as ValidationItem rows. Nothing is pushed to Google; the frozen snapshot is never touched (mutations
are on the editable working copy only). Undo reuses the existing staged-edit undo path (feature 003).
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.errors import ConflictError, NotFoundError
from src.models.triage import StagedEdit, TriageDecision, TriageSession
from src.models.validation import ValidationItem, ValidationRun
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service, contact_fields, phone_normalizer, website_checker
from src.services import email_validator_service as email_service

# Google People payload arrays per field kind.
_ARRAY = {"phone": "phoneNumbers", "email": "emailAddresses", "website": "urls"}
_ACTIVE = ("queued", "running")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- run lifecycle ---------------------------------------------------------------------------

def start_run(
    session: Session,
    working_copy_id: uuid.UUID,
    *,
    session_id: uuid.UUID | None = None,
    default_region: str | None = None,
) -> ValidationRun:
    if session.get(WorkingCopy, working_copy_id) is None:
        raise NotFoundError("working copy not found")
    existing = session.scalar(
        select(ValidationRun).where(
            ValidationRun.working_copy_id == working_copy_id,
            ValidationRun.status.in_(_ACTIVE),
        )
    )
    if existing is not None:
        raise ConflictError("a validation run is already in progress for this draft")
    run = ValidationRun(
        working_copy_id=working_copy_id,
        session_id=session_id,
        default_region=(default_region or None),
        status="queued",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: uuid.UUID) -> ValidationRun:
    run = session.get(ValidationRun, run_id)
    if run is None:
        raise NotFoundError("validation run not found")
    return run


def list_runs(session: Session, working_copy_id: uuid.UUID) -> list[ValidationRun]:
    return list(
        session.scalars(
            select(ValidationRun)
            .where(ValidationRun.working_copy_id == working_copy_id)
            .order_by(ValidationRun.created_at.desc())
        )
    )


def pending_count(session: Session, run_id: uuid.UUID) -> int:
    return len(
        session.scalars(
            select(ValidationItem.id).where(
                ValidationItem.validation_run_id == run_id,
                ValidationItem.status == "pending",
            )
        ).all()
    )


# ---- kept set --------------------------------------------------------------------------------

def _kept_contacts(session: Session, run: ValidationRun) -> list[WorkingCopyContact]:
    contacts = list(
        session.scalars(
            select(WorkingCopyContact)
            .where(
                WorkingCopyContact.working_copy_id == run.working_copy_id,
                WorkingCopyContact.status == "active",
            )
            .order_by(WorkingCopyContact.created_at)
        )
    )
    sess_id = run.session_id
    if sess_id is None:
        latest = session.scalar(
            select(TriageSession)
            .where(TriageSession.working_copy_id == run.working_copy_id)
            .order_by(TriageSession.created_at.desc())
        )
        sess_id = latest.id if latest else None
    if sess_id is not None:
        deleted = set(
            session.scalars(
                select(TriageDecision.working_copy_contact_id).where(
                    TriageDecision.session_id == sess_id,
                    TriageDecision.outcome == "delete",
                )
            )
        )
        contacts = [c for c in contacts if c.id not in deleted]
    return contacts


# ---- staging (reversible StagedEdit, kind=normalize) -----------------------------------------

def _stage(
    session: Session, contact: WorkingCopyContact, new_payload: dict, *, action: str, kind: str
) -> StagedEdit:
    edit = StagedEdit(
        working_copy_contact_id=contact.id,
        working_copy_id=contact.working_copy_id,
        kind=kind,
        payload_before=deepcopy(contact.payload),
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
        details={"edit": str(edit.id), "kind": kind},
    )
    return edit


def _queue(
    session: Session,
    run: ValidationRun,
    contact: WorkingCopyContact,
    field_kind: str,
    field_index: int,
    issue_type: str,
    original_value: str,
    *,
    suggested: str | None = None,
) -> None:
    session.add(
        ValidationItem(
            validation_run_id=run.id,
            working_copy_contact_id=contact.id,
            field_kind=field_kind,
            field_index=field_index,
            issue_type=issue_type,
            original_value=original_value,
            suggested_value=suggested,
            status="pending",
        )
    )


def _to_https(value: str) -> str:
    if "://" in value:
        return value.replace("http://", "https://", 1)
    return "https://" + value.lstrip("/")


# ---- the pass ---------------------------------------------------------------------------------

def run_validation_job(session: Session, run_id: uuid.UUID, *, website_check=None) -> ValidationRun:
    website_check = website_check or website_checker.check
    run = get_run(session, run_id)
    run.status = "running"
    run.started_at = _now()
    session.flush()
    region = run.default_region or get_settings().phone_default_region

    checked = auto = queued = 0
    try:
        for contact in _kept_contacts(session, run):
            payload = contact.payload  # original snapshot of values/indices (stable across staging)

            for idx, entry in enumerate(payload.get("phoneNumbers", []) or []):
                value = entry.get("value")
                if not value:
                    continue
                checked += 1
                res = phone_normalizer.analyze(value, region)
                if not res.valid:
                    _queue(session, run, contact, "phone", idx, "invalid_phone", value)
                    queued += 1
                    continue
                if res.e164 and res.e164 != value:
                    np = deepcopy(contact.payload)
                    np["phoneNumbers"][idx]["value"] = res.e164
                    _stage(session, contact, np, action="contact.normalized", kind="normalize")
                    auto += 1
                if not entry.get("type"):
                    if res.is_mobile:
                        np = deepcopy(contact.payload)
                        np["phoneNumbers"][idx]["type"] = "mobile"
                        _stage(session, contact, np, action="contact.normalized", kind="normalize")
                        auto += 1
                    else:
                        _queue(session, run, contact, "phone", idx, "unclear_type", value,
                               suggested=res.e164)
                        queued += 1

            for idx, entry in enumerate(payload.get("emailAddresses", []) or []):
                value = entry.get("value")
                if not value:
                    continue
                checked += 1
                er = email_service.analyze(value)
                if er.issue:
                    _queue(session, run, contact, "email", idx, er.issue, value)
                    queued += 1

            for idx, entry in enumerate(payload.get("urls", []) or []):
                value = entry.get("value")
                if not value:
                    continue
                checked += 1
                wr = website_check(value)
                if wr.status == "unsafe":
                    _queue(session, run, contact, "website", idx, "website_unsafe", value)
                    queued += 1
                elif wr.status == "unreachable":
                    _queue(session, run, contact, "website", idx, "website_unreachable", value)
                    queued += 1
                elif wr.status == "upgrade_https":
                    np = deepcopy(contact.payload)
                    np["urls"][idx]["value"] = _to_https(value)
                    _stage(session, contact, np, action="contact.normalized", kind="normalize")
                    auto += 1

        run.checked_count = checked
        run.auto_applied_count = auto
        run.queued_count = queued
        run.status = "completed"
        run.completed_at = _now()
        session.commit()
    except Exception as exc:  # noqa: BLE001 — mark the run failed and re-raise for the worker log
        session.rollback()
        run = get_run(session, run_id)
        run.status = "failed"
        run.last_error = str(exc)[:500]
        run.completed_at = _now()
        session.commit()
        raise
    session.refresh(run)
    return run


# ---- manual queue ----------------------------------------------------------------------------

def list_items(session: Session, run_id: uuid.UUID, *, status: str = "pending") -> list[ValidationItem]:
    get_run(session, run_id)
    stmt = select(ValidationItem).where(ValidationItem.validation_run_id == run_id)
    if status != "all":
        stmt = stmt.where(ValidationItem.status == status)
    return list(session.scalars(stmt.order_by(ValidationItem.created_at)))


def _require_item(session: Session, item_id: uuid.UUID) -> ValidationItem:
    item = session.get(ValidationItem, item_id)
    if item is None:
        raise NotFoundError("validation item not found")
    return item


def _locate(arr: list[dict], field_index: int, original_value: str) -> int:
    if 0 <= field_index < len(arr) and arr[field_index].get("value") == original_value:
        return field_index
    for i, entry in enumerate(arr):
        if entry.get("value") == original_value:
            return i
    return min(field_index, len(arr) - 1)


def resolve_item(
    session: Session,
    item_id: uuid.UUID,
    *,
    action: str,
    type: str | None = None,
    value: str | None = None,
) -> ValidationItem:
    item = _require_item(session, item_id)
    if item.status != "pending":
        raise ConflictError("item is already resolved or skipped")
    contact = session.get(WorkingCopyContact, item.working_copy_contact_id)
    if contact is None:
        raise NotFoundError("contact not found")

    array_key = _ARRAY[item.field_kind]
    new_payload = deepcopy(contact.payload)
    arr = new_payload.get(array_key) or []
    if not arr:
        raise ConflictError("field no longer present on the contact")
    idx = _locate(arr, item.field_index, item.original_value)

    still_pending = False
    if action == "set_type":
        if not type:
            raise ConflictError("set_type requires a type")
        arr[idx]["type"] = type
    elif action == "edit_value":
        if value is None:
            raise ConflictError("edit_value requires a value")
        arr[idx]["value"] = value
        if item.field_kind == "phone":
            region = (
                get_run(session, item.validation_run_id).default_region
                or get_settings().phone_default_region
            )
            still_pending = not phone_normalizer.analyze(value, region).valid
    elif action == "remove_field":
        del arr[idx]
    else:
        raise ConflictError(f"unknown action: {action}")

    new_payload[array_key] = arr
    edit = _stage(session, contact, new_payload, action="contact.edited", kind="normalize")
    item.staged_edit_id = edit.id
    item.resolution = {"action": action}
    if type is not None:
        item.resolution["type"] = type
    if value is not None:
        item.resolution["value"] = value
        item.original_value = value
    if not still_pending:
        item.status = "resolved"
        item.resolved_at = _now()
    session.commit()
    session.refresh(item)
    return item


def skip_item(session: Session, item_id: uuid.UUID) -> ValidationItem:
    item = _require_item(session, item_id)
    if item.status != "pending":
        raise ConflictError("item is already resolved or skipped")
    item.status = "skipped"
    item.resolved_at = _now()
    session.commit()
    session.refresh(item)
    return item


# ---- serialization helpers (derived fields) --------------------------------------------------

def run_out(session: Session, run: ValidationRun) -> dict:
    return {
        "id": run.id,
        "workingCopyId": run.working_copy_id,
        "sessionId": run.session_id,
        "status": run.status,
        "defaultRegion": run.default_region,
        "checkedCount": run.checked_count,
        "autoAppliedCount": run.auto_applied_count,
        "queuedCount": run.queued_count,
        "pendingCount": pending_count(session, run.id),
        "lastError": run.last_error,
        "createdAt": run.created_at,
        "startedAt": run.started_at,
        "completedAt": run.completed_at,
    }


def item_out(session: Session, item: ValidationItem) -> dict:
    contact = session.get(WorkingCopyContact, item.working_copy_contact_id)
    display = contact_fields.display_name(contact.payload) if contact else None
    return {
        "id": item.id,
        "workingCopyContactId": item.working_copy_contact_id,
        "contactDisplayName": display,
        "fieldKind": item.field_kind,
        "fieldIndex": item.field_index,
        "issueType": item.issue_type,
        "originalValue": item.original_value,
        "suggestedValue": item.suggested_value,
        "status": item.status,
        "stagedEditId": item.staged_edit_id,
        "createdAt": item.created_at,
        "resolvedAt": item.resolved_at,
    }
