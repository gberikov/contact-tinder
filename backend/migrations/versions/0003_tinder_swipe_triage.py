"""feature 003: triage sessions/decisions, processing items, staged edits, delete batches/records

Revision ID: 0003_tinder_swipe_triage
Revises: 0002_zingg_dedup
Create Date: 2026-06-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_tinder_swipe_triage"
down_revision = "0002_zingg_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "triage_session",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dedup_run_id",
            sa.Uuid(),
            sa.ForeignKey("dedup_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    # D11: at most one in-progress session per working copy.
    op.create_index(
        "uq_triage_session_active_per_copy",
        "triage_session",
        ["working_copy_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )

    op.create_table(
        "triage_decision",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("triage_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "working_copy_contact_id"),
    )
    op.create_index(
        "ix_triage_decision_session_outcome", "triage_decision", ["session_id", "outcome"]
    )

    op.create_table(
        "processing_item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("triage_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("wants_edit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("wants_transliterate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_id", "working_copy_contact_id"),
    )
    op.create_index(
        "ix_processing_item_session_status", "processing_item", ["session_id", "status"]
    )

    op.create_table(
        "staged_edit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("payload_before", postgresql.JSONB(), nullable=False),
        sa.Column("payload_after", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_staged_edit_wcc_status", "staged_edit", ["working_copy_contact_id", "status"]
    )

    op.create_table(
        "delete_batch",
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
        sa.Column("status", sa.String(16), nullable=False, server_default="staged"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("previewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_delete_batch_copy_status", "delete_batch", ["working_copy_id", "status"])

    op.create_table(
        "deletion_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "delete_batch_id",
            sa.Uuid(),
            sa.ForeignKey("delete_batch.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("origin_resource_name", sa.String(255), nullable=False),
        sa.Column("payload_before", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("google_result", postgresql.JSONB(), nullable=True),
        sa.Column("restored_resource_name", sa.String(255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("delete_batch_id", "origin_resource_name"),
    )


def downgrade() -> None:
    op.drop_table("deletion_record")
    op.drop_index("ix_delete_batch_copy_status", table_name="delete_batch")
    op.drop_table("delete_batch")
    op.drop_index("ix_staged_edit_wcc_status", table_name="staged_edit")
    op.drop_table("staged_edit")
    op.drop_index("ix_processing_item_session_status", table_name="processing_item")
    op.drop_table("processing_item")
    op.drop_index("ix_triage_decision_session_outcome", table_name="triage_decision")
    op.drop_table("triage_decision")
    op.drop_index("uq_triage_session_active_per_copy", table_name="triage_session")
    op.drop_table("triage_session")
