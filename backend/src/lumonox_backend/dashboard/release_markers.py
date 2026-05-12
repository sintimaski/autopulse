from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumonox_backend.models import Event
from lumonox_backend.schemas.dashboard_overview_models import DashboardReleaseMarker


async def fetch_release_markers_for_event_filters(
    session: AsyncSession,
    *,
    dialect_name: str,
    filters: list[Any],
) -> list[DashboardReleaseMarker]:
    """Distinct (release, git_sha) pairs with the earliest timestamp in the window.

    ``dialect_name`` is ``session.bind.dialect.name`` (``sqlite`` vs ``postgresql``).
    """
    if dialect_name == "postgresql":
        rel = Event.payload["release"].as_string()
        sha_raw = Event.payload["git_sha"].as_string()
    else:
        rel = cast(func.json_extract(Event.payload, "$.release"), String)
        sha_raw = cast(func.json_extract(Event.payload, "$.git_sha"), String)
    sha = func.nullif(func.trim(sha_raw), "")

    stmt = (
        select(func.min(Event.timestamp), rel, sha)
        .where(*filters)
        .group_by(rel, sha)
        .having(rel.is_not(None))
        .having(func.length(func.trim(cast(rel, String))) > 0)
        .order_by(func.min(Event.timestamp))
        .limit(40)
    )
    rows = (await session.execute(stmt)).all()
    out: list[DashboardReleaseMarker] = []
    for ts, rel_v, sha_v in rows:
        if ts is None or rel_v is None:
            continue
        rel_s = str(rel_v).strip()[:200]
        if not rel_s:
            continue
        git_s = str(sha_v).strip()[:120] if sha_v is not None and str(sha_v).strip() else None
        out.append(DashboardReleaseMarker(at=ts, release=rel_s, git_sha=git_s))
    return out
