"""feature 002: dedup runs, clusters, members, merge records + working_copy_contact.status

Revision ID: 0002_zingg_dedup
Revises: 0001_initial
Create Date: 2026-06-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_zingg_dedup"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "working_copy_contact",
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
    )
    op.create_index(
        "ix_wcc_copy_status", "working_copy_contact", ["working_copy_id", "status"]
    )

    op.create_table(
        "dedup_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("confidence_floor", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cluster_count", sa.Integer(), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    # FR-007: at most one active run per working copy.
    op.create_index(
        "uq_dedup_run_active_per_copy",
        "dedup_run",
        ["working_copy_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
    )

    op.create_table(
        "duplicate_cluster",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dedup_run_id",
            sa.Uuid(),
            sa.ForeignKey("dedup_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("z_cluster_key", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("min_score", sa.Float(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_cluster_run_status_conf",
        "duplicate_cluster",
        ["dedup_run_id", "status", "confidence"],
    )

    op.create_table(
        "cluster_member",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Uuid(),
            sa.ForeignKey("duplicate_cluster.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "working_copy_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("is_survivor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("cluster_id", "working_copy_contact_id"),
    )
    op.create_index("ix_cluster_member_wcc", "cluster_member", ["working_copy_contact_id"])

    op.create_table(
        "merge_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Uuid(),
            sa.ForeignKey("duplicate_cluster.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "working_copy_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "survivor_contact_id",
            sa.Uuid(),
            sa.ForeignKey("working_copy_contact.id"),
            nullable=False,
        ),
        sa.Column("survivor_payload_before", postgresql.JSONB(), nullable=False),
        sa.Column("merged_payload", postgresql.JSONB(), nullable=False),
        sa.Column("retired_member_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("merge_record")
    op.drop_index("ix_cluster_member_wcc", table_name="cluster_member")
    op.drop_table("cluster_member")
    op.drop_index("ix_cluster_run_status_conf", table_name="duplicate_cluster")
    op.drop_table("duplicate_cluster")
    op.drop_index("uq_dedup_run_active_per_copy", table_name="dedup_run")
    op.drop_table("dedup_run")
    op.drop_index("ix_wcc_copy_status", table_name="working_copy_contact")
    op.drop_column("working_copy_contact", "status")
