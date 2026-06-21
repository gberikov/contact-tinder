"""feature 006: validation_run, validation_item

Adds the Validate & Normalize (Tidy) tables. Auto-fixes and queue resolutions reuse feature 003's
staged_edit (kind widened to include "normalize" — no DDL, the column is already String(16)); no
existing table is altered.

Revision ID: 0005_validate_normalize
Revises: 0004_google_contacts_export
Create Date: 2026-06-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_validate_normalize"
down_revision = "0004_google_contacts_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("triage_session.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("default_region", sa.String(2), nullable=True),
        sa.Column("checked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_applied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_validation_run_copy_status", "validation_run", ["working_copy_id", "status"]
    )

    op.create_table(
        "validation_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "validation_run_id",
            sa.Uuid(),
            sa.ForeignKey("validation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_kind", sa.String(8), nullable=False),
        sa.Column("field_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issue_type", sa.String(24), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=False),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("resolution", postgresql.JSONB(), nullable=True),
        sa.Column(
            "staged_edit_id",
            sa.Uuid(),
            sa.ForeignKey("staged_edit.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_validation_item_run_status", "validation_item", ["validation_run_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_validation_item_run_status", table_name="validation_item")
    op.drop_table("validation_item")
    op.drop_index("ix_validation_run_copy_status", table_name="validation_run")
    op.drop_table("validation_run")
