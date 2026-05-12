"""Add title and updated_at to incident share rows (saved incidents list).

Revision ID: incident_shares_title_20260215
Revises: incident_share_notebook_20260214
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "incident_shares_title_20260215"
down_revision = "incident_share_notebook_20260214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # Avoid batch_alter_table: it reflects the table and breaks `alembic upgrade --sql`.
        op.execute(text("ALTER TABLE dashboard_incident_shares ADD COLUMN title VARCHAR(200)"))
        op.execute(
            text(
                "ALTER TABLE dashboard_incident_shares ADD COLUMN updated_at "
                "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
        )
        return
    op.add_column(
        "dashboard_incident_shares", sa.Column("title", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "dashboard_incident_shares",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(text("ALTER TABLE dashboard_incident_shares DROP COLUMN updated_at"))
        op.execute(text("ALTER TABLE dashboard_incident_shares DROP COLUMN title"))
        return
    op.drop_column("dashboard_incident_shares", "updated_at")
    op.drop_column("dashboard_incident_shares", "title")
