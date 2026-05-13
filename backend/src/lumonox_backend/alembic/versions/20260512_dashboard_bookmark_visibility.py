"""Add project visibility to dashboard user bookmarks.

Revision ID: dashboard_bookmark_visibility_20260512
Revises: project_alert_notification_controls_20260512
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "dashboard_bookmark_visibility_20260512"
down_revision = "project_alert_notification_controls_20260512"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            text(
                "ALTER TABLE dashboard_user_bookmarks ADD COLUMN "
                "visibility VARCHAR(16) NOT NULL DEFAULT 'private'"
            )
        )
        return
    op.add_column(
        "dashboard_user_bookmarks",
        sa.Column(
            "visibility",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'private'"),
        ),
    )
    op.alter_column("dashboard_user_bookmarks", "visibility", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(text("ALTER TABLE dashboard_user_bookmarks DROP COLUMN visibility"))
        return
    op.drop_column("dashboard_user_bookmarks", "visibility")
