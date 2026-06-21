"""Account lifecycle: store encrypted connections, list, disconnect, re-auth flagging."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.models.account import Account, Credential
from src.services import crypto
from src.services.oauth import OAuthResult


def store_connection(session: Session, result: OAuthResult) -> Account:
    """Create or update a connection, storing tokens encrypted at rest (FR-002)."""
    account = session.scalar(
        select(Account).where(Account.google_account_id == result.google_account_id)
    )
    if account is None:
        account = Account(google_account_id=result.google_account_id, email=result.email)
        session.add(account)
        session.flush()

    account.email = result.email
    account.status = "connected"
    account.granted_scopes = " ".join(result.scopes)

    if account.credential is None:
        account.credential = Credential(
            account_id=account.id,
            enc_refresh_token=crypto.encrypt(result.refresh_token),
            enc_access_token=crypto.encrypt(result.access_token),
            access_token_expiry=result.expiry,
            key_id=crypto.KEY_ID,
        )
    else:
        account.credential.enc_refresh_token = crypto.encrypt(result.refresh_token)
        account.credential.enc_access_token = crypto.encrypt(result.access_token)
        account.credential.access_token_expiry = result.expiry
    session.flush()
    return account


def list_accounts(session: Session) -> list[Account]:
    return list(session.scalars(select(Account).order_by(Account.created_at)))


def get_account(session: Session, account_id: uuid.UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise NotFoundError("account not found")
    return account


def disconnect(session: Session, account_id: uuid.UUID) -> None:
    account = get_account(session, account_id)
    # Cascade: delete the account's snapshots (and their drafts/derived data) first so the
    # snapshot RESTRICT child constraint is satisfied (Connect cleanup).
    from src.models.snapshot import Snapshot
    from src.services import snapshot_service

    # NOTE: cascade commits per child (per existing pattern), so a mid-cascade failure can leave a
    # partially-deleted subtree. Accepted for this single-operator tool; atomic-subtree delete is a follow-up.
    for sid in session.scalars(
        select(Snapshot.id).where(Snapshot.account_id == account_id)
    ).all():
        snapshot_service.delete_snapshot(session, sid, confirm=True)

    account = get_account(session, account_id)  # re-fetch after child commits
    session.delete(account)
    session.flush()


def mark_needs_reauth(session: Session, account_id: uuid.UUID) -> None:
    account = session.get(Account, account_id)
    if account is not None:
        account.status = "needs_reauth"
        session.flush()
