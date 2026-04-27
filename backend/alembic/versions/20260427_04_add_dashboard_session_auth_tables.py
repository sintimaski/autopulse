"""add dashboard session auth tables

Revision ID: 20260427_04
Revises: 20260427_03
Create Date: 2026-04-27 21:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_04"
down_revision = "20260427_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dashboard_users_email", "dashboard_users", ["email"], unique=True)

    op.create_table(
        "dashboard_magic_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_dashboard_magic_links_email_created_at",
        "dashboard_magic_links",
        ["email", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_magic_links_expires_at",
        "dashboard_magic_links",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "dashboard_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["dashboard_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_dashboard_sessions_expires_at",
        "dashboard_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_sessions_user_created_at",
        "dashboard_sessions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_sessions_user_created_at", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_expires_at", table_name="dashboard_sessions")
    op.drop_table("dashboard_sessions")

    op.drop_index("ix_dashboard_magic_links_expires_at", table_name="dashboard_magic_links")
    op.drop_index("ix_dashboard_magic_links_email_created_at", table_name="dashboard_magic_links")
    op.drop_table("dashboard_magic_links")

    op.drop_index("ix_dashboard_users_email", table_name="dashboard_users")
    op.drop_table("dashboard_users")
