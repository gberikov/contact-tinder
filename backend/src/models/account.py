"""Account (Google connection) and Credential (encrypted tokens, never serialized)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from src.models.base import Base, created_ts, uuid_pk


class Account(Base):
    __tablename__ = "account"

    id: Mapped[uuid.UUID] = uuid_pk()
    google_account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # connected | needs_reauth | revoked
    status: Mapped[str] = mapped_column(String(32), default="connected", nullable=False)
    granted_scopes: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    created_at: Mapped[datetime] = created_ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    credential: Mapped["Credential"] = relationship(
        back_populates="account", uselist=False, cascade="all, delete-orphan"
    )


class Credential(Base):
    """Secret. MUST NOT be serialized into any API response/log/export (FR-002)."""

    __tablename__ = "credential"

    id: Mapped[uuid.UUID] = uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), unique=True
    )
    enc_refresh_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enc_access_token: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    key_id: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    created_at: Mapped[datetime] = created_ts()

    account: Mapped[Account] = relationship(back_populates="credential")
