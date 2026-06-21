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


class GrantWriteBody(BaseModel):
    # Relative frontend path to return to after consent (e.g. the Export screen).
    returnTo: str | None = None


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


# ---- Swipe triage (feature 003) -----------------------------------------------------------

class SessionSummaryOut(BaseModel):
    total: int
    decided: int
    keep: int
    delete: int
    processing: int
    remaining: int


class TriageSessionOut(BaseModel):
    id: uuid.UUID
    workingCopyId: uuid.UUID
    dedupRunId: uuid.UUID | None = None
    status: str
    createdAt: datetime
    finishedAt: datetime | None = None
    summary: SessionSummaryOut


class ContactDetailOut(BaseModel):
    displayName: str | None = None
    primaryEmail: str | None = None
    primaryPhone: str | None = None
    organization: str | None = None
    status: str
    payload: dict


class DeckCardOut(BaseModel):
    workingCopyContactId: uuid.UUID
    contact: ContactDetailOut
    currentOutcome: str | None = None


class DeckPageOut(BaseModel):
    cards: list[DeckCardOut]
    nextCursor: str | None = None


class DecisionRequest(BaseModel):
    outcome: str
    wantsEdit: bool = False
    wantsTransliterate: bool = False


class TriageDecisionOut(BaseModel):
    id: uuid.UUID
    sessionId: uuid.UUID
    workingCopyContactId: uuid.UUID
    outcome: str
    decidedAt: datetime
    processingItemId: uuid.UUID | None = None


class TransliterationSuggestionOut(BaseModel):
    hasSuggestion: bool
    fields: dict[str, str]


class TransliterationAcceptRequest(BaseModel):
    fields: dict[str, str]


class EditRequest(BaseModel):
    payload: dict


class StagedEditOut(BaseModel):
    id: uuid.UUID
    workingCopyContactId: uuid.UUID
    kind: str
    status: str
    createdAt: datetime
    undoneAt: datetime | None = None


class ProcessingItemOut(BaseModel):
    id: uuid.UUID
    sessionId: uuid.UUID
    workingCopyContactId: uuid.UUID
    wantsEdit: bool
    wantsTransliterate: bool
    status: str
    contact: ContactDetailOut
    transliterationSuggestion: TransliterationSuggestionOut | None = None


class CreateDeleteBatchBody(BaseModel):
    sessionId: uuid.UUID | None = None


class DeletionRecordOut(BaseModel):
    id: uuid.UUID
    workingCopyContactId: uuid.UUID | None = None
    status: str
    contact: ContactDetailOut
    error: str | None = None


class DeleteBatchOut(BaseModel):
    id: uuid.UUID
    workingCopyId: uuid.UUID
    sessionId: uuid.UUID | None = None
    accountId: uuid.UUID
    status: str
    totalCount: int
    deletedCount: int
    failedCount: int
    lastError: str | None = None
    createdAt: datetime
    previewedAt: datetime | None = None
    committedAt: datetime | None = None
    undoneAt: datetime | None = None


# ---- Export to Google (feature 004) -------------------------------------------------------

class ExportContactSummaryOut(BaseModel):
    """Redacted display summary of a set member (mirrors openapi.yaml ContactSummary)."""

    workingCopyContactId: uuid.UUID
    displayName: str | None = None
    primaryEmail: str | None = None
    primaryPhone: str | None = None
    organization: str | None = None


class StartExportBody(BaseModel):
    sessionId: uuid.UUID | None = None


class ExportPreviewOut(BaseModel):
    workingCopyId: uuid.UUID
    sessionId: uuid.UUID | None = None
    deleteCount: int
    labelCount: int
    undecidedCount: int
    nothingToExport: bool
    labelName: str
    deleteSet: list[ExportContactSummaryOut] = []
    labelSet: list[ExportContactSummaryOut] = []


class ExportReportOut(BaseModel):
    deleted: int
    skippedAbsentDelete: int
    labeled: int
    skippedAbsentLabel: int
    failed: int
    excluded: int
    deleteStatus: str | None = None
    labelStatus: str | None = None


class ExportRunOut(BaseModel):
    id: uuid.UUID
    workingCopyId: uuid.UUID
    accountId: uuid.UUID
    sessionId: uuid.UUID | None = None
    deleteBatchId: uuid.UUID | None = None
    labelBatchId: uuid.UUID | None = None
    status: str
    undecidedCount: int
    createdAt: datetime
    completedAt: datetime | None = None
    report: ExportReportOut


# ---- Validate & Normalize / Tidy (feature 006) --------------------------------------------

class StartValidationBody(BaseModel):
    sessionId: uuid.UUID | None = None
    # ISO-3166 alpha-2 region for parsing national-format phones; falls back to phone_default_region.
    defaultRegion: str | None = None


class ValidationRunOut(BaseModel):
    id: uuid.UUID
    workingCopyId: uuid.UUID
    sessionId: uuid.UUID | None = None
    status: str
    defaultRegion: str | None = None
    totalCount: int
    checkedCount: int
    autoAppliedCount: int
    queuedCount: int
    # Derived (not stored): live count of items still status='pending' (drives the passable warning).
    pendingCount: int
    lastError: str | None = None
    createdAt: datetime
    startedAt: datetime | None = None
    completedAt: datetime | None = None


class ValidationItemOut(BaseModel):
    id: uuid.UUID
    workingCopyContactId: uuid.UUID
    contactDisplayName: str | None = None
    fieldKind: str
    fieldIndex: int
    issueType: str
    originalValue: str
    suggestedValue: str | None = None
    status: str
    stagedEditId: uuid.UUID | None = None
    createdAt: datetime
    resolvedAt: datetime | None = None


class ResolveValidationItemBody(BaseModel):
    # exactly one action: "set_type" (+type) | "edit_value" (+value) | "remove_field"
    action: str
    type: str | None = None
    value: str | None = None


class DetectRegionOut(BaseModel):
    region: str | None = None
    source: str  # "geoip" | "none"
