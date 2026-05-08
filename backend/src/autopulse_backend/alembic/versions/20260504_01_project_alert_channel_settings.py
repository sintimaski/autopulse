"""add per-project alert delivery channel settings

Revision ID: 20260504_01
Revises: 20260503_03
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260504_01"
down_revision = "20260503_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_alert_settings",
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("slack_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("slack_webhook_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("discord_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("discord_webhook_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "project_alert_settings",
        sa.Column("webhook_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_alert_settings", "webhook_url")
    op.drop_column("project_alert_settings", "webhook_enabled")
    op.drop_column("project_alert_settings", "discord_webhook_url")
    op.drop_column("project_alert_settings", "discord_enabled")
    op.drop_column("project_alert_settings", "slack_webhook_url")
    op.drop_column("project_alert_settings", "slack_enabled")
    op.drop_column("project_alert_settings", "email_enabled")
