"""Resumable paged import of personal connections into a snapshot (FR-016, A1).

Pure of the queue mechanism: callable directly with an injected PeopleClient and sleep, so the
finalize/resume/atomicity behavior is unit-testable without live Google or a worker loop.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from src.core import backoff
from src.integrations.people_client import (
    AuthError,
    PeopleClient,
    RateLimitedError,
    TransientError,
)
from src.models.snapshot import ImportJob, SnapshotContact
from src.services import account_service, contact_fields, snapshot_service

logger = logging.getLogger(__name__)


def run_import_job(
    session: Session,
    job_id: uuid.UUID,
    client: PeopleClient,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> ImportJob:
    """Run (or resume) an import job to terminal state. Commits progress per page."""
    job = session.get(ImportJob, job_id)
    if job is None:
        raise ValueError("import job not found")
    snapshot = job.snapshot

    job.status = "running"
    session.flush()
    session.commit()

    page_token = job.page_token
    sync_token: str | None = snapshot.next_sync_token

    while True:
        try:
            page = client.list_connections(page_token)
        except AuthError:
            # Token expired/revoked: fail without finalizing; flag account (FR-017).
            account_service.mark_needs_reauth(session, snapshot.account_id)
            _fail(session, job, snapshot, "authorization required")
            return job
        except (RateLimitedError, TransientError) as exc:
            job.attempts += 1
            if not backoff.should_retry(job.attempts, job.max_attempts):
                _fail(session, job, snapshot, "transient error retry ceiling reached")
                return job
            retry_after = getattr(exc, "retry_after", None)
            session.commit()
            sleep(backoff.next_delay(job.attempts, retry_after=retry_after))
            continue

        for person in page.people:
            session.add(
                SnapshotContact(
                    snapshot_id=snapshot.id,
                    resource_name=person.get("resourceName", str(uuid.uuid4())),
                    etag=person.get("etag"),
                    payload=person,
                    display_name=contact_fields.display_name(person),
                    primary_email=contact_fields.primary_email(person),
                    primary_phone=contact_fields.primary_phone(person),
                )
            )
        job.fetched_count += len(page.people)
        job.page_token = page.next_page_token
        if page.total_estimate is not None:
            job.total_estimate = page.total_estimate
        if page.next_sync_token:
            sync_token = page.next_sync_token
        session.flush()
        session.commit()  # persist cursor -> resumable across restarts

        if page.next_page_token is None:
            break
        page_token = page.next_page_token

    # Finalize transactionally (FR-008): only here does the snapshot become usable.
    snapshot_service.finalize_import(session, snapshot, job.fetched_count, sync_token)
    job.status = "completed"
    job.finished_at = _now()
    session.commit()
    return job


def _fail(session: Session, job: ImportJob, snapshot, message: str) -> None:
    job.status = "failed"
    job.last_error = message
    job.finished_at = _now()
    snapshot.status = "failed"
    session.commit()


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
