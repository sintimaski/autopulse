from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from autopulse_backend.core.config import Settings, normalize_database_url
from autopulse_backend.maintenance.retention_constants import (
    _SQLITE_SHRINK_BATCH,
    _SQLITE_SHRINK_MAX_ITERATIONS,
)
from autopulse_backend.maintenance.retention_deletes import (
    _delete_oldest_events_global_batch,
    _delete_oldest_project_events,
    _sqlite_pressure_delete_auxiliary_batch,
)
from autopulse_backend.models import Event, ProjectUiSettings


def _resolve_sqlite_db_path(database_url: str) -> Path | None:
    """Resolve the SQLite file path for retention size checks (matches engine URL normalization)."""
    normalized = normalize_database_url(database_url.strip())
    if not normalized.startswith("sqlite"):
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return None
    raw_path = unquote(parsed.path or "")
    if normalized.endswith(":memory:") or raw_path == ":memory:":
        return None
    if not raw_path:
        return None
    # `normalize_database_url` rewrites to an absolute path; URLs often appear as sqlite://///abs/path.
    if raw_path.startswith("//"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/./") or raw_path.startswith("/../"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/") and parsed.netloc:
        return Path(raw_path).resolve()
    if raw_path.startswith("/") and not parsed.netloc:
        return Path(raw_path).resolve()
    return Path(raw_path).resolve()


def _sqlite_db_disk_footprint_bytes(db_path: Path) -> int:
    """Bytes on disk for the DB file plus WAL/SHM sidecars (WAL mode)."""
    if not db_path.exists():
        return 0
    base = str(db_path)
    total = 0
    for path in (db_path, Path(base + "-wal"), Path(base + "-shm")):
        if path.exists():
            total += int(path.stat().st_size)
    return total


def _vacuum_sqlite_db_file(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    # Keep VACUUM fail-fast under contention; never block runtime/shutdown for minutes.
    try:
        with sqlite3.connect(str(db_path), timeout=2.0) as connection:
            connection.execute("PRAGMA busy_timeout=2000")
            with suppress(sqlite3.OperationalError):
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
        return db_path.stat().st_size
    except sqlite3.OperationalError:
        # If DB is busy, skip this pass and retry on the next scheduled tick.
        return db_path.stat().st_size if db_path.exists() else 0


async def _sqlite_shrink_under_size_cap(
    *,
    session: AsyncSession,
    sqlite_db_path: Path,
    max_bytes: int,
    project_id: UUID | None,
) -> int:
    """Delete oldest rows (per-project or globally) plus auxiliary tables until file fits cap."""
    deleted_total = 0
    stall_rounds = 0
    max_batch = _SQLITE_SHRINK_BATCH
    for _ in range(_SQLITE_SHRINK_MAX_ITERATIONS):
        try:
            current_size = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
        except OSError:
            break
        if current_size <= max_bytes:
            break
        over_ratio = max(0.0, float(current_size - max_bytes) / float(max(current_size, 1)))
        # Keep newest data close to the cap: use smaller batches when only slightly over cap.
        batch = max(200, min(max_batch, int(max_batch * max(over_ratio, 0.05))))

        if project_id is not None:
            deleted_now = await _delete_oldest_project_events(
                session=session,
                project_id=project_id,
                rows_to_delete=batch,
            )
        else:
            deleted_now = await _delete_oldest_events_global_batch(
                session=session,
                rows_to_delete=batch,
            )
        if deleted_now > 0:
            deleted_total += deleted_now
            await session.commit()
            _vacuum_sqlite_db_file(sqlite_db_path)
            try:
                current_after_delete = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
            except OSError:
                break
            if current_after_delete <= max_bytes:
                break
            stall_rounds = 0
            continue

        aux_deleted = await _sqlite_pressure_delete_auxiliary_batch(
            session=session,
            rows_to_delete=batch,
        )
        if aux_deleted > 0:
            deleted_total += aux_deleted
            await session.commit()
            _vacuum_sqlite_db_file(sqlite_db_path)
            try:
                current_after_aux = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
            except OSError:
                break
            if current_after_aux <= max_bytes:
                break
            stall_rounds = 0
            continue

        _vacuum_sqlite_db_file(sqlite_db_path)
        try:
            current_after = _sqlite_db_disk_footprint_bytes(sqlite_db_path)
        except OSError:
            break
        if current_after <= max_bytes:
            break
        stall_rounds += 1
        if stall_rounds >= 3:
            break

    if deleted_total > 0:
        _vacuum_sqlite_db_file(sqlite_db_path)
    return deleted_total


async def _apply_project_rotation_limits(
    *,
    session: AsyncSession,
    settings: Settings,
) -> int:
    sqlite_db_path = _resolve_sqlite_db_path(settings.database_url)
    if sqlite_db_path is None:
        return 0

    rotation_settings = (
        await session.execute(
            select(
                ProjectUiSettings.project_id,
                ProjectUiSettings.retention_max_db_size_mb,
                ProjectUiSettings.retention_max_log_rows,
            ).where(
                ProjectUiSettings.retention_max_db_size_mb.is_not(None)
                | ProjectUiSettings.retention_max_log_rows.is_not(None)
            )
        )
    ).all()
    if not rotation_settings:
        return 0

    deleted_total = 0
    for project_id, max_db_size_mb, max_log_rows in rotation_settings:
        if max_log_rows is not None:
            count_result = await session.execute(
                select(func.count(Event.id)).where(Event.project_id == project_id)
            )
            project_count = int(count_result.scalar_one())
            overflow = max(0, project_count - int(max_log_rows))
            deleted_total += await _delete_oldest_project_events(
                session=session,
                project_id=project_id,
                rows_to_delete=overflow,
            )

        if max_db_size_mb is not None:
            max_size_bytes = int(max_db_size_mb) * 1024 * 1024
            deleted_total += await _sqlite_shrink_under_size_cap(
                session=session,
                sqlite_db_path=sqlite_db_path,
                max_bytes=max_size_bytes,
                project_id=project_id,
            )

    return deleted_total


async def _apply_sqlite_global_file_cap(
    *,
    session: AsyncSession,
    settings: Settings,
    cap_mb: int,
) -> int:
    """Enforce a maximum SQLite **file** size under storage pressure.

    Ingest also grows aggregate and widget tables; they can dominate file size even when
    raw `events` rows are few. After trimming oldest events globally, we trim oldest rows
    from dashboard widget points, per-minute metric buckets, archived events, error group
    aggregates, ingest rate-limit windows, and alert dispatches until the file fits the
    cap (or nothing left to delete).
    """
    sqlite_db_path = _resolve_sqlite_db_path(settings.database_url)
    if sqlite_db_path is None:
        return 0
    max_bytes = int(cap_mb) * 1024 * 1024
    return await _sqlite_shrink_under_size_cap(
        session=session,
        sqlite_db_path=sqlite_db_path,
        max_bytes=max_bytes,
        project_id=None,
    )
