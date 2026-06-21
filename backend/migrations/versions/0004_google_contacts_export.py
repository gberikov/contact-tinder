"""feature 004: export_run, label_batch, label_assignment, contact_label

Adds the export-to-Google orchestration tables. The delete half reuses feature 003's
delete_batch/deletion_record unchanged — no existing table is altered.

Revision ID: 0004_google_contacts_export
Revises: 0003_tinder_swipe_triage
Create Date: 2026-06-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_google_contacts_export"
down_revision = "0003_tinder_swipe_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_label",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False, server_default="Process"),
        sa.Column("group_resource_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "name"),
    )

    op.create_table(
        "label_batch",
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
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contact_label_id",
            sa.Uuid(),
            sa.ForeignKey("contact_label.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="staged"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("labeled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_label_batch_copy_status", "label_batch", ["working_copy_id", "status"])

    op.create_table(
        "label_assignment",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "label_batch_id",
            sa.Uuid(),
            sa.ForeignKey("label_batch.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("origin_resource_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("google_result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("label_batch_id", "origin_resource_name"),
    )

    op.create_table(
        "export_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("triage_session.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "delete_batch_id",
            sa.Uuid(),
            sa.ForeignKey("delete_batch.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "label_batch_id",
            sa.Uuid(),
            sa.ForeignKey("label_batch.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="previewing"),
        sa.Column("undecided_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_export_run_copy_status", "export_run", ["working_copy_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_export_run_copy_status", table_name="export_run")
    op.drop_table("export_run")
    op.drop_table("label_assignment")
    op.drop_index("ix_label_batch_copy_status", table_name="label_batch")
    op.drop_table("label_batch")
    op.drop_table("contact_label")
