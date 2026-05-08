"""add sqlite rotation limits to project ui settings

Revision ID: 20260429_01
Revises: 20260428_02
Create Date: 2026-04-29 16:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260429_01"
down_revision = "20260428_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_ui_settings",
        sa.Column("retention_max_db_size_mb", sa.Integer(), nullable=True),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column("retention_max_log_rows", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_ui_settings", "retention_max_log_rows")
    op.drop_column("project_ui_settings", "retention_max_db_size_mb")
