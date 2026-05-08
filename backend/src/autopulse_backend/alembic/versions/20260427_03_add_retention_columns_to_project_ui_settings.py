"""add retention columns to project ui settings

Revision ID: 20260427_03
Revises: 20260427_02
Create Date: 2026-04-27 19:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_03"
down_revision = "20260427_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_ui_settings",
        sa.Column("retention_raw_events_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column(
            "logs_query_max_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1440"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_ui_settings", "logs_query_max_window_minutes")
    op.drop_column("project_ui_settings", "retention_raw_events_days")
