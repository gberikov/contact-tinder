"""Pydantic response/request schemas mirroring contracts/openapi.yaml.

NOTE: no schema exposes Credential/token fields (FR-002).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AccountOut(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    grantedScopes: list[str]
    createdAt: datetime


class SnapshotOut(BaseModel):
    id: uuid.UUID
    accountId: uuid.UUID
    accountEmail: str | None = None
    status: str
    source: str
    contactCount: int | None = None
    workingCopyCount: int = 0
    label: str | None = None
    createdAt: datetime
    finalizedAt: datetime | None = None


class ImportJobOut(BaseModel):
    snapshotId: uuid.UUID
    status: str
    fetchedCount: int
    totalEstimate: int | None = None
    lastError: str | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class WorkingCopyOut(BaseModel):
    id: uuid.UUID
    snapshotId: uuid.UUID
    label: str
    status: str
    contactCount: int | None = None
    createdAt: datetime


class ContactOut(BaseModel):
    id: uuid.UUID
    resourceName: str
    displayName: str | None = None
    primaryEmail: str | None = None
    primaryPhone: str | None = None
    payload: dict


class ContactPage(BaseModel):
    items: list[ContactOut]
    page: int
    pageSize: int
    total: int


class CreateBody(BaseModel):
    label: str | None = None


# ---- Deduplication (feature 002) ----------------------------------------------------------

class DedupRunOut(BaseModel):
    id: uuid.UUID
    workingCopyId: uuid.UUID
    status: str
    modelVersion: str
    confidenceFloor: float
    clusterCount: int | None = None
    lastError: str | None = None
    createdAt: datetime
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class ContactSummaryOut(BaseModel):
    displayName: str | None = None
    primaryEmail: str | None = None
    primaryPhone: str | None = None
    organization: str | None = None
    status: str


class ClusterMemberOut(BaseModel):
    id: uuid.UUID
    workingCopyContactId: uuid.UUID
    matchScore: float | None = None
    isSurvivor: bool = False
    contact: ContactSummaryOut


class ClusterOut(BaseModel):
    id: uuid.UUID
    dedupRunId: uuid.UUID
    workingCopyId: uuid.UUID
    confidence: float
    minScore: float | None = None
    size: int
    status: str
    mergeRecordId: uuid.UUID | None = None
    members: list[ClusterMemberOut]


class MergeConflict(BaseModel):
    field: str
    chosen: str
    candidates: list[str]


class MergePreviewOut(BaseModel):
    survivorContactId: uuid.UUID
    proposedPayload: dict
    conflicts: list[MergeConflict]


class MergeRequest(BaseModel):
    survivorContactId: uuid.UUID | None = None
    payloadOverride: dict | None = None


class MergeResultOut(BaseModel):
    mergeRecordId: uuid.UUID
    survivorContactId: uuid.UUID
    clusterId: uuid.UUID
    retiredContactIds: list[uuid.UUID]
