"""T023 (US1) — auto-apply: E.164, mobile type, http→https as reversible StagedEdits + counts.

Idempotent re-run stages nothing new; the snapshot is never touched.
"""
from __future__ import annotations

from src.models.triage import StagedEdit
from src.models.validation import ValidationRun
from src.services import validation_service
from src.services.website_checker import WebsiteResult
from tests.helpers import seed_account, seed_working_copy


def _person(i: int, *, phones=None, emails=None, urls=None) -> dict:
    p: dict = {"resourceName": f"people/c{i}", "etag": f"e{i}",
               "names": [{"displayName": f"C{i}", "metadata": {"primary": True}}]}
    if phones:
        p["phoneNumbers"] = phones
    if emails:
        p["emailAddresses"] = emails
    if urls:
        p["urls"] = urls
    return p


def _fake_web(url, **_):
    if url.startswith("http://up."):
        return WebsiteResult(status="upgrade_https", final_url="https://up.example/")
    return WebsiteResult(status="ok")


def _run(db, wc):
    run = validation_service.start_run(db, wc.id, default_region="KZ")
    validation_service.run_validation_job(db, run.id, website_check=_fake_web)
    db.refresh(run)
    return run


def test_e164_mobile_type_and_https_upgrade(db):
    account = seed_account(db)
    people = [
        _person(0, phones=[{"value": "+7 (701) 722-15-02"}]),          # reformat + mobile type
        _person(1, urls=[{"value": "http://up.example/"}]),            # http→https
    ]
    wc = seed_working_copy(db, account, people)

    run = _run(db, wc)
    assert run.status == "completed"
    assert run.auto_applied_count >= 3  # e164 + mobile-type + https

    contacts = {c.payload["resourceName"]: c.payload for c in wc.contacts}
    assert contacts["people/c0"]["phoneNumbers"][0]["value"] == "+77017221502"
    assert contacts["people/c0"]["phoneNumbers"][0]["type"] == "mobile"
    assert contacts["people/c1"]["urls"][0]["value"] == "https://up.example/"

    edits = db.query(StagedEdit).filter_by(kind="normalize").all()
    assert len(edits) >= 3
    assert all(e.status == "active" for e in edits)


def test_rerun_is_idempotent(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [_person(0, phones=[{"value": "+7 (701) 722-15-02"}])])

    first = _run(db, wc)
    assert first.auto_applied_count >= 2

    second = _run(db, wc)
    # Already normalized — the second run stages nothing.
    assert second.auto_applied_count == 0


def test_snapshot_untouched(db):
    account = seed_account(db)
    wc = seed_working_copy(db, account, [_person(0, phones=[{"value": "+7 (701) 722-15-02"}])])
    snap_contact_before = wc.snapshot.contacts[0].payload["phoneNumbers"][0]["value"]
    _run(db, wc)
    db.refresh(wc.snapshot.contacts[0])
    assert wc.snapshot.contacts[0].payload["phoneNumbers"][0]["value"] == snap_contact_before
