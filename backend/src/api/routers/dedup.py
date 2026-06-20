"""Deduplication router (feature 002): runs, clusters, and resolution (merge/dismiss/undo).

Makes zero Google calls and never writes the snapshot. All access is scoped to a working copy
(FR-022). Mirrors contracts/openapi.yaml.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    ClusterMemberOut,
    ClusterOut,
    ContactSummaryOut,
    DedupRunOut,
    MergePreviewOut,
    MergeRequest,
    MergeResultOut,
)
from src.core.config import get_settings
from src.core.db import get_session
from src.integrations.dedup_engine import get_engine
from src.models.dedup import DuplicateCluster
from src.services import cluster_service, dedup_service

router = APIRouter(prefix="/api", tags=["dedup"])


def _run_out(run) -> DedupRunOut:
    return DedupRunOut(
        id=run.id,
        workingCopyId=run.working_copy_id,
        status=run.status,
        modelVersion=run.model_version,
        confidenceFloor=run.confidence_floor,
        clusterCount=run.cluster_count,
        lastError=run.last_error,
        createdAt=run.created_at,
        startedAt=run.started_at,
        finishedAt=run.finished_at,
    )


def _cluster_out(session: Session, cluster: DuplicateCluster) -> ClusterOut:
    members = [
        ClusterMemberOut(
            id=m.id,
            workingCopyContactId=m.working_copy_contact_id,
            matchScore=m.match_score,
            isSurvivor=m.is_survivor,
            contact=ContactSummaryOut(**cluster_service.contact_summary(contact)),
        )
        for m, contact in cluster_service.member_contacts(session, cluster)
    ]
    return ClusterOut(
        id=cluster.id,
        dedupRunId=cluster.dedup_run_id,
        workingCopyId=cluster.working_copy_id,
        confidence=cluster.confidence,
        minScore=cluster.min_score,
        size=cluster.size,
        status=cluster.status,
        mergeRecordId=cluster.merge_record.id if cluster.merge_record else None,
        members=members,
    )


# ---- Runs (US1) ----------------------------------------------------------------------------

@router.post(
    "/working-copies/{working_copy_id}/dedup-runs", response_model=DedupRunOut, status_code=202
)
def start_dedup_run(
    working_copy_id: uuid.UUID,
    background: bool = Query(True, description="Run asynchronously via the worker"),
    session: Session = Depends(get_session),
) -> DedupRunOut:
    run = dedup_service.create_run(session, working_copy_id)
    if not background:
        # Synchronous path for single-process/dev use; the worker handles the async path.
        engine = get_engine(get_settings().dedup_engine)
        dedup_service.run_dedup_job(session, run.id, engine)
        run = dedup_service.get_run(session, run.id)
    return _run_out(run)


@router.get(
    "/working-copies/{working_copy_id}/dedup-runs", response_model=list[DedupRunOut]
)
def list_dedup_runs(
    working_copy_id: uuid.UUID, session: Session = Depends(get_session)
) -> list[DedupRunOut]:
    return [_run_out(r) for r in dedup_service.list_runs(session, working_copy_id)]


@router.get("/dedup-runs/{run_id}", response_model=DedupRunOut)
def get_dedup_run(run_id: uuid.UUID, session: Session = Depends(get_session)) -> DedupRunOut:
    return _run_out(dedup_service.get_run(session, run_id))


# ---- Clusters review (US2) -----------------------------------------------------------------

@router.get("/dedup-runs/{run_id}/clusters", response_model=list[ClusterOut])
def list_clusters(
    run_id: uuid.UUID,
    status: str = Query("pending"),
    minConfidence: float | None = Query(None),
    session: Session = Depends(get_session),
) -> list[ClusterOut]:
    clusters = cluster_service.list_clusters(
        session, run_id, status=status, min_confidence=minConfidence
    )
    return [_cluster_out(session, c) for c in clusters]


@router.get("/clusters/{cluster_id}", response_model=ClusterOut)
def get_cluster(cluster_id: uuid.UUID, session: Session = Depends(get_session)) -> ClusterOut:
    return _cluster_out(session, cluster_service.get_cluster(session, cluster_id))


# ---- Cluster resolution (US3) --------------------------------------------------------------

@router.get("/clusters/{cluster_id}/merge-preview", response_model=MergePreviewOut)
def get_merge_preview(
    cluster_id: uuid.UUID,
    survivorContactId: uuid.UUID | None = Query(None),
    session: Session = Depends(get_session),
) -> MergePreviewOut:
    return MergePreviewOut(**cluster_service.merge_preview(session, cluster_id, survivorContactId))


@router.post("/clusters/{cluster_id}/merge", response_model=MergeResultOut)
def merge_cluster(
    cluster_id: uuid.UUID, body: MergeRequest | None = None, session: Session = Depends(get_session)
) -> MergeResultOut:
    body = body or MergeRequest()
    record = cluster_service.merge_cluster(
        session,
        cluster_id,
        survivor_id=body.survivorContactId,
        payload_override=body.payloadOverride,
    )
    return MergeResultOut(
        mergeRecordId=record.id,
        survivorContactId=record.survivor_contact_id,
        clusterId=record.cluster_id,
        retiredContactIds=[uuid.UUID(r) for r in record.retired_member_ids],
    )


@router.post("/clusters/{cluster_id}/dismiss", response_model=ClusterOut)
def dismiss_cluster(
    cluster_id: uuid.UUID, session: Session = Depends(get_session)
) -> ClusterOut:
    cluster = cluster_service.dismiss_cluster(session, cluster_id)
    return _cluster_out(session, cluster)


@router.post("/merge-records/{merge_record_id}/undo", response_model=ClusterOut)
def undo_merge(
    merge_record_id: uuid.UUID, session: Session = Depends(get_session)
) -> ClusterOut:
    cluster = cluster_service.undo_merge(session, merge_record_id)
    return _cluster_out(session, cluster)
