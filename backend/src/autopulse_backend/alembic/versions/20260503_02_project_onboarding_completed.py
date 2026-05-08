"""projects.onboarding_completed for dashboard gate

Revision ID: 20260503_02
Revises: 20260503_01
Create Date: 2026-05-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260503_02"
down_revision = "20260503_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("UPDATE projects SET onboarding_completed = TRUE"))
    else:
        op.execute(sa.text("UPDATE projects SET onboarding_completed = 1"))


def downgrade() -> None:
    op.drop_column("projects", "onboarding_completed")
