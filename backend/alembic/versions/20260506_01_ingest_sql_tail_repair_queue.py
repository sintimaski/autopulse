"""ingest sql-tail repair queue

Revision ID: 20260506_01
Revises: 20260505_01
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260506_01"
down_revision = "20260505_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_t = _json_type()
    op.create_table(
        "ingest_sql_tail_repair_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("payload", json_t, nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingest_sql_tail_repair_pending",
        "ingest_sql_tail_repair_items",
        ["resolved_at", "dead_lettered_at", "next_retry_at"],
        unique=False,
    )
    op.create_index(
        "ix_ingest_sql_tail_repair_project_created",
        "ingest_sql_tail_repair_items",
        ["project_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingest_sql_tail_repair_project_created",
        table_name="ingest_sql_tail_repair_items",
    )
    op.drop_index("ix_ingest_sql_tail_repair_pending", table_name="ingest_sql_tail_repair_items")
    op.drop_table("ingest_sql_tail_repair_items")
