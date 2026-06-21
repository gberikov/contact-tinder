"""Combined worker loop — runs import jobs, delete batches AND label batches in one process.

Keeps everything in the single existing `worker` container (no new service, research D10/feature 004
D6). Each poll claims at most one import job, one delete batch and one label batch with FOR UPDATE
SKIP LOCKED, so multiple worker replicas remain safe.
"""
from __future__ import annotations

import logging
import time

from src.core.db import SessionLocal
from src.core.logging import configure_logging
from src.workers import delete_worker, import_worker, label_worker

logger = logging.getLogger(__name__)


def main() -> None:  # pragma: no cover - long-running loop
    configure_logging()
    logger.info("combined worker started (import + delete + label)")
    while True:
        worked = False
        for name, run_once in (
            ("import", import_worker.run_once),
            ("delete", delete_worker.run_once),
            ("label", label_worker.run_once),
        ):
            with SessionLocal() as session:
                try:
                    worked = run_once(session) or worked
                except Exception:  # noqa: BLE001 - keep the worker alive
                    logger.exception("%s worker iteration failed", name)
        if not worked:
            time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    main()
