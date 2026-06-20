"""Deduplication entities (feature 002-zingg-dedup).

DedupRun → DuplicateCluster → ClusterMember (→ WorkingCopyContact), plus MergeRecord for
reversible survivor-based merges. All state is local to a working copy; the snapshot is never
touched. Cross-dialect (Postgres + SQLite for tests): arrays are stored as JsonB lists.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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

from src.models.base import Base, JsonB, created_ts, uuid_pk

# Run lifecycle / resolution status string sets (kept as strings for cross-dialect simplicity).
RUN_STATES = ("queued", "running", "completed", "failed")
CLUSTER_STATES = ("pending", "merged", "dismissed", "superseded")


class DedupRun(Base):
    __tablename__ = "dedup_run"
    __table_args__ = (
        # FR-007: at most one active (queued/running) run per working copy.
        Index(
            "uq_dedup_run_active_per_copy",
            "working_copy_id",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
            postgresql_where=text("status IN ('queued','running')"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_floor: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cluster_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    params: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_ts()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clusters: Mapped[list["DuplicateCluster"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class DuplicateCluster(Base):
    __tablename__ = "duplicate_cluster"
    __table_args__ = (
        Index("ix_cluster_run_status_conf", "dedup_run_id", "status", "confidence"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dedup_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dedup_run.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    z_cluster_key: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # z_maxScore
    min_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # z_minScore
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending | merged | dismissed | superseded
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_ts()

    run: Mapped[DedupRun] = relationship(back_populates="clusters")
    members: Mapped[list["ClusterMember"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )
    merge_record: Mapped["MergeRecord | None"] = relationship(
        back_populates="cluster", uselist=False, cascade="all, delete-orphan"
    )


class ClusterMember(Base):
    __tablename__ = "cluster_member"
    __table_args__ = (
        UniqueConstraint("cluster_id", "working_copy_contact_id"),
        Index("ix_cluster_member_wcc", "working_copy_contact_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("duplicate_cluster.id", ondelete="CASCADE"), nullable=False
    )
    working_copy_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_survivor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cluster: Mapped[DuplicateCluster] = relationship(back_populates="members")


class MergeRecord(Base):
    __tablename__ = "merge_record"

    id: Mapped[uuid.UUID] = uuid_pk()
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("duplicate_cluster.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    working_copy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False
    )
    survivor_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_copy_contact.id"), nullable=False
    )
    survivor_payload_before: Mapped[dict] = mapped_column(JsonB, nullable=False)
    merged_payload: Mapped[dict] = mapped_column(JsonB, nullable=False)
    # list[str] of retired working_copy_contact ids (JsonB for cross-dialect; no ARRAY on SQLite)
    retired_member_ids: Mapped[list] = mapped_column(JsonB, nullable=False)
    # active | undone
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped[DuplicateCluster] = relationship(back_populates="merge_record")
