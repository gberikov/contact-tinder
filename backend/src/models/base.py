"""Declarative base and shared column types (cross-dialect: Postgres + SQLite)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

# jsonb on Postgres, json on SQLite — same Python interface.
JsonB = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_ts() -> Mapped[datetime]:
    # Python-side default gives microsecond precision on every backend (stable ordering).
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
