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
        ):
            raise
        alter_statements = [
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN exclude_autopulse_traffic BOOLEAN NOT NULL DEFAULT 1",
            "ALTER TABLE project_ui_settings "
            "ADD COLUMN logs_query_max_window_minutes INTEGER NOT NULL DEFAULT 1440",
            "ALTER TABLE project_ui_settings ADD COLUMN retention_raw_events_days INTEGER NULL",
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
