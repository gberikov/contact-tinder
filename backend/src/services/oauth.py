"""OAuth seam — isolates Google token exchange so it can be faked in tests (Principle IV)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.core.config import get_settings


@dataclass
class OAuthResult:
    google_account_id: str
    email: str
    refresh_token: str
    access_token: str | None
    expiry: datetime | None
    scopes: list[str]


class OAuthProvider(Protocol):
    def authorization_url(self, state: str) -> str: ...
    def exchange(self, code: str) -> OAuthResult: ...


class GoogleOAuthProvider:
    """Real provider backed by google-auth-oauthlib + the People API `people/me` profile."""

    def _flow(self):
        from google_auth_oauthlib.flow import Flow

        s = get_settings()
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": s.google_oauth_client_id,
                    "client_secret": s.google_oauth_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [s.google_oauth_redirect_uri],
                }
            },
            scopes=list(s.google_scopes),
            redirect_uri=s.google_oauth_redirect_uri,
        )

    def authorization_url(self, state: str) -> str:  # pragma: no cover - needs google env
        flow = self._flow()
        url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent", state=state
        )
        return url

    def exchange(self, code: str) -> OAuthResult:  # pragma: no cover - needs google env
        from googleapiclient.discovery import build

        flow = self._flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        service = build("people", "v1", credentials=creds, cache_discovery=False)
        me = (
            service.people()
            .get(resourceName="people/me", personFields="emailAddresses,metadata,names")
            .execute()
        )
        email = (me.get("emailAddresses") or [{}])[0].get("value", "")
        account_id = ((me.get("metadata") or {}).get("sources") or [{}])[0].get("id", email)
        return OAuthResult(
            google_account_id=account_id,
            email=email,
            refresh_token=creds.refresh_token,
            access_token=creds.token,
            expiry=creds.expiry,
            scopes=list(creds.scopes or get_settings().google_scopes),
        )
