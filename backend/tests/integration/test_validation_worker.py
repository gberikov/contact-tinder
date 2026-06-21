"""T025 (US1) — the worker claims a queued ValidationRun and drives it to completed."""
from __future__ import annotations

from src.services import validation_service
from src.services.website_checker import WebsiteResult
from src.workers import validation_worker
from tests.helpers import seed_account, seed_working_copy


def test_worker_claims_and_completes(db, monkeypatch):
    # Avoid any real network from the worker's default website check.
    monkeypatch.setattr(
        validation_worker, "_website_check",
        lambda url, **_: WebsiteResult(status="reachable", final_url=url),
        raising=False,
    )
    account = seed_account(db)
    wc = seed_working_copy(db, account, [{
        "resourceName": "people/c0", "etag": "e0",
        "names": [{"displayName": "C0", "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": "+7 (701) 722-15-02"}],
    }])
    run = validation_service.start_run(db, wc.id, default_region="KZ")
    assert run.status == "queued"

    did = validation_worker.run_once(db)
    assert did is True
    db.refresh(run)
    assert run.status == "completed"
    assert run.auto_applied_count >= 2

    # nothing left to claim
    assert validation_worker.run_once(db) is False
