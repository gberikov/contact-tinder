"""OAuth seam — isolates Google token exchange so it can be faked in tests (Principle IV)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.core.config import get_settings

# Google may return extra granted scopes (e.g. via include_granted_scopes); relax oauthlib's
# strict scope-equality check so the token exchange doesn't raise on a harmless scope change.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


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
    def exchange(self, code: str, state: str) -> OAuthResult: ...


class GoogleOAuthProvider:
    """Real provider backed by google-auth-oauthlib + the People API `people/me` profile."""

    def __init__(self) -> None:
        # PKCE code_verifier per state — generated at authorization_url, reused at exchange.
        self._verifiers: dict[str, str | None] = {}

    def _flow(self, code_verifier: str | None = None):
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
            code_verifier=code_verifier,
        )

    def authorization_url(self, state: str) -> str:  # pragma: no cover - needs google env
        flow = self._flow()
        url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent", state=state
        )
        # Persist the PKCE verifier so the callback can complete the exchange.
        self._verifiers[state] = flow.code_verifier
        return url

    def exchange(self, code: str, state: str) -> OAuthResult:  # pragma: no cover - needs google env
        from google.auth.transport.requests import AuthorizedSession

        flow = self._flow(code_verifier=self._verifiers.pop(state, None))
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Read the account's stable id (sub) and email from the OIDC userinfo endpoint.
        # This needs only openid+email (not the broader People `profile` scope).
        session = AuthorizedSession(creds)
        resp = session.get("https://openidconnect.googleapis.com/v1/userinfo", timeout=10)
        resp.raise_for_status()
        info = resp.json()
        email = info.get("email", "")
        account_id = info.get("sub") or email

        return OAuthResult(
            google_account_id=account_id,
            email=email,
            refresh_token=creds.refresh_token,
            access_token=creds.token,
            expiry=creds.expiry,
            scopes=list(creds.scopes or get_settings().google_scopes),
        )
