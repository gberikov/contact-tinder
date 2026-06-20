"""PostgreSQL-backed delete-batch worker (feature 003, research D10).

Claims `committing` (delete) and `undoing` (restore) DeleteBatch rows with FOR UPDATE SKIP LOCKED
(PostgreSQL stays the only datastore — no Redis), builds an authorized PeopleWriteClient per account,
and runs the batch to a terminal state idempotently. Runs inside the existing `worker` service —
no new container. The default client is the Google-free fake; set PEOPLE_WRITE_CLIENT=google to use
the real Google write path.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.db import SessionLocal
from src.core.logging import configure_logging
from src.integrations.people_client import PeopleWriteClient, get_write_client
from src.models.account import Account
from src.models.triage import DeleteBatch
from src.services import crypto, delete_batch_service

logger = logging.getLogger(__name__)
_ACTIVE = ("committing", "undoing")


def claim_next_batch(session: Session) -> DeleteBatch | None:
    stmt = (
        select(DeleteBatch)
        .where(DeleteBatch.status.in_(_ACTIVE))
        .order_by(DeleteBatch.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalar(stmt)


def build_write_client(session: Session, batch: DeleteBatch) -> PeopleWriteClient:
    settings = get_settings()
    if settings.people_write_client != "google":
        return get_write_client("fake")
    account = session.get(Account, batch.account_id)  # pragma: no cover - integration env
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=crypto.decrypt(account.credential.enc_access_token),
        refresh_token=crypto.decrypt(account.credential.enc_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        # client_id/secret are REQUIRED to refresh the access token mid-run (long batches outlive
        # the ~1h token); without them google-auth raises RefreshError and the batch stalls.
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=account.granted_scopes.split() if account.granted_scopes else None,
    )
    return get_write_client("google", credentials=creds)


def run_once(session: Session) -> bool:
    batch = claim_next_batch(session)
    if batch is None:
        return False
    client = build_write_client(session, batch)
    if batch.status == "undoing":
        delete_batch_service.process_undo(session, batch.id, client)
    else:
        delete_batch_service.process_batch(session, batch.id, client)
    return True


def main() -> None:  # pragma: no cover - long-running loop
    configure_logging()
    logger.info("delete worker started (client=%s)", get_settings().people_write_client)
    while True:
        with SessionLocal() as session:
            try:
                worked = run_once(session)
            except Exception:  # noqa: BLE001 - keep worker alive
                logger.exception("delete batch iteration failed")
                worked = False
        if not worked:
            time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    main()
