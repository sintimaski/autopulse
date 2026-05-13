"""Add mute/snooze/ack fields to project alert settings.

Revision ID: project_alert_notification_controls_20260512
Revises: incident_shares_title_20260215
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "project_alert_notification_controls_20260512"
down_revision = "incident_shares_title_20260215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            text(
                "ALTER TABLE project_alert_settings ADD COLUMN "
                "notifications_muted BOOLEAN NOT NULL DEFAULT 0"
            )
        )
        op.execute(
            text(
                "ALTER TABLE project_alert_settings ADD COLUMN notifications_snoozed_until DATETIME"
            )
        )
        op.execute(
            text(
                "ALTER TABLE project_alert_settings ADD COLUMN "
                "last_notifications_acknowledged_at DATETIME"
            )
        )
        return
    op.add_column(
        "project_alert_settings",
        sa.Column(
            "notifications_muted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("notifications_snoozed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column(
            "last_notifications_acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.alter_column(
        "project_alert_settings",
        "notifications_muted",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            text(
                "ALTER TABLE project_alert_settings DROP COLUMN last_notifications_acknowledged_at"
            )
        )
        op.execute(
            text("ALTER TABLE project_alert_settings DROP COLUMN notifications_snoozed_until")
        )
        op.execute(text("ALTER TABLE project_alert_settings DROP COLUMN notifications_muted"))
        return
    op.drop_column("project_alert_settings", "last_notifications_acknowledged_at")
    op.drop_column("project_alert_settings", "notifications_snoozed_until")
    op.drop_column("project_alert_settings", "notifications_muted")
