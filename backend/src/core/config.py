"""Application configuration loaded from environment (Principle I: secrets via env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/contacttinder"

    # Google OAuth (read-only contacts scope only — Principle I, FR-001)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/accounts/callback"
    google_scopes: tuple[str, ...] = ("https://www.googleapis.com/auth/contacts.readonly",)

    # Token encryption at rest (FR-002)
    token_encryption_key: str = ""

    # Where to send the browser back after the OAuth callback completes.
    frontend_url: str = "http://localhost:5173"

    # Import behavior
    import_max_attempts: int = 5
    import_page_size: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()
