import uuid

import pytest
from sqlalchemy import func, select

from src.core.errors import ConflictError, NotFoundError
from src.models.audit import AuditEntry
from src.models.dedup import DedupRun, DuplicateCluster
from src.models.export import ExportRun, LabelBatch
from src.models.triage import DeleteBatch, StagedEdit, TriageSession
from src.models.working_copy import WorkingCopyContact
from src.services import working_copy_service
from tests.helpers import dup_person, seed_account, seed_working_copy


def _seed_derived(db, copy):
    """Attach one row of every working-copy-derived kind, plus a child where one exists."""
    wcc_id = db.scalar(
        select(WorkingCopyContact.id).where(WorkingCopyContact.working_copy_id == copy.id)
    )
    run = DedupRun(working_copy_id=copy.id, status="completed", model_version="t")
    db.add(run)
    db.flush()
    db.add(DuplicateCluster(dedup_run_id=run.id, working_copy_id=copy.id,
                            z_cluster_key="k", confidence=0.9, size=2, status="pending"))
    session = TriageSession(working_copy_id=copy.id, status="in_progress")
    db.add(session)
    db.add(StagedEdit(working_copy_contact_id=wcc_id, working_copy_id=copy.id, kind="edit",
                      payload_before={}, payload_after={}))
    db.add(DeleteBatch(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.add(LabelBatch(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.add(ExportRun(working_copy_id=copy.id, account_id=copy.snapshot.account_id))
    db.commit()


def test_delete_requires_confirmation(db):
    account = seed_account(db)
    copy = seed_working_copy(db, account, [dup_person(0, name="A B", phone="1")])
    with pytest.raises(ConflictError) as exc:
        working_copy_service.delete_working_copy(db, copy.id, confirm=False)
    assert exc.value.status_code == 400
    assert exc.value.code == "confirmation_required"


def test_delete_unknown_raises_not_found(db):
    with pytest.raises(NotFoundError):
        working_copy_service.delete_working_copy(db, uuid.uuid4(), confirm=True)


def test_delete_cascades_and_audits(db):
    account = seed_account(db)
    copy = seed_working_copy(db, account, [dup_person(0, name="A B", phone="1")])
    cid = copy.id
    _seed_derived(db, copy)

    working_copy_service.delete_working_copy(db, cid, confirm=True)

    with pytest.raises(NotFoundError):
        working_copy_service.get_working_copy(db, cid)
    for model in (DedupRun, DuplicateCluster, TriageSession, StagedEdit, DeleteBatch,
                  LabelBatch, ExportRun, WorkingCopyContact):
        remaining = db.scalar(
            select(func.count()).select_from(model).where(model.working_copy_id == cid)
        )
        assert remaining == 0, f"{model.__name__} rows survived"
    audited = db.scalar(
        select(func.count()).select_from(AuditEntry).where(
            AuditEntry.action == "working_copy.deleted", AuditEntry.target_id == cid
        )
    )
    assert audited == 1
