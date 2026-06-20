"""Test fixtures. Uses SQLite so integration tests run without a live Postgres/Google."""
from __future__ import annotations

import os

# Configure secrets/URL BEFORE importing app modules (config is cached at first use).
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
if not os.environ.get("TOKEN_ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet

    os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.api.deps import get_oauth_provider  # noqa: E402
from src.api.main import create_app  # noqa: E402
from src.core.db import get_session  # noqa: E402
from src.models import Base  # noqa: E402
from src.services.oauth import OAuthResult  # noqa: E402


@pytest.fixture
def engine():
    # Set TEST_DATABASE_URL to a Postgres DSN to validate against the real datastore (JSONB,
    # UUID, bytea). Defaults to in-memory SQLite for fast, dependency-free runs.
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        eng = create_engine(test_url, future=True)
        Base.metadata.drop_all(eng)
        Base.metadata.create_all(eng)
        yield eng
        Base.metadata.drop_all(eng)
        eng.dispose()
    else:
        eng = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(eng)
        yield eng
        Base.metadata.drop_all(eng)


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@pytest.fixture
def db(Session):
    session = Session()
    try:
        yield session
    finally:
        session.close()


class FakeOAuthProvider:
    def __init__(self):
        self._next = OAuthResult(
            google_account_id="g-1",
            email="user1@example.com",
            refresh_token="refresh-1",
            access_token="access-1",
            expiry=None,
            scopes=["https://www.googleapis.com/auth/contacts.readonly"],
        )

    def set_result(self, result: OAuthResult) -> None:
        self._next = result

    def authorization_url(self, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/auth?state={state}"

    def exchange(self, code: str) -> OAuthResult:
        return self._next


@pytest.fixture
def oauth_provider():
    return FakeOAuthProvider()


@pytest.fixture
def client(Session, oauth_provider):
    app = create_app()
    app.state.oauth_provider = oauth_provider

    def _session_override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_oauth_provider] = lambda: oauth_provider
    with TestClient(app) as c:
        yield c
