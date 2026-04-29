"""add dashboard widget tables

Revision ID: 20260429_02
Revises: 20260429_01
Create Date: 2026-04-29 17:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260429_02"
down_revision = "20260429_01"
branch_labels = None
depends_on = None


def _uuid_type() -> sa.UUID:
    return sa.UUID()


def upgrade() -> None:
    op.create_table(
        "dashboard_widget_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", _uuid_type(), nullable=False),
        sa.Column("widget_id", sa.String(length=128), nullable=False),
        sa.Column("widget_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text())
            if op.get_bind().dialect.name == "postgresql"
            else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_widget_definitions_project_order",
        "dashboard_widget_definitions",
        ["project_id", "display_order"],
        unique=False,
    )
    op.create_index(
        "ux_dashboard_widget_definitions_project_widget_id",
        "dashboard_widget_definitions",
        ["project_id", "widget_id"],
        unique=True,
    )
    op.create_table(
        "dashboard_widget_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", _uuid_type(), nullable=False),
        sa.Column("widget_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dashboard_widget_points_project_timestamp",
        "dashboard_widget_points",
        ["project_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_widget_points_project_widget_id",
        "dashboard_widget_points",
        ["project_id", "widget_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_widget_points_project_widget_id", table_name="dashboard_widget_points"
    )
    op.drop_index(
        "ix_dashboard_widget_points_project_timestamp", table_name="dashboard_widget_points"
    )
    op.drop_table("dashboard_widget_points")
    op.drop_index(
        "ux_dashboard_widget_definitions_project_widget_id",
        table_name="dashboard_widget_definitions",
    )
    op.drop_index(
        "ix_dashboard_widget_definitions_project_order", table_name="dashboard_widget_definitions"
    )
    op.drop_table("dashboard_widget_definitions")
