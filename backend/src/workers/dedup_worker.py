"""PostgreSQL-backed dedup worker (research D1).

Claims queued/running DedupRun rows with FOR UPDATE SKIP LOCKED (PostgreSQL stays the only
datastore — no Redis), resolves the configured DedupEngine, and runs the job to terminal state.
A restart resumes an in-flight run by re-claiming it. The default engine is the Spark-free fake;
set DEDUP_ENGINE=zingg in the dedup container to use the real Spark/Zingg engine.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.db import SessionLocal
from src.core.logging import configure_logging
from src.integrations.dedup_engine import get_engine
from src.models.dedup import DedupRun
from src.services import dedup_service

logger = logging.getLogger(__name__)
_ACTIVE = ("queued", "running")


def claim_next_run(session: Session) -> DedupRun | None:
    stmt = (
        select(DedupRun)
        .where(DedupRun.status.in_(_ACTIVE))
        .order_by(DedupRun.started_at.is_(None).desc(), DedupRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalar(stmt)


def run_once(session: Session) -> bool:
    run = claim_next_run(session)
    if run is None:
        return False
    engine = get_engine(get_settings().dedup_engine)
    dedup_service.run_dedup_job(session, run.id, engine)
    return True


def main() -> None:  # pragma: no cover - long-running loop
    configure_logging()
    logger.info("dedup worker started (engine=%s)", get_settings().dedup_engine)
    while True:
        session = SessionLocal()
        try:
            did_work = run_once(session)
        except Exception:  # noqa: BLE001
            logger.exception("dedup worker iteration failed")
            did_work = False
        finally:
            session.close()
        if not did_work:
            time.sleep(2.0)


if __name__ == "__main__":  # pragma: no cover
    main()
