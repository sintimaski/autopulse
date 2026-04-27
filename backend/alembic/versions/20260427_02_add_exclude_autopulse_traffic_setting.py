"""add exclude autopulse traffic setting

Revision ID: 20260427_02
Revises: 20260427_01
Create Date: 2026-04-27 18:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_02"
down_revision = "20260427_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_ui_settings",
        sa.Column(
            "exclude_autopulse_traffic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_ui_settings", "exclude_autopulse_traffic")
