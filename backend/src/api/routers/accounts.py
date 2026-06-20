"""Accounts router: OAuth connect/callback, list, disconnect (US1, FR-001/002)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.api.deps import get_oauth_provider
from src.api.schemas import AccountOut
from src.core.config import get_settings
from src.core.db import get_session
from src.services import account_service
from src.services.oauth import OAuthProvider

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _to_out(account) -> AccountOut:
    return AccountOut(
        id=account.id,
        email=account.email,
        status=account.status,
        grantedScopes=account.granted_scopes.split() if account.granted_scopes else [],
        createdAt=account.created_at,
    )


@router.get("", response_model=list[AccountOut])
def list_accounts(session: Session = Depends(get_session)) -> list[AccountOut]:
    return [_to_out(a) for a in account_service.list_accounts(session)]


@router.post("/connect")
def connect(
    provider: OAuthProvider = Depends(get_oauth_provider),
) -> dict[str, str]:
    state = uuid.uuid4().hex
    return {"authorizationUrl": provider.authorization_url(state)}


@router.get("/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    provider: OAuthProvider = Depends(get_oauth_provider),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    result = provider.exchange(code)
    account_service.store_connection(session, result)
    session.commit()
    return RedirectResponse(url=f"{get_settings().frontend_url}/accounts", status_code=302)


@router.delete("/{account_id}", status_code=204)
def disconnect(account_id: uuid.UUID, session: Session = Depends(get_session)) -> None:
    account_service.disconnect(session, account_id)
    session.commit()
