"""Shared test helpers for seeding accounts and snapshots."""
from __future__ import annotations

from src.models.account import Account, Credential
from src.services import crypto, import_runner, snapshot_service
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
