"""phase 5 retention, archive, and org foundations

Revision ID: 20260428_02
Revises: 20260428_01
Create Date: 2026-04-28 15:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260428_02"
down_revision = "20260428_01"
branch_labels = None
depends_on = None


def _uuid_type() -> sa.UUID:
    return sa.UUID()


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", _uuid_type(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "archived_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("original_event_id", sa.Integer(), nullable=False),
        sa.Column("project_id", _uuid_type(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text())
            if op.get_bind().dialect.name == "postgresql"
            else sa.JSON(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_archived_events_project_archived_at",
        "archived_events",
        ["project_id", "archived_at"],
        unique=False,
    )
    op.create_index(
        "ix_archived_events_original_event_id",
        "archived_events",
        ["original_event_id"],
        unique=False,
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", _uuid_type(), nullable=False),
        sa.Column("organization_id", _uuid_type(), nullable=False),
        sa.Column("user_id", _uuid_type(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default=sa.text("'member'")),
        sa.Column("invited_email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["dashboard_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_memberships_org_user",
        "organization_memberships",
        ["organization_id", "user_id"],
        unique=True,
    )
    op.create_table(
        "governance_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", _uuid_type(), nullable=True),
        sa.Column("actor_user_id", _uuid_type(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text())
            if op.get_bind().dialect.name == "postgresql"
            else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["dashboard_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_audit_org_created_at",
        "governance_audit_events",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.add_column("projects", sa.Column("organization_id", _uuid_type(), nullable=True))
    op.create_foreign_key(
        "fk_projects_organization_id",
        "projects",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], unique=False)

    op.add_column(
        "dashboard_sessions",
        sa.Column("organization_id", _uuid_type(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dashboard_sessions_organization_id",
        "dashboard_sessions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "project_ui_settings",
        sa.Column(
            "retention_plan",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column(
            "archival_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column(
            "archival_mode",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'db_archive'"),
        ),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column(
            "archival_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'idle'"),
        ),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column("archival_last_success_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_ui_settings",
        sa.Column("archival_last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_ui_settings", "archival_last_error")
    op.drop_column("project_ui_settings", "archival_last_success_at")
    op.drop_column("project_ui_settings", "archival_status")
    op.drop_column("project_ui_settings", "archival_mode")
    op.drop_column("project_ui_settings", "archival_enabled")
    op.drop_column("project_ui_settings", "retention_plan")

    op.drop_constraint(
        "fk_dashboard_sessions_organization_id", "dashboard_sessions", type_="foreignkey"
    )
    op.drop_column("dashboard_sessions", "organization_id")

    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_constraint("fk_projects_organization_id", "projects", type_="foreignkey")
    op.drop_column("projects", "organization_id")

    op.drop_index("ix_governance_audit_org_created_at", table_name="governance_audit_events")
    op.drop_table("governance_audit_events")
    op.drop_index("ix_org_memberships_org_user", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_index("ix_archived_events_original_event_id", table_name="archived_events")
    op.drop_index("ix_archived_events_project_archived_at", table_name="archived_events")
    op.drop_table("archived_events")
    op.drop_table("organizations")
