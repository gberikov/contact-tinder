"""Validate & Normalize entities (feature 006-validate-normalize).

ValidationRun → ValidationItem over a Draft's *kept* contacts (those not marked delete in Review).
Auto-fixes (phone E.164, mobile type, http→https) and queue resolutions are reversible StagedEdit
rows (kind="normalize"/"edit", feature 003) — this module persists only the run + the manual queue.
No Google write, no existing table altered. Cross-dialect (Postgres + SQLite): JSON via JsonB.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, uuid_pk

# Status / classification string sets (kept as strings for cross-dialect simplicity, like 002–004).
VALIDATION_RUN_STATES = ("queued", "running", "completed", "failed")
FIELD_KINDS = ("phone", "email", "website")
ISSUE_TYPES = (
    "invalid_phone",        # phone unparseable / not valid for the active region
    "unclear_type",         # valid phone, missing type, not confidently mobile
    "invalid_email",        # email syntactically invalid
    "dead_email_domain",    # email domain has no MX record
    "website_unreachable",  # transport-level failure (DNS/connect/TLS/timeout)
    "website_unsafe",       # SSRF guard: resolves to a non-public address — never fetched
)
VALIDATION_ITEM_STATES = ("pending", "resolved", "skipped")


class ValidationRun(Base):
    __tablename__ = "validation_run"
    __table_args__ = (
        Index("ix_validation_run_copy_status", "working_copy_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("triage_session.id", ondelete="SET NULL"), nullable=True
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    # ISO-3166 alpha-2 used to parse national-format phones (research D2); +E.164 ignores it.
    default_region: Mapped[str | None] = mapped_column(String(2), nullable=True)
    checked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    auto_applied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # redacted (Principle V)
    created_at: Mapped[datetime] = created_ts()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["ValidationItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ValidationItem(Base):
    __tablename__ = "validation_item"
    __table_args__ = (
        Index("ix_validation_item_run_status", "validation_run_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    validation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("validation_run.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy_contact.id", ondelete="CASCADE"), nullable=False
    )
    # phone | email | website
    field_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    # position within that field's array in the payload (locates the value)
    field_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # one of ISSUE_TYPES
    issue_type: Mapped[str] = mapped_column(String(24), nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | resolved | skipped
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    resolution: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    staged_edit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staged_edit.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[ValidationRun] = relationship(back_populates="items")
