from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

import duckdb

from autopulse_backend.config import Settings, get_settings
from autopulse_backend.dashboard.log_query import parse_log_query


@dataclass(frozen=True, slots=True)
class EventStoreFilters:
    project_id: UUID
    from_timestamp: datetime
    to_timestamp: datetime
    method: str | None = None
    status_class: int | None = None
    path_contains: str | None = None
    environments: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    exclude_autopulse_traffic: bool = False
    event_sql_filter: str | None = None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_duckdb_timestamp(value: datetime) -> str:
    return _as_utc(value).strftime("%Y-%m-%d %H:%M:%S.%f")


class DuckDbEventStore:
    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._path))
        self._lock = Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id BIGINT PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                received_at TIMESTAMP NOT NULL,
                sdk_version VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                service_name VARCHAR NOT NULL,
                environment VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                path VARCHAR NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms DOUBLE NOT NULL,
                payload JSON NOT NULL,
                request_id VARCHAR
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboard_widget_points (
                id BIGINT PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                widget_id VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                label VARCHAR,
                value DOUBLE NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_events_project_timestamp "
            "ON events(project_id, timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_widget_points_project_timestamp "
            "ON dashboard_widget_points(project_id, timestamp)"
        )

    def insert_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        values = [
            (
                idx,
                row["project_id"],
                _as_duckdb_timestamp(row["timestamp"]),
                _as_duckdb_timestamp(row["received_at"]),
                row["sdk_version"],
                row["type"],
                row["service_name"],
                row["environment"],
                row["method"],
                row["path"],
                int(row["status_code"]),
                float(row["latency_ms"]),
                json.dumps(row["payload"]),
                row["request_id"],
            )
            for idx, row in enumerate(rows, start=self._next_id())
        ]
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO events (
                    id, project_id, timestamp, received_at, sdk_version, type,
                    service_name, environment, method, path, status_code,
                    latency_ms, payload, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    def _next_id(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM events").fetchone()
        return int(row[0] if row else 1)

    def _next_widget_point_id(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM dashboard_widget_points"
            ).fetchone()
        return int(row[0] if row else 1)

    def insert_widget_points(self, points: list[dict[str, object]]) -> None:
        if not points:
            return
        values = []
        for idx, point in enumerate(points, start=self._next_widget_point_id()):
            widget_id = point.get("widget_id")
            timestamp = point.get("timestamp")
            value = point.get("value")
            project_id = point.get("project_id")
            if (
                not isinstance(widget_id, str)
                or not isinstance(timestamp, datetime)
                or not isinstance(value, int | float)
                or project_id is None
            ):
                continue
            label = point.get("label")
            values.append(
                (
                    idx,
                    str(project_id),
                    widget_id,
                    _as_duckdb_timestamp(timestamp),
                    label if isinstance(label, str) else None,
                    float(value),
                )
            )
        if not values:
            return
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO dashboard_widget_points (
                    id, project_id, widget_id, timestamp, label, value
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    def list_widget_points(
        self, *, project_id: UUID, from_timestamp: datetime, to_timestamp: datetime
    ) -> list[tuple[str, datetime, str | None, float]]:
        with self._lock:
            return self._conn.execute(
                """
                SELECT widget_id, timestamp, label, value
                FROM dashboard_widget_points
                WHERE project_id = ?
                  AND timestamp >= CAST(? AS TIMESTAMP)
                  AND timestamp <= CAST(? AS TIMESTAMP)
                ORDER BY timestamp ASC, id ASC
                """,
                [
                    str(project_id),
                    _as_duckdb_timestamp(from_timestamp),
                    _as_duckdb_timestamp(to_timestamp),
                ],
            ).fetchall()

    def _compile_filters(self, filters: EventStoreFilters) -> tuple[str, list[Any]]:
        clauses = [
            "project_id = ?",
            "timestamp >= CAST(? AS TIMESTAMP)",
            "timestamp <= CAST(? AS TIMESTAMP)",
        ]
        params: list[Any] = [
            str(filters.project_id),
            _as_duckdb_timestamp(filters.from_timestamp),
            _as_duckdb_timestamp(filters.to_timestamp),
        ]
        if filters.exclude_autopulse_traffic:
            clauses.append("path NOT LIKE '/autopulse/%'")
        if filters.method:
            clauses.append("method = ?")
            params.append(filters.method.upper())
        if filters.status_class is not None:
            lower = filters.status_class * 100
            clauses.append("status_code >= ? AND status_code < ?")
            params.extend([lower, lower + 100])
        if filters.path_contains and filters.path_contains.strip():
            clauses.append("lower(path) LIKE ?")
            params.append(f"%{filters.path_contains.strip().lower()}%")
        if filters.environments:
            placeholders = ",".join("?" for _ in filters.environments)
            clauses.append(f"environment IN ({placeholders})")
            params.extend(filters.environments)
        if filters.services:
            placeholders = ",".join("?" for _ in filters.services)
            clauses.append(f"service_name IN ({placeholders})")
            params.extend(filters.services)
        if filters.min_latency_ms is not None:
            clauses.append("latency_ms >= ?")
            params.append(filters.min_latency_ms)
        if filters.max_latency_ms is not None:
            clauses.append("latency_ms <= ?")
            params.append(filters.max_latency_ms)
        if filters.event_sql_filter and filters.event_sql_filter.strip():
            wrapped = (
                "SELECT * FROM events WHERE "
                f"{filters.event_sql_filter.strip()} "  # nosec B608
                "ORDER BY timestamp DESC LIMIT 100"
            )
            parsed = parse_log_query(wrapped)
            for clause in parsed.where_clauses:
                clauses.append(self._translate_supported_where(clause, params))
        return " AND ".join(f"({clause})" for clause in clauses), params

    def _translate_supported_where(self, clause: str, params: list[Any]) -> str:
        lower = clause.lower()
        if lower.startswith("method = '") and clause.endswith("'"):
            params.append(clause.split("'")[1].upper())
            return "method = ?"
        if lower.startswith("environment = '") and clause.endswith("'"):
            params.append(clause.split("'")[1])
            return "environment = ?"
        if lower.startswith("service_name = '") and clause.endswith("'"):
            params.append(clause.split("'")[1])
            return "service_name = ?"
        if lower.startswith("path like '") and clause.endswith("'"):
            params.append(clause.split("'")[1])
            return "path LIKE ?"
        if lower.startswith("status_code >="):
            params.append(int(clause.split(">=")[1].strip()))
            return "status_code >= ?"
        if lower.startswith("status_code <="):
            params.append(int(clause.split("<=")[1].strip()))
            return "status_code <= ?"
        if lower.startswith("latency_ms >="):
            params.append(float(clause.split(">=")[1].strip()))
            return "latency_ms >= ?"
        if lower.startswith("latency_ms <="):
            params.append(float(clause.split("<=")[1].strip()))
            return "latency_ms <= ?"
        raise ValueError(f"Unsupported WHERE clause fragment: '{clause}'")

    def fetch_events(
        self,
        filters: EventStoreFilters,
        *,
        columns: str = (
            "id, timestamp, method, path, status_code, latency_ms, "
            "service_name, environment, request_id, type, payload"
        ),
        order_by: str = "timestamp DESC, id DESC",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[tuple[Any, ...]]:
        where_sql, params = self._compile_filters(filters)
        sql = f"SELECT {columns} FROM events WHERE {where_sql} ORDER BY {order_by}"  # nosec B608
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        if offset:
            sql += " OFFSET ?"
            params.append(offset)
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def count_events(self, filters: EventStoreFilters) -> int:
        where_sql, params = self._compile_filters(filters)
        with self._lock:
            result = self._conn.execute(
                f"SELECT COUNT(*) FROM events WHERE {where_sql}",  # nosec B608
                params,
            ).fetchone()
        return int(result[0] if result else 0)

    def delete_events_before(self, *, cutoff: datetime, project_id: UUID | None = None) -> int:
        sql = "DELETE FROM events WHERE received_at < ?"
        params: list[Any] = [_as_duckdb_timestamp(cutoff)]
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(str(project_id))
        with self._lock:
            count_predicate = sql.removeprefix("DELETE FROM events WHERE ")
            deleted = self._conn.execute(
                f"SELECT COUNT(*) FROM events WHERE {count_predicate}",  # nosec B608
                params,
            ).fetchone()
            self._conn.execute(sql, params)
        return int(deleted[0] if deleted else 0)

    def max_timestamp(self) -> datetime | None:
        with self._lock:
            row = self._conn.execute("SELECT MAX(timestamp) FROM events").fetchone()
        value = row[0] if row else None
        if value is None:
            return None
        return _as_utc(value)

    def file_size_bytes(self) -> int:
        total = 0
        for path in (self._path, Path(f"{self._path}.wal")):
            try:
                total += int(path.stat().st_size)
            except OSError:
                continue
        return total

    def checkpoint(self) -> None:
        with self._lock:
            self._conn.execute("CHECKPOINT")

    def list_project_ids(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT project_id FROM events ORDER BY project_id ASC"
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0] is not None]

    def count_events_for_project(self, project_id: UUID | None = None) -> int:
        if project_id is None:
            with self._lock:
                row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return int(row[0] if row else 0)
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE project_id = ?",
                [str(project_id)],
            ).fetchone()
        return int(row[0] if row else 0)

    def delete_oldest_events(self, *, rows_to_delete: int, project_id: UUID | None = None) -> int:
        if rows_to_delete <= 0:
            return 0
        if project_id is None:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM events ORDER BY received_at ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM events WHERE id IN ("
                "SELECT id FROM events ORDER BY received_at ASC, id ASC LIMIT ?"
                ")"
            )
            params = [rows_to_delete]
        else:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM events WHERE project_id = ? "
                "ORDER BY received_at ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM events WHERE id IN ("
                "SELECT id FROM events WHERE project_id = ? "
                "ORDER BY received_at ASC, id ASC LIMIT ?"
                ")"
            )
            params = [str(project_id), rows_to_delete]
        with self._lock:
            deleted_row = self._conn.execute(count_sql, params).fetchone()
            deleted = int(deleted_row[0] if deleted_row else 0)
            if deleted > 0:
                self._conn.execute(delete_sql, params)
        return deleted


_duckdb_store: DuckDbEventStore | None = None
_duckdb_store_lock = Lock()


def event_store_enabled(settings: Settings | None = None) -> bool:
    resolved = settings if settings is not None else get_settings()
    return resolved.event_store == "duckdb"


def get_duckdb_event_store() -> DuckDbEventStore:
    global _duckdb_store
    if _duckdb_store is not None:
        return _duckdb_store
    with _duckdb_store_lock:
        if _duckdb_store is None:
            _duckdb_store = DuckDbEventStore(get_settings().event_store_duckdb_path)
    return _duckdb_store


def try_get_duckdb_event_store() -> DuckDbEventStore | None:
    try:
        return get_duckdb_event_store()
    except duckdb.IOException:
        return None


async def insert_events_duckdb(rows: list[dict[str, Any]]) -> None:
    if not event_store_enabled():
        return
    store = get_duckdb_event_store()
    await asyncio.to_thread(store.insert_rows, rows)
