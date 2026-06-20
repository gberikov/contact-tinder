"""AuditEntry — append-only record of contact-affecting events (Principle V)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, uuid_pk


class AuditEntry(Base):
    __tablename__ = "audit_entry"

    id: Mapped[uuid.UUID] = uuid_pk()
    occurred_at: Mapped[datetime] = created_ts()
    # snapshot.created | snapshot.deleted | working_copy.created |
    # dedup.run.started | dedup.run.completed | dedup.run.failed |
    # cluster.merged | merge.undone | cluster.dismissed |
    # triage.session.started | triage.session.completed | triage.session.reset |
    # contact.kept | contact.queued_delete | contact.sent_processing |
    # contact.edited | contact.transliterated | edit.undone |
    # delete.batch.previewed | delete.batch.committed | contact.deleted | contact.restored
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="operator", nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_ref: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
