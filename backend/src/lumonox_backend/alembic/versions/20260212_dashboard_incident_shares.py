"""Add dashboard_incident_shares for DB-backed incident share URLs.

Revision ID: incident_shares_20260212
Revises: initial
Create Date: 2026-02-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "incident_shares_20260212"
down_revision = "initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_incident_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("scope_state", sa.JSON(), nullable=False),
        sa.Column("access_mode", sa.String(length=32), nullable=False),
        sa.Column("allowed_user_ids", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["dashboard_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_incident_shares_project_created",
        "dashboard_incident_shares",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_incident_shares_expires_at",
        "dashboard_incident_shares",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_incident_shares_expires_at", table_name="dashboard_incident_shares")
    op.drop_index(
        "ix_dashboard_incident_shares_project_created", table_name="dashboard_incident_shares"
    )
    op.drop_table("dashboard_incident_shares")
