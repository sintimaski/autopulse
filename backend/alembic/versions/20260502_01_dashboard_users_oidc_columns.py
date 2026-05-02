"""dashboard_users idp columns for OIDC linking

Revision ID: 20260502_01
Revises: 20260429_02
Create Date: 2026-05-02 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260502_01"
down_revision = "20260429_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboard_users",
        sa.Column("idp_provider", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "dashboard_users",
        sa.Column("idp_subject", sa.String(length=255), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "ux_dashboard_users_idp_provider_subject",
            "dashboard_users",
            ["idp_provider", "idp_subject"],
            unique=True,
            postgresql_where=sa.text("idp_provider IS NOT NULL AND idp_subject IS NOT NULL"),
        )
    else:
        op.create_index(
            "ux_dashboard_users_idp_provider_subject",
            "dashboard_users",
            ["idp_provider", "idp_subject"],
            unique=True,
            sqlite_where=sa.text("idp_provider IS NOT NULL AND idp_subject IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("ux_dashboard_users_idp_provider_subject", table_name="dashboard_users")
    op.drop_column("dashboard_users", "idp_subject")
    op.drop_column("dashboard_users", "idp_provider")
