"""feature 006: validation_run.total_count (progress bar)

Adds a denominator for the Tidy progress bar — the total number of field values (phones + emails +
websites) to check across the kept set, in the same unit as `checked_count`.

Revision ID: 0006_validation_total_count
Revises: 0005_validate_normalize
Create Date: 2026-06-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_validation_total_count"
down_revision = "0005_validate_normalize"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_run",
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("validation_run", "total_count")
