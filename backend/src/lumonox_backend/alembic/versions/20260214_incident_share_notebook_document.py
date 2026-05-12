"""Add notebook_document JSON to incident shares (full notebook snapshot).

Revision ID: incident_share_notebook_20260214
Revises: incident_shares_20260212
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "incident_share_notebook_20260214"
down_revision = "incident_shares_20260212"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboard_incident_shares",
        sa.Column("notebook_document", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dashboard_incident_shares", "notebook_document")
