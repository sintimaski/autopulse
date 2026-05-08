"""add alerting and retention tables

Revision ID: 20260426_03
Revises: 20260426_02
Create Date: 2026-04-26 22:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260426_03"
down_revision = "20260426_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if op.get_bind().dialect.name == "postgresql"
        else sa.JSON()
    )
    op.create_table(
        "project_alert_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("destination_email", sa.String(length=320), nullable=True),
        sa.Column(
            "error_spike_ratio_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.4"),
        ),
        sa.Column(
            "error_spike_min_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("20"),
        ),
        sa.Column(
            "error_spike_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column(
            "outage_min_requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "outage_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("last_error_spike_alert_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outage_alert_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )

    op.create_table(
        "alert_dispatches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("destination_email", sa.String(length=320), nullable=True),
        sa.Column(
            "delivered_via",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'stub'"),
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", json_type, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_dispatches_project_triggered_at",
        "alert_dispatches",
        ["project_id", "triggered_at"],
        unique=False,
    )
    op.create_index(
        "ix_alert_dispatches_project_type_triggered_at",
        "alert_dispatches",
        ["project_id", "alert_type", "triggered_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alert_dispatches_project_type_triggered_at", table_name="alert_dispatches")
    op.drop_index("ix_alert_dispatches_project_triggered_at", table_name="alert_dispatches")
    op.drop_table("alert_dispatches")
    op.drop_table("project_alert_settings")
