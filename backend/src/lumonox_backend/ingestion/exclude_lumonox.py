"""Project UI setting: hide Lumonox internal HTTP traffic from analytics queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.models import Event, ProjectUiSettings

_LUMONOX_INTERNAL_PATH_PREFIXES: tuple[str, ...] = (
    "/lumonox",
    "/dashboard",
)
_LUMONOX_INTERNAL_PATH_EXACT: tuple[str, ...] = ("/ingest",)


def is_lumonox_internal_path(path: str | None) -> bool:
    if not isinstance(path, str):
        return False
    candidate = path.strip()
    if not candidate:
        return False
    if candidate in _LUMONOX_INTERNAL_PATH_EXACT:
        return True
    return any(
        candidate == prefix or candidate.startswith(f"{prefix}/")
        for prefix in _LUMONOX_INTERNAL_PATH_PREFIXES
    )


async def resolve_exclude_lumonox_traffic(session: AsyncSession, project_id: UUID) -> bool:
    setting = await session.scalar(
        select(ProjectUiSettings.exclude_lumonox_traffic).where(
            ProjectUiSettings.project_id == project_id
        )
    )
    if setting is None:
        return True
    return bool(setting)


def append_exclude_lumonox_event_filters(
    filters: list[ColumnElement[bool]],
    *,
    exclude_lumonox_traffic: bool,
) -> None:
    if not exclude_lumonox_traffic:
        return
    # Embedded mount: /lumonox/*. Standalone backend: dashboard API and ingest are often
    # recorded without that prefix (/dashboard/*, /ingest) when middleware sees root paths.
    internal = or_(
        Event.path == "/lumonox",
        Event.path.like("/lumonox/%"),
        Event.path == "/ingest",
        Event.path == "/dashboard",
        Event.path.like("/dashboard/%"),
    )
    filters.append(~internal)
