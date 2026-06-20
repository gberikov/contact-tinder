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
    # contacts.readonly = the feature; openid+email = identify which account a snapshot
    # belongs to (FR-018). All read-only; no write/delete scope is ever requested.
    google_scopes: tuple[str, ...] = (
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/contacts.readonly",
    )

    # Token encryption at rest (FR-002)
    token_encryption_key: str = ""

    # Where to send the browser back after the OAuth callback completes.
    frontend_url: str = "http://localhost:5173"

    # Import behavior
    import_max_attempts: int = 5
    import_page_size: int = 1000

    # Deduplication (feature 002). The real Zingg/Spark engine runs only in the `dedup` container;
    # CI and the backend default to the Spark-free fake engine.
    dedup_engine: str = "fake"  # fake | zingg
    dedup_model_version: str = "contacts-v1"
    dedup_confidence_floor: float = 0.5  # precision-favouring default (research D5)
    dedup_num_partitions: int = 8  # Spark local-mode tuning (research D9)
    # JDBC connection the Zingg engine uses to read input / write match output (research D3).
    dedup_jdbc_url: str = ""
    dedup_jdbc_user: str = ""
    dedup_jdbc_password: str = ""
    dedup_zingg_dir: str = "/app/dedup/model"
    dedup_model_id: str = "100"
    # NOTE: there is intentionally no merge-undo retention/expiry setting — merges are undoable for
    # the life of the working copy (research D6); undo is gated only by the MergeRecord existing.

    # Swipe triage (feature 003). The real Google write path runs only behind the PeopleWriteClient
    # seam; CI and the backend default to the Google-free fake write client.
    people_write_client: str = "fake"  # fake | google
    # Deleting contacts in Google requires the read-WRITE contacts scope. Google offers no delete-only
    # scope, so this is the narrowest that works (research D8/D9). It is requested ONLY via incremental
    # consent when the operator enables deletion — it is deliberately NOT in `google_scopes` above.
    google_contacts_write_scope: str = "https://www.googleapis.com/auth/contacts"
    # NOTE: like merge-undo, staged-edit and delete undo have NO timed expiry — they are reversible for
    # the life of the working copy (research D12). Do not add an expiry knob without an amendment.


@lru_cache
def get_settings() -> Settings:
    return Settings()
