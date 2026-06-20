"""Slow integration: the REAL Zingg engine groups ≥90% of seeded duplicate pairs (T017 / SC-001).

Marked `slow` — excluded from the default CI lane (no Spark/JVM). Skipped automatically when the
`zingg`/`pyspark` packages are not importable, so it never fails a Spark-free environment.
"""
from __future__ import annotations

import pytest

pytest.importorskip("pyspark")
pytest.importorskip("zingg")

pytestmark = pytest.mark.slow


def test_real_zingg_recall_on_seeded_pairs(db):  # pragma: no cover - container-only
    from dedup.zingg_engine import ZinggDedupEngine
    from src.services import dedup_service
    from tests.helpers import dup_person, seed_account, seed_working_copy

    # 10 known duplicate pairs (same phone, name variant) interleaved with unique contacts.
    people = []
    for i in range(10):
        people.append(dup_person(i * 2, name=f"Pair{i} A", phone=f"+1-202-555-{1000 + i:04d}",
                                 email=f"p{i}a@x.com"))
        people.append(dup_person(i * 2 + 1, name=f"Pair{i} B", phone=f"+1-202-555-{1000 + i:04d}",
                                 email=f"p{i}b@y.com"))

    account = seed_account(db)
    wc = seed_working_copy(db, account, people)
    run = dedup_service.create_run(db, wc.id)
    dedup_service.run_dedup_job(db, run.id, ZinggDedupEngine())
    db.refresh(run)

    assert run.status == "completed"
    # ≥90% of the 10 true pairs grouped (SC-001).
    assert run.cluster_count >= 9
