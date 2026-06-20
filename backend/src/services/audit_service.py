"""Append-only audit log writer (Constitution Principle V, FR-019/FR-023)."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from src.models.audit import AuditEntry


def record(
    session: Session,
    *,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    source_ref: uuid.UUID | None = None,
    details: dict | None = None,
) -> AuditEntry:
    """Insert an audit entry. `details` MUST never contain tokens/secrets (Principle V)."""
    entry = AuditEntry(
        action=action,
        target_type=target_type,
        target_id=target_id,
        source_ref=source_ref,
        details=details,
    )
    session.add(entry)
    session.flush()
    return entry
