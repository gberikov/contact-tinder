from sqlalchemy import func, select

from src.integrations.people_client import TransientError
from src.models.snapshot import SnapshotContact
from src.services import import_runner, snapshot_service
from tests.fakes.fake_people_client import FakePeopleClient, make_person
from tests.helpers import seed_account


def test_import_resumes_from_persisted_cursor(db):
    """A transient failure mid-import leaves a persisted page cursor; rerun completes with no loss."""
    account = seed_account(db)
    people = [make_person(i) for i in range(6)]
    snapshot = snapshot_service.create_snapshot(db, account.id)
    job_id = snapshot.import_job.id

    # First run: 2 pages succeed (4 contacts), then ceiling-exhausting transient errors.
    # 2 good pages (4 contacts), then 5 transient errors to exhaust max_attempts (=5).
    failing = FakePeopleClient(
        people, page_size=2,
        errors=[None, None] + [TransientError() for _ in range(5)],
    )
    import_runner.run_import_job(db, job_id, failing, sleep=lambda _: None)

    job = snapshot_service.get_import_job(db, snapshot.id)
    assert job.status == "failed"
    assert job.fetched_count == 4
    assert job.page_token == "4"  # cursor persisted at the resume point

    # Re-queue and resume with a healthy client — continues from cursor, finalizes.
    job.status = "queued"
    job.attempts = 0
    db.commit()
    healthy = FakePeopleClient(people, page_size=2)
    import_runner.run_import_job(db, job_id, healthy, sleep=lambda _: None)

    db.refresh(snapshot)
    assert snapshot.status == "complete"
    total = db.scalar(
        select(func.count()).select_from(SnapshotContact).where(
            SnapshotContact.snapshot_id == snapshot.id
        )
    )
    assert total == 6  # zero loss, no duplicates across the resume boundary
