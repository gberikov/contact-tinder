"""Pydantic response/request schemas mirroring contracts/openapi.yaml.

NOTE: no schema exposes Credential/token fields (FR-002).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AccountOut(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    grantedScopes: list[str]
    createdAt: datetime


class SnapshotOut(BaseModel):
    id: uuid.UUID
    accountId: uuid.UUID
    accountEmail: str | None = None
    status: str
    source: str
    contactCount: int | None = None
    workingCopyCount: int = 0
    label: str | None = None
    createdAt: datetime
    finalizedAt: datetime | None = None


class ImportJobOut(BaseModel):
    snapshotId: uuid.UUID
    status: str
    fetchedCount: int
    totalEstimate: int | None = None
    lastError: str | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class WorkingCopyOut(BaseModel):
    id: uuid.UUID
    snapshotId: uuid.UUID
    label: str
    status: str
    contactCount: int | None = None
    createdAt: datetime


class ContactOut(BaseModel):
    id: uuid.UUID
    resourceName: str
    displayName: str | None = None
    primaryEmail: str | None = None
    primaryPhone: str | None = None
    payload: dict


class ContactPage(BaseModel):
    items: list[ContactOut]
    page: int
    pageSize: int
    total: int


class CreateBody(BaseModel):
    label: str | None = None
