"""add alert dispatch delivery status fields

Revision ID: 20260428_01
Revises: 20260427_04
Create Date: 2026-04-28 10:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260428_01"
down_revision = "20260427_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_dispatches",
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'sent'")),
    )
    op.add_column("alert_dispatches", sa.Column("reason_code", sa.String(length=64), nullable=True))
    op.add_column(
        "alert_dispatches",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "alert_dispatches", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "alert_dispatches",
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_dispatches", "provider_message_id")
    op.drop_column("alert_dispatches", "delivered_at")
    op.drop_column("alert_dispatches", "attempt_count")
    op.drop_column("alert_dispatches", "reason_code")
    op.drop_column("alert_dispatches", "status")
