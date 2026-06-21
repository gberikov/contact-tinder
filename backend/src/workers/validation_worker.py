"""Validation (Tidy) worker (feature 006).

Claims a queued/running ValidationRun with FOR UPDATE SKIP LOCKED (PostgreSQL stays the only queue,
mirroring dedup/import/delete/label) and drives it to terminal state via `validation_service`. A
restart re-claims an in-flight run and resumes it. Website checks are time-limited per request
(`website_check_timeout_seconds`) so a run always terminates regardless of slow/blocking sites.

`_website_check` is a module seam so tests inject a network-free check.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db import SessionLocal
from src.core.logging import configure_logging
from src.models.validation import ValidationRun
from src.services import validation_service, website_checker

logger = logging.getLogger(__name__)
_ACTIVE = ("queued", "running")
_website_check = website_checker.check


def claim_next_run(session: Session) -> ValidationRun | None:
    stmt = (
        select(ValidationRun)
        .where(ValidationRun.status.in_(_ACTIVE))
        .order_by(ValidationRun.started_at.is_(None).desc(), ValidationRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalar(stmt)


def run_once(session: Session) -> bool:
    run = claim_next_run(session)
    if run is None:
        return False
    validation_service.run_validation_job(session, run.id, website_check=_website_check)
    return True


def main() -> None:  # pragma: no cover - long-running loop
    configure_logging()
    logger.info("validation worker started")
    while True:
        session = SessionLocal()
        try:
            did_work = run_once(session)
        except Exception:  # noqa: BLE001 - keep the worker alive
            logger.exception("validation worker iteration failed")
            did_work = False
        finally:
            session.close()
        if not did_work:
            time.sleep(2.0)


if __name__ == "__main__":  # pragma: no cover
    main()
