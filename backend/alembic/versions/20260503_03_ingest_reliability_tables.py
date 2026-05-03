"""ingest idempotency keys and aggregate dead letters

Revision ID: 20260503_03
Revises: 20260503_02
Create Date: 2026-05-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260503_03"
down_revision = "20260503_02"
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
        "ingest_idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("accepted_events", sa.Integer(), nullable=True),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key_hash", name="ux_ingest_idempotency_project_key"),
    )
    op.create_index(
        "ix_ingest_idempotency_project_reserved",
        "ingest_idempotency_keys",
        ["project_id", "reserved_at"],
        unique=False,
    )
    op.create_table(
        "ingest_aggregate_dead_letters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("payload", json_t, nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingest_agg_dl_created",
        "ingest_aggregate_dead_letters",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_agg_dl_created", table_name="ingest_aggregate_dead_letters")
    op.drop_table("ingest_aggregate_dead_letters")
    op.drop_index("ix_ingest_idempotency_project_reserved", table_name="ingest_idempotency_keys")
    op.drop_table("ingest_idempotency_keys")
