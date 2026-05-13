"""Add alert_webhook_pacing for distributed (DB-coordinated) webhook send pacing.

Revision ID: alert_webhook_pacing_20260513
Revises: alert_dispatch_acknowledged_20260513
Create Date: 2026-05-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "alert_webhook_pacing_20260513"
down_revision = "alert_dispatch_acknowledged_20260513"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_webhook_pacing",
        sa.Column("webhook_key", sa.String(length=128), primary_key=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_webhook_pacing")
