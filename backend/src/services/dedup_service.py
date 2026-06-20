"""Dedup run lifecycle: create/list/get runs and ingest engine output into clusters.

Pure of the worker loop: `run_dedup_job` is callable directly with an injected `DedupEngine`, so
ingestion/supersede/finalize are testable without Spark (FakeDedupEngine) — Constitution IV.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.errors import ConflictError, NotFoundError
from src.integrations.dedup_engine import DedupEngine, MatchRow
from src.models.dedup import ClusterMember, DedupRun, DuplicateCluster
from src.models.working_copy import WorkingCopy, WorkingCopyContact
from src.services import audit_service, contact_flatten

_ACTIVE_RUN_STATES = ("queued", "running")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _has_active_run(session: Session, working_copy_id: uuid.UUID) -> bool:
    return bool(
        session.scalar(
            select(DedupRun.id).where(
                DedupRun.working_copy_id == working_copy_id,
                DedupRun.status.in_(_ACTIVE_RUN_STATES),
            )
        )
    )


def create_run(session: Session, working_copy_id: uuid.UUID) -> DedupRun:
    """Enqueue a dedup run for a ready working copy (FR-001, FR-007)."""
    copy = session.get(WorkingCopy, working_copy_id)
    if copy is None:
        raise NotFoundError("working copy not found")
    if copy.status != "ready":
        raise ConflictError("working copy is not ready")
    if _has_active_run(session, working_copy_id):
        raise ConflictError("a deduplication run is already active for this working copy")

    settings = get_settings()
    run = DedupRun(
        working_copy_id=working_copy_id,
        status="queued",
        model_version=settings.dedup_model_version,
        confidence_floor=settings.dedup_confidence_floor,
        params={"engine": settings.dedup_engine, "num_partitions": settings.dedup_num_partitions},
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:  # partial unique index lost the race (FR-007)
        session.rollback()
        raise ConflictError(
            "a deduplication run is already active for this working copy"
        ) from exc

    audit_service.record(
        session,
        action="dedup.run.started",
        target_type="dedup_run",
        target_id=run.id,
        source_ref=working_copy_id,
        details={"model_version": run.model_version},
    )
    session.commit()
    return run


def list_runs(session: Session, working_copy_id: uuid.UUID) -> list[DedupRun]:
    if session.get(WorkingCopy, working_copy_id) is None:
        raise NotFoundError("working copy not found")
    return list(
        session.scalars(
            select(DedupRun)
            .where(DedupRun.working_copy_id == working_copy_id)
            .order_by(DedupRun.created_at.desc())
        )
    )


def get_run(session: Session, run_id: uuid.UUID) -> DedupRun:
    run = session.get(DedupRun, run_id)
    if run is None:
        raise NotFoundError("dedup run not found")
    return run


def _flatten_active_contacts(session: Session, working_copy_id: uuid.UUID) -> list[dict]:
    rows = session.scalars(
        select(WorkingCopyContact).where(
            WorkingCopyContact.working_copy_id == working_copy_id,
            WorkingCopyContact.status == "active",
        )
    )
    return [contact_flatten.flatten_contact(r.id, r.payload) for r in rows]


def run_dedup_job(session: Session, run_id: uuid.UUID, engine: DedupEngine) -> DedupRun:
    """Run a queued/running dedup job to a terminal state (FR-005/FR-006/FR-008)."""
    run = session.get(DedupRun, run_id)
    if run is None:
        raise ValueError("dedup run not found")

    run.status = "running"
    run.started_at = _now()
    session.commit()

    try:
        rows = _flatten_active_contacts(session, run.working_copy_id)
        match_rows = list(engine.run(str(run.id), rows))
        count = _ingest(session, run, match_rows)
    except Exception as exc:  # noqa: BLE001 - record redacted failure, never finalize (FR-006)
        session.rollback()
        run = session.get(DedupRun, run_id)
        run.status = "failed"
        run.last_error = type(exc).__name__
        run.finished_at = _now()
        audit_service.record(
            session,
            action="dedup.run.failed",
            target_type="dedup_run",
            target_id=run.id,
            source_ref=run.working_copy_id,
            details={"error": type(exc).__name__},
        )
        session.commit()
        return run

    _supersede_prior_pending(session, run)
    run.cluster_count = count
    run.status = "completed"
    run.finished_at = _now()
    audit_service.record(
        session,
        action="dedup.run.completed",
        target_type="dedup_run",
        target_id=run.id,
        source_ref=run.working_copy_id,
        details={"cluster_count": count, "model_version": run.model_version},
    )
    session.commit()
    return run


def _ingest(session: Session, run: DedupRun, match_rows: list[MatchRow]) -> int:
    """Group match rows by z_cluster (size ≥ 2) into clusters; apply the confidence floor."""
    grouped: dict[str, list[MatchRow]] = defaultdict(list)
    for mr in match_rows:
        grouped[mr.z_cluster].append(mr)

    created = 0
    for key, members in grouped.items():
        if len(members) < 2:
            continue  # singletons are never clustered (D5)
        confidence = max(m.z_max_score for m in members)
        if confidence < run.confidence_floor:
            continue  # precision floor (D5)
        min_score = min(m.z_min_score for m in members)
        cluster = DuplicateCluster(
            dedup_run_id=run.id,
            working_copy_id=run.working_copy_id,
            z_cluster_key=str(key),
            confidence=confidence,
            min_score=min_score,
            size=len(members),
            status="pending",
        )
        session.add(cluster)
        session.flush()
        for m in members:
            session.add(
                ClusterMember(
                    cluster_id=cluster.id,
                    working_copy_contact_id=uuid.UUID(m.wcc_id),
                    match_score=m.z_max_score,
                )
            )
        created += 1
    session.flush()
    return created


def _supersede_prior_pending(session: Session, run: DedupRun) -> None:
    """A newer completed run supersedes still-pending clusters of older runs (FR-008)."""
    prior = session.scalars(
        select(DuplicateCluster)
        .join(DedupRun, DedupRun.id == DuplicateCluster.dedup_run_id)
        .where(
            DuplicateCluster.working_copy_id == run.working_copy_id,
            DuplicateCluster.dedup_run_id != run.id,
            DuplicateCluster.status == "pending",
        )
    )
    for cluster in prior:
        cluster.status = "superseded"
    session.flush()
