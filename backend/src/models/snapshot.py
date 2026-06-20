"""Snapshot (immutable capture), ImportJob (resumable), SnapshotContact (immutable)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, uuid_pk

if TYPE_CHECKING:
    from src.models.account import Account
    from src.models.working_copy import WorkingCopy


class Snapshot(Base):
    __tablename__ = "snapshot"

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    # importing | complete | failed | deleting
    status: Mapped[str] = mapped_column(String(16), default="importing", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="personal_connections", nullable=False)
    contact_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = created_ts()
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship("Account")
    import_job: Mapped["ImportJob"] = relationship(
        back_populates="snapshot", uselist=False, cascade="all, delete-orphan"
    )
    contacts: Mapped[list["SnapshotContact"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    working_copies: Mapped[list["WorkingCopy"]] = relationship(
        "WorkingCopy", back_populates="snapshot"
    )


class ImportJob(Base):
    __tablename__ = "import_job"

    id: Mapped[uuid.UUID] = uuid_pk()
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("snapshot.id", ondelete="CASCADE"), unique=True
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    page_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    snapshot: Mapped[Snapshot] = relationship(back_populates="import_job")


class SnapshotContact(Base):
    __tablename__ = "snapshot_contact"
    __table_args__ = (UniqueConstraint("snapshot_id", "resource_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("snapshot.id", ondelete="CASCADE"), nullable=False
    )
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JsonB, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_at: Mapped[datetime] = created_ts()

    snapshot: Mapped[Snapshot] = relationship(back_populates="contacts")
