"""Shared test helpers for seeding accounts and snapshots."""
from __future__ import annotations

from src.models.account import Account, Credential
from src.services import crypto, import_runner, snapshot_service, working_copy_service
from tests.fakes.fake_people_client import FakePeopleClient, make_person


def seed_account(db, *, gid: str = "g-1", email: str = "user@example.com", status: str = "connected") -> Account:
    account = Account(google_account_id=gid, email=email, status=status,
                      granted_scopes="https://www.googleapis.com/auth/contacts.readonly")
    account.credential = Credential(
        enc_refresh_token=crypto.encrypt("refresh-token"),
        enc_access_token=crypto.encrypt("access-token"),
    )
    db.add(account)
    db.commit()
    return account


def seed_complete_snapshot(db, account, *, count: int = 5, full: bool = False, page_size: int = 2):
    people = [make_person(i, full=full) for i in range(count)]
    snapshot = snapshot_service.create_snapshot(db, account.id)
    client = FakePeopleClient(people, page_size=page_size)
    import_runner.run_import_job(db, snapshot.import_job.id, client, sleep=lambda _: None)
    db.refresh(snapshot)
    return snapshot


def dup_person(i: int, *, name: str, phone: str, email: str | None = None) -> dict:
    """A contact with explicit name/phone/email so duplicates can be controlled in dedup tests."""
    person = {
        "resourceName": f"people/c{i}",
        "etag": f"etag{i}",
        "names": [{"displayName": name, "givenName": name.split()[0],
                   "familyName": name.split()[-1], "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": phone, "metadata": {"primary": True}}],
    }
    if email:
        person["emailAddresses"] = [{"value": email, "metadata": {"primary": True}}]
    return person


def seed_working_copy(db, account, people: list[dict], *, label: str = "wc"):
    """Build a snapshot from `people`, then a ready working copy; returns the WorkingCopy."""
    snapshot = snapshot_service.create_snapshot(db, account.id)
    client = FakePeopleClient(people, page_size=max(1, len(people)))
    import_runner.run_import_job(db, snapshot.import_job.id, client, sleep=lambda _: None)
    return working_copy_service.create_working_copy(db, snapshot.id, label)
