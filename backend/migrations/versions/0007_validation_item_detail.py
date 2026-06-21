"""feature 006: validation_item.detail (granular human-readable reason)

Adds a specific reason string per queue item (e.g. "Domain does not exist" vs "Domain has no MX
record", or "TLS/SSL handshake failed" vs "Connection timed out") so the operator does not have to
re-check manually. `issue_type` stays the coarse category that drives the action set.

Revision ID: 0007_validation_item_detail
Revises: 0006_validation_total_count
Create Date: 2026-06-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_validation_item_detail"
down_revision = "0006_validation_total_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("validation_item", sa.Column("detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("validation_item", "detail")
