"""PostgreSQL-backed import worker (research D4).

Claims queued/running import jobs with FOR UPDATE SKIP LOCKED (keeps PostgreSQL as the only
datastore — no Redis), builds an authorized PeopleClient per account, and runs the resumable
import. Designed so a restart resumes in-flight jobs from their persisted cursor.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.db import SessionLocal
from src.core.logging import configure_logging
from src.integrations.people_client import GooglePeopleClient
from src.models.account import Account
from src.models.snapshot import ImportJob, Snapshot
from src.services import crypto, import_runner

logger = logging.getLogger(__name__)
_ACTIVE = ("queued", "running")


def claim_next_job(session: Session) -> ImportJob | None:
    stmt = (
        select(ImportJob)
        .where(ImportJob.status.in_(_ACTIVE))
        .order_by(ImportJob.started_at.is_(None).desc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalar(stmt)


def build_client(session: Session, snapshot: Snapshot) -> GooglePeopleClient:
    settings = get_settings()
    account = session.get(Account, snapshot.account_id)
    from google.oauth2.credentials import Credentials

    settings_scopes = account.granted_scopes.split() if account.granted_scopes else None
    creds = Credentials(
        token=crypto.decrypt(account.credential.enc_access_token),
        refresh_token=crypto.decrypt(account.credential.enc_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        # client_id/secret are REQUIRED to refresh the access token mid-import (a large address
        # book outlives the ~1h token); without them google-auth raises RefreshError and the
        # import stalls. Mirrors the delete/label workers (commit 84c8eeb).
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=settings_scopes,
    )
    return GooglePeopleClient(creds)


def run_once(session: Session) -> bool:
    job = claim_next_job(session)
    if job is None:
        return False
    client = build_client(session, job.snapshot)
    import_runner.run_import_job(session, job.id, client)
    return True


def main() -> None:  # pragma: no cover - long-running loop
    configure_logging()
    logger.info("import worker started")
    while True:
        with SessionLocal() as session:
            try:
                worked = run_once(session)
            except Exception:  # noqa: BLE001 - keep worker alive
                logger.exception("import job failed")
                worked = False
        if not worked:
            time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    main()
