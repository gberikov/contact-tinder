from sqlalchemy import func, select

from src.integrations.people_client import AuthError, TransientError
from src.models.snapshot import SnapshotContact
from src.services import import_runner, snapshot_service
from tests.fakes.fake_people_client import FakePeopleClient, make_person
from tests.helpers import seed_account


def test_auth_error_fails_without_finalizing_and_flags_account(db):
    account = seed_account(db)
    snapshot = snapshot_service.create_snapshot(db, account.id)
    client = FakePeopleClient([make_person(0)], page_size=2, errors=[AuthError()])

    import_runner.run_import_job(db, snapshot.import_job.id, client, sleep=lambda _: None)

    db.refresh(snapshot)
    db.refresh(account)
    assert snapshot.status == "failed"
    assert snapshot.contact_count is None  # never finalized (FR-008)
    assert snapshot.import_job.status == "failed"
    assert account.status == "needs_reauth"  # FR-017


def test_retry_ceiling_exhaustion_fails(db):
    account = seed_account(db)
    snapshot = snapshot_service.create_snapshot(db, account.id)
    client = FakePeopleClient(
        [make_person(i) for i in range(4)], page_size=2,
        errors=[TransientError() for _ in range(5)],
    )

    import_runner.run_import_job(db, snapshot.import_job.id, client, sleep=lambda _: None)

    db.refresh(snapshot)
    assert snapshot.status == "failed"
    assert snapshot.import_job.status == "failed"
    assert "ceiling" in (snapshot.import_job.last_error or "")
    # No partial snapshot is presented as usable (SC-006): nothing imported.
    total = db.scalar(
        select(func.count()).select_from(SnapshotContact).where(
            SnapshotContact.snapshot_id == snapshot.id
        )
    )
    assert total == 0
