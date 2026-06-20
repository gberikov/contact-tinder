"""Export-to-Google entities (feature 004-google-contacts-export).

An ExportRun orchestrates the (reused) DeleteBatch from feature 003 and a NEW LabelBatch that tags the
Processing-Queue survivors with a `Process` Google contact group. LabelBatch → LabelAssignment mirror
DeleteBatch → DeletionRecord (research D3): idempotent, reversible, `404 → skipped_absent`. ContactLabel
caches the resolved `Process` group resourceName per account so re-runs reuse it (research D5). The delete
half persists nothing new here — it drives the existing tables in models/triage.py. No existing table is
altered. Cross-dialect (Postgres + SQLite for tests): payloads/results stored as JsonB.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, uuid_pk

# Status string sets (kept as strings for cross-dialect simplicity, like feature 003).
EXPORT_RUN_STATES = ("previewing", "running", "completed", "failed")
LABEL_BATCH_STATES = ("staged", "labeling", "committed", "failed", "unlabeling", "undone")
LABEL_ASSIGNMENT_STATES = ("pending", "labeled", "skipped_absent", "failed", "removed")


class ExportRun(Base):
    __tablename__ = "export_run"
    __table_args__ = (
        Index("ix_export_run_copy_status", "working_copy_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("triage_session.id", ondelete="SET NULL"), nullable=True
    )
    delete_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("delete_batch.id", ondelete="SET NULL"), nullable=True
    )
    label_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("label_batch.id", ondelete="SET NULL"), nullable=True
    )
    # previewing | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), default="previewing", nullable=False)
    # Active survivors with no terminal decision — warned & excluded (FR-017a).
    undecided_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = created_ts()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LabelBatch(Base):
    __tablename__ = "label_batch"
    __table_args__ = (
        Index("ix_label_batch_copy_status", "working_copy_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("triage_session.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    contact_label_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contact_label.id", ondelete="SET NULL"), nullable=True
    )
    # staged | labeling | committed | failed | unlabeling | undone
    status: Mapped[str] = mapped_column(String(16), default="staged", nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    labeled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # redacted (FR-023)
    created_at: Mapped[datetime] = created_ts()
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignments: Mapped[list["LabelAssignment"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class LabelAssignment(Base):
    __tablename__ = "label_assignment"
    __table_args__ = (
        UniqueConstraint("label_batch_id", "origin_resource_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    label_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("label_batch.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy_contact.id", ondelete="SET NULL"), nullable=True
    )
    origin_resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # pending | labeled | skipped_absent | failed | removed
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    google_result: Mapped[dict | None] = mapped_column(JsonB, nullable=True)  # redacted
    error: Mapped[str | None] = mapped_column(Text, nullable=True)  # redacted (FR-023)
    created_at: Mapped[datetime] = created_ts()
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[LabelBatch] = relationship(back_populates="assignments")


class ContactLabel(Base):
    """The `Process` contact group resolved/created once per account (research D5)."""

    __tablename__ = "contact_label"
    __table_args__ = (
        UniqueConstraint("account_id", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), default="Process", nullable=False)
    group_resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = created_ts()
