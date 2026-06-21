"""Model package — import all entities so metadata is fully populated."""
from src.models.account import Account, Credential
from src.models.audit import AuditEntry
from src.models.base import Base
from src.models.dedup import ClusterMember, DedupRun, DuplicateCluster, MergeRecord
from src.models.export import ContactLabel, ExportRun, LabelAssignment, LabelBatch
from src.models.snapshot import ImportJob, Snapshot, SnapshotContact
from src.models.triage import (
    DeleteBatch,
    DeletionRecord,
    ProcessingItem,
    StagedEdit,
    TriageDecision,
    TriageSession,
)
from src.models.validation import ValidationItem, ValidationRun
from src.models.working_copy import WorkingCopy, WorkingCopyContact

__all__ = [
    "Base",
    "Account",
    "Credential",
    "Snapshot",
    "ImportJob",
    "SnapshotContact",
    "WorkingCopy",
    "WorkingCopyContact",
    "AuditEntry",
    "DedupRun",
    "DuplicateCluster",
    "ClusterMember",
    "MergeRecord",
    "TriageSession",
    "TriageDecision",
    "ProcessingItem",
    "StagedEdit",
    "DeleteBatch",
    "DeletionRecord",
    "ExportRun",
    "LabelBatch",
    "LabelAssignment",
    "ContactLabel",
    "ValidationRun",
    "ValidationItem",
]
