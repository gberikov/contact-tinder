"""WorkingCopy (editable derivative) and WorkingCopyContact (editable)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, JsonB, created_ts, uuid_pk

if TYPE_CHECKING:
    from src.models.snapshot import Snapshot


class WorkingCopy(Base):
    __tablename__ = "working_copy"

    id: Mapped[uuid.UUID] = uuid_pk()
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("snapshot.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # creating | ready
    status: Mapped[str] = mapped_column(String(16), default="creating", nullable=False)
    created_at: Mapped[datetime] = created_ts()

    snapshot: Mapped["Snapshot"] = relationship("Snapshot", back_populates="working_copies")
    contacts: Mapped[list["WorkingCopyContact"]] = relationship(
        back_populates="working_copy", cascade="all, delete-orphan"
    )


class WorkingCopyContact(Base):
    __tablename__ = "working_copy_contact"
    __table_args__ = (Index("ix_wcc_copy_status", "working_copy_id", "status"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    origin_resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonB, nullable=False)
    # active | retired (retired = merged away, reversible via MergeRecord — feature 002)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    working_copy: Mapped[WorkingCopy] = relationship(back_populates="contacts")
