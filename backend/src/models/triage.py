"""Swipe-triage entities (feature 003-tinder-swipe-triage).

TriageSession → TriageDecision / ProcessingItem over the `active` working_copy_contact survivors,
StagedEdit for reversible card edits / transliterations, and DeleteBatch → DeletionRecord for the
snapshot-protected, undoable delete-to-Google flow. All state is local to a working copy; the
immutable snapshot is never touched. Cross-dialect (Postgres + SQLite for tests): arrays/payloads
are stored as JsonB.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, utcnow, uuid_pk

# Status / outcome string sets (kept as strings for cross-dialect simplicity).
SESSION_STATES = ("in_progress", "complete")
OUTCOMES = ("keep", "delete", "process")
PROCESSING_STATES = ("pending", "done")
EDIT_KINDS = ("edit", "transliterate", "normalize")  # "normalize" = feature 006 Tidy auto-fix
EDIT_STATES = ("active", "undone")
BATCH_STATES = ("staged", "previewed", "committing", "committed", "failed", "undoing", "undone")
DELETION_STATES = ("pending", "deleted", "skipped_absent", "failed", "restored")


class TriageSession(Base):
    __tablename__ = "triage_session"
    __table_args__ = (
        # D11: at most one in-progress session per working copy.
        Index(
            "uq_triage_session_active_per_copy",
            "working_copy_id",
            unique=True,
            sqlite_where=text("status = 'in_progress'"),
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    dedup_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dedup_run.id", ondelete="SET NULL"), nullable=True
    )
    # in_progress | complete
    status: Mapped[str] = mapped_column(String(16), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    decisions: Mapped[list["TriageDecision"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    processing_items: Mapped[list["ProcessingItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class TriageDecision(Base):
    __tablename__ = "triage_decision"
    __table_args__ = (
        UniqueConstraint("session_id", "working_copy_contact_id"),
        Index("ix_triage_decision_session_outcome", "session_id", "outcome"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("triage_session.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
        nullable=False,
    )
    # keep | delete | process  (latest decision wins — row updated in place, FR-006)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    session: Mapped[TriageSession] = relationship(back_populates="decisions")


class ProcessingItem(Base):
    __tablename__ = "processing_item"
    __table_args__ = (
        UniqueConstraint("session_id", "working_copy_contact_id"),
        Index("ix_processing_item_session_status", "session_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("triage_session.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
        nullable=False,
    )
    wants_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wants_transliterate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # pending | done
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[TriageSession] = relationship(back_populates="processing_items")


class StagedEdit(Base):
    __tablename__ = "staged_edit"
    __table_args__ = (
        Index("ix_staged_edit_wcc_status", "working_copy_contact_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
        nullable=False,
    )
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    # edit | transliterate | normalize (normalize = feature 006 Tidy auto-fix / queue resolution)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_before: Mapped[dict] = mapped_column(JsonB, nullable=False)
    payload_after: Mapped[dict] = mapped_column(JsonB, nullable=False)
    # active | undone
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeleteBatch(Base):
    __tablename__ = "delete_batch"
    __table_args__ = (
        Index("ix_delete_batch_copy_status", "working_copy_id", "status"),
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
    # staged | previewed | committing | committed | failed | undone
    status: Mapped[str] = mapped_column(String(16), default="staged", nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_ts()
    previewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    records: Mapped[list["DeletionRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class DeletionRecord(Base):
    __tablename__ = "deletion_record"
    __table_args__ = (
        UniqueConstraint("delete_batch_id", "origin_resource_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    delete_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("delete_batch.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("working_copy_contact.id", ondelete="SET NULL"),
        nullable=True,
    )
    origin_resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_before: Mapped[dict] = mapped_column(JsonB, nullable=False)
    # pending | deleted | skipped_absent | failed | restored
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    google_result: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    restored_resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_ts()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[DeleteBatch] = relationship(back_populates="records")
