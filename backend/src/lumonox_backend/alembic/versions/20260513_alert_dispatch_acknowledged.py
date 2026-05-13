"""Add per-dispatch acknowledged_at and acknowledged_by_user_id to alert_dispatches.

Revision ID: alert_dispatch_acknowledged_20260513
Revises: dashboard_bookmark_visibility_20260512
Create Date: 2026-05-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "alert_dispatch_acknowledged_20260513"
down_revision = "dashboard_bookmark_visibility_20260512"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(text("ALTER TABLE alert_dispatches ADD COLUMN " "acknowledged_at TIMESTAMP"))
        op.execute(
            text("ALTER TABLE alert_dispatches ADD COLUMN " "acknowledged_by_user_id CHAR(36)")
        )
        return
    op.add_column(
        "alert_dispatches",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alert_dispatches",
        sa.Column("acknowledged_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(text("ALTER TABLE alert_dispatches DROP COLUMN acknowledged_by_user_id"))
        op.execute(text("ALTER TABLE alert_dispatches DROP COLUMN acknowledged_at"))
        return
    op.drop_column("alert_dispatches", "acknowledged_by_user_id")
    op.drop_column("alert_dispatches", "acknowledged_at")
