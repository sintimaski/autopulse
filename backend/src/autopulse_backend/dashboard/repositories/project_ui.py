from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.models import ProjectUiSettings


async def get_or_create_project_ui_settings(
    session: AsyncSession,
    project_id,
) -> ProjectUiSettings:
    try:
        settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project_id)
        )
    except OperationalError as exc:
        # SQLite local dev path uses create_all and may lag model columns.
        error_text = str(exc)
        if (
            "project_ui_settings.exclude_autopulse_traffic" not in error_text
            and "project_ui_settings.logs_query_max_window_minutes" not in error_text
            and "project_ui_settings.retention_raw_events_days" not in error_text
            and "project_ui_settings.retention_max_db_size_mb" not in error_text
            and "project_ui_settings.retention_max_log_rows" not in error_text
            and "project_ui_settings.retention_plan" not in error_text
            and "project_ui_settings.archival_enabled" not in error_text
            and "project_ui_settings.archival_mode" not in error_text
            and "project_ui_settings.archival_status" not in error_text
            and "project_ui_settings.archival_last_success_at" not in error_text
            and "project_ui_settings.archival_last_error" not in error_text
        ):
            raise
        alter_statements = [
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN exclude_autopulse_traffic BOOLEAN NOT NULL DEFAULT 1",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN logs_query_max_window_minutes INTEGER NOT NULL DEFAULT 1440",
            "ALTER TABLE project_ui_settings ADD COLUMN retention_raw_events_days INTEGER NULL",
            "ALTER TABLE project_ui_settings ADD COLUMN retention_max_db_size_mb INTEGER NULL",
            "ALTER TABLE project_ui_settings ADD COLUMN retention_max_log_rows INTEGER NULL",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN retention_plan VARCHAR(32) NOT NULL DEFAULT 'standard'",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN archival_enabled BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN archival_mode VARCHAR(32) NOT NULL DEFAULT 'db_archive'",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN archival_status VARCHAR(16) NOT NULL DEFAULT 'idle'",
            "ALTER TABLE project_ui_settings " "ADD COLUMN archival_last_success_at DATETIME NULL",
            "ALTER TABLE project_ui_settings ADD COLUMN archival_last_error TEXT NULL",
        ]
        for statement in alter_statements:
            try:
                await session.execute(text(statement))
            except OperationalError as migration_exc:
                # Column already exists or dialect-specific duplicate-column error.
                duplicate_column_markers = (
                    "duplicate column name",
                    "already exists",
                )
                if not any(
                    marker in str(migration_exc).lower() for marker in duplicate_column_markers
                ):
                    raise
        await session.commit()
        settings = await session.scalar(
            select(ProjectUiSettings).where(ProjectUiSettings.project_id == project_id)
        )
    if settings is not None:
        return settings
    settings = ProjectUiSettings(project_id=project_id, theme_preference="system")
    session.add(settings)
    await session.flush()
    return settings
