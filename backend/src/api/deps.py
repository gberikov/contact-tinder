"""Shared FastAPI dependencies (session, OAuth provider seam)."""
from __future__ import annotations

from fastapi import Request

from src.services.oauth import GoogleOAuthProvider, OAuthProvider


def get_oauth_provider(request: Request) -> OAuthProvider:
    provider = getattr(request.app.state, "oauth_provider", None)
    if provider is None:
        provider = GoogleOAuthProvider()
        request.app.state.oauth_provider = provider
    return provider
