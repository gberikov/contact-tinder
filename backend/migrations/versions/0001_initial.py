"""initial schema: accounts, snapshots, working copies, audit

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("google_account_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
        sa.Column("granted_scopes", sa.String(1024), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "credential",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("account.id", ondelete="CASCADE"),
                  unique=True),
        sa.Column("enc_refresh_token", sa.LargeBinary(), nullable=False),
        sa.Column("enc_access_token", sa.LargeBinary(), nullable=True),
        sa.Column("access_token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("key_id", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("account.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="importing"),
        sa.Column("source", sa.String(32), nullable=False, server_default="personal_connections"),
        sa.Column("contact_count", sa.Integer(), nullable=True),
        sa.Column("next_sync_token", sa.Text(), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "import_job",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("snapshot.id", ondelete="CASCADE"),
                  unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("page_token", sa.Text(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_estimate", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "snapshot_contact",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("snapshot.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("etag", sa.String(255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("display_name", sa.String(512), nullable=True),
        sa.Column("primary_email", sa.String(320), nullable=True),
        sa.Column("primary_phone", sa.String(64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("snapshot_id", "resource_name"),
    )
    op.create_index(
        "ix_snapshot_contact_snapshot_display",
        "snapshot_contact",
        ["snapshot_id", "display_name"],
    )
    op.create_table(
        "working_copy",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("snapshot.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="creating"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "working_copy_contact",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("working_copy_id", sa.Uuid(),
                  sa.ForeignKey("working_copy.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin_resource_name", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "audit_entry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False, server_default="operator"),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "audit_entry",
        "working_copy_contact",
        "working_copy",
        "snapshot_contact",
        "import_job",
        "snapshot",
        "credential",
        "account",
    ):
        op.drop_table(table)
