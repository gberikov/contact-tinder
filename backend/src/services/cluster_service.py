"""Cluster review and resolution: survivor-based merge (reversible), dismiss, undo.

All access is scoped by working_copy_id so cross-account/cross-working-copy ids return not-found
(FR-022). Merges never touch the snapshot and are fully reversible via MergeRecord (FR-018, D6).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.models.dedup import ClusterMember, DedupRun, DuplicateCluster, MergeRecord
from src.models.working_copy import WorkingCopyContact
from src.services import audit_service, contact_fields, contact_flatten

# Multi-valued Person fields that are unioned on merge.
_MULTI_FIELDS = (
    "emailAddresses",
    "phoneNumbers",
    "addresses",
    "organizations",
    "urls",
    "biographies",
    "userDefined",
)
# Single-valued fields where members may conflict (operator override surfaced).
_SINGLE_FIELDS = ("names", "birthdays", "nicknames")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- Review (US2) ---------------------------------------------------------------------------

def list_clusters(
    session: Session,
    run_id: uuid.UUID,
    *,
    status: str = "pending",
    min_confidence: float | None = None,
) -> list[DuplicateCluster]:
    run = session.get(DedupRun, run_id)
    if run is None:
        raise NotFoundError("dedup run not found")
    if run.status != "completed":
        raise ConflictError("run is not completed")
    stmt = select(DuplicateCluster).where(
        DuplicateCluster.dedup_run_id == run_id,
        DuplicateCluster.status == status,
    )
    if min_confidence is not None:
        stmt = stmt.where(DuplicateCluster.confidence >= min_confidence)
    stmt = stmt.order_by(DuplicateCluster.confidence.desc())
    return list(session.scalars(stmt))


def get_cluster(session: Session, cluster_id: uuid.UUID) -> DuplicateCluster:
    cluster = session.get(DuplicateCluster, cluster_id)
    if cluster is None:
        raise NotFoundError("cluster not found")
    return cluster


def member_contacts(
    session: Session, cluster: DuplicateCluster
) -> list[tuple[ClusterMember, WorkingCopyContact]]:
    out = []
    for m in cluster.members:
        contact = session.get(WorkingCopyContact, m.working_copy_contact_id)
        if contact is not None:
            out.append((m, contact))
    return out


def contact_summary(contact: WorkingCopyContact) -> dict:
    return {
        "displayName": contact_fields.display_name(contact.payload),
        "primaryEmail": contact_fields.primary_email(contact.payload),
        "primaryPhone": contact_fields.primary_phone(contact.payload),
        "organization": contact_flatten.organization(contact.payload),
        "status": contact.status,
    }


# ---- Merge preview + apply (US3) ------------------------------------------------------------

def _completeness(payload: dict) -> int:
    return sum(1 for v in payload.values() if v)


def _pick_survivor(
    contacts: list[WorkingCopyContact], override: uuid.UUID | None
) -> WorkingCopyContact:
    if override is not None:
        match = next((c for c in contacts if c.id == override), None)
        if match is None:
            raise ConflictError("survivor must be a member of the cluster")
        return match
    return max(contacts, key=lambda c: _completeness(c.payload))


def _build_merged_payload(
    survivor: WorkingCopyContact, others: list[WorkingCopyContact]
) -> tuple[dict, list[dict]]:
    """Union multi-valued fields into the survivor; record single-value conflicts."""
    merged: dict = dict(survivor.payload)
    conflicts: list[dict] = []

    for field in _MULTI_FIELDS:
        combined = list(merged.get(field) or [])
        seen = {_value_key(v) for v in combined}
        for other in others:
            for item in other.payload.get(field) or []:
                key = _value_key(item)
                if key not in seen:
                    combined.append(item)
                    seen.add(key)
        if combined:
            merged[field] = combined

    for field in _SINGLE_FIELDS:
        candidates: list[str] = []
        for c in [survivor, *others]:
            label = _single_label(c.payload.get(field))
            if label and label not in candidates:
                candidates.append(label)
        if len(candidates) > 1:
            conflicts.append({"field": field, "chosen": candidates[0], "candidates": candidates})
    return merged, conflicts


def _value_key(item: dict) -> str:
    return (item.get("value") or item.get("name") or item.get("formattedValue") or str(item)).strip().lower()


def _single_label(items) -> str | None:
    if not items:
        return None
    first = items[0]
    return first.get("displayName") or first.get("value") or first.get("text")


def merge_preview(
    session: Session, cluster_id: uuid.UUID, survivor_id: uuid.UUID | None = None
) -> dict:
    cluster = get_cluster(session, cluster_id)
    pairs = member_contacts(session, cluster)
    contacts = [c for _, c in pairs]
    survivor = _pick_survivor(contacts, survivor_id)
    others = [c for c in contacts if c.id != survivor.id]
    merged, conflicts = _build_merged_payload(survivor, others)
    return {
        "survivorContactId": survivor.id,
        "proposedPayload": merged,
        "conflicts": conflicts,
    }


def merge_cluster(
    session: Session,
    cluster_id: uuid.UUID,
    *,
    survivor_id: uuid.UUID | None = None,
    payload_override: dict | None = None,
) -> MergeRecord:
    cluster = get_cluster(session, cluster_id)
    if cluster.status != "pending":
        raise ConflictError("cluster is not pending")

    pairs = member_contacts(session, cluster)
    contacts = [c for _, c in pairs]
    if any(c.status != "active" for c in contacts) or len(contacts) != cluster.size:
        raise ConflictError("a cluster member is no longer active")  # FR-020

    survivor = _pick_survivor(contacts, survivor_id)
    others = [c for c in contacts if c.id != survivor.id]
    merged = payload_override or _build_merged_payload(survivor, others)[0]

    # A cluster has at most one MergeRecord (unique). After an undo it persists as `undone`;
    # re-merging reuses that row rather than inserting a duplicate.
    record = session.scalar(
        select(MergeRecord).where(MergeRecord.cluster_id == cluster.id)
    )
    if record is None:
        record = MergeRecord(cluster_id=cluster.id, working_copy_id=cluster.working_copy_id)
        session.add(record)
    record.survivor_contact_id = survivor.id
    record.survivor_payload_before = dict(survivor.payload)
    record.merged_payload = merged
    record.retired_member_ids = [str(c.id) for c in others]
    record.status = "active"
    record.undone_at = None

    survivor.payload = merged
    for c in others:
        c.status = "retired"
    for m, contact in pairs:
        m.is_survivor = contact.id == survivor.id
    cluster.status = "merged"
    cluster.resolved_at = _now()
    session.flush()

    audit_service.record(
        session,
        action="cluster.merged",
        target_type="duplicate_cluster",
        target_id=cluster.id,
        source_ref=cluster.dedup_run_id,
        details={
            "survivor": str(survivor.id),
            "retired": [str(c.id) for c in others],
            "confidence": cluster.confidence,
        },
    )
    session.commit()
    return record


def dismiss_cluster(session: Session, cluster_id: uuid.UUID) -> DuplicateCluster:
    cluster = get_cluster(session, cluster_id)
    if cluster.status != "pending":
        raise ConflictError("cluster is not pending")
    cluster.status = "dismissed"  # per-run only (FR-019)
    cluster.resolved_at = _now()
    session.flush()
    audit_service.record(
        session,
        action="cluster.dismissed",
        target_type="duplicate_cluster",
        target_id=cluster.id,
        source_ref=cluster.dedup_run_id,
        details={"size": cluster.size},
    )
    session.commit()
    return cluster


def undo_merge(session: Session, merge_record_id: uuid.UUID) -> DuplicateCluster:
    record = session.get(MergeRecord, merge_record_id)
    if record is None:
        raise NotFoundError("merge record not found")
    if record.status != "active":
        raise ConflictError("merge already undone")

    survivor = session.get(WorkingCopyContact, record.survivor_contact_id)
    survivor.payload = dict(record.survivor_payload_before)
    for rid in record.retired_member_ids:
        retired = session.get(WorkingCopyContact, uuid.UUID(rid))
        if retired is not None:
            retired.status = "active"

    cluster = session.get(DuplicateCluster, record.cluster_id)
    cluster.status = "pending"
    cluster.resolved_at = None
    for m in cluster.members:
        m.is_survivor = False
    record.status = "undone"
    record.undone_at = _now()
    session.flush()

    audit_service.record(
        session,
        action="merge.undone",
        target_type="duplicate_cluster",
        target_id=cluster.id,
        source_ref=cluster.dedup_run_id,
        details={"merge_record": str(record.id)},
    )
    session.commit()
    return cluster
