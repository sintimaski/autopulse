"""add error grouping expression index

Revision ID: 20260426_02
Revises: 20260426_01
Create Date: 2026-04-26 19:25:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260426_02"
down_revision = "20260426_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_project_error_hash
        ON events (project_id, ((payload ->> 'error_hash')))
        WHERE type = 'error'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_events_project_error_hash")
