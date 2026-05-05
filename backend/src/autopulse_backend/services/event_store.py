from __future__ import annotations

import json
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from threading import Lock, local
from typing import Any, cast
from uuid import UUID

import duckdb

from autopulse_backend.core.config import Settings, get_settings
from autopulse_backend.dashboard.log_query import parse_log_query
from autopulse_backend.dashboard.payload_limits import MAX_DASHBOARD_WIDGET_POINTS_RETURNED
from autopulse_backend.services.duckdb_async import run_duckdb_write_sync


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
    #: When True (default), dashboard aggregations only include HTTP-shaped rows.
    http_events_only: bool = True
    #: If set, restricts to these ``type`` values (``http_events_only`` is ignored).
    require_event_types: tuple[str, ...] | None = None
    #: When True, rows match the window if either ``timestamp`` or ``received_at`` falls
    #: inside ``[from_timestamp, to_timestamp]``. Used by trace explorer so OTLP spans
    #: with stale or synthetic clock times still appear after ingest.
    include_received_at_in_time_window: bool = False


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_duckdb_timestamp(value: datetime) -> str:
    return _as_utc(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def _duckdb_connect_config() -> dict[str, Any]:
    """Per-connection DuckDB settings (see DuckDB configuration / pragmas docs)."""
    cfg: dict[str, Any] = {}
    raw_threads = getenv("AUTOPULSE_DUCKDB_THREADS")
    if raw_threads and raw_threads.strip():
        try:
            threads = max(1, min(int(raw_threads.strip()), 128))
            cfg["threads"] = str(threads)
        except ValueError:
            pass
    raw_mem = getenv("AUTOPULSE_DUCKDB_MEMORY_LIMIT")
    if raw_mem and raw_mem.strip():
        cfg["memory_limit"] = raw_mem.strip()
    return cfg


class DuckDbEventStore:
    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _cfg = _duckdb_connect_config()
        self._connect_config = _cfg
        self._write_conn = self._open_connection(str(self._path), _cfg)
        self._write_lock = Lock()
        self._read_local = local()
        self._read_conn_init_lock = Lock()
        self._read_connections: list[Any] = []
        self._read_connections_lock = Lock()
        self._ensure_schema()

    def _open_connection(self, path: str, config: dict[str, Any]) -> Any:
        attempts = int(getenv("AUTOPULSE_DUCKDB_CONNECT_RETRIES", "16").strip() or "16")
        attempts = max(1, min(attempts, 64))
        base_delay_s = float(
            getenv("AUTOPULSE_DUCKDB_CONNECT_RETRY_BASE_S", "0.08").strip() or "0.08"
        )
        base_delay_s = max(0.01, min(base_delay_s, 2.0))
        last: duckdb.IOException | None = None
        for attempt in range(attempts):
            try:
                return duckdb.connect(path, config=config)
            except duckdb.IOException as exc:
                last = exc
                msg = str(exc).lower()
                if "lock" not in msg and "conflicting" not in msg:
                    raise
                if attempt + 1 >= attempts:
                    break
                time.sleep(min(base_delay_s * (2 ** min(attempt, 8)), 3.0))
        assert last is not None
        raise last

    def _get_thread_read_connection(self) -> Any:
        """Return a dedicated connection for SELECTs on the executor pool.

        Uses the same connect config as the writer. SELECTs skip ``_write_lock``
        so parallel dashboard reads are not serialized on the ingest connection.
        """
        existing = getattr(self._read_local, "conn", None)
        if existing is not None:
            return existing
        with self._read_conn_init_lock:
            existing = getattr(self._read_local, "conn", None)
            if existing is not None:
                return existing
            conn = self._open_connection(str(self._path), self._connect_config)
            self._read_local.conn = conn
            with self._read_connections_lock:
                self._read_connections.append(conn)
            return conn

    def close(self) -> None:
        with self._write_lock, suppress(Exception):
            self._write_conn.close()
        with self._read_connections_lock:
            for read_conn in self._read_connections:
                with suppress(Exception):
                    read_conn.close()
            self._read_connections.clear()

    def _fetchall_read(self, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
        params_list = params or []
        conn = self._get_thread_read_connection()
        return cast(
            list[tuple[Any, ...]],
            conn.execute(sql, params_list).fetchall(),
        )

    def _fetchone_read(self, sql: str, params: list[Any] | None = None) -> tuple[Any, ...] | None:
        params_list = params or []
        conn = self._get_thread_read_connection()
        return cast(
            tuple[Any, ...] | None,
            conn.execute(sql, params_list).fetchone(),
        )

    def _query_with_columns_read(
        self, sql: str, params: list[Any] | None = None
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        params_list = params or []
        conn = self._get_thread_read_connection()
        cursor = conn.execute(sql, params_list)
        description = cursor.description or []
        columns = [str(col[0]) for col in description]
        rows = cast(list[tuple[Any, ...]], cursor.fetchall())
        return columns, rows

    def ping_sync(self) -> None:
        """Synchronous health probe for readiness checks (uses the writer connection)."""
        with self._write_lock:
            self._write_conn.execute("SELECT 1")

    def _ensure_schema(self) -> None:
        self._write_conn.execute(
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
        self._write_conn.execute(
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
        self._write_conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_events_project_timestamp "
            "ON events(project_id, timestamp)"
        )
        self._write_conn.execute(
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
        with self._write_lock:
            self._write_conn.executemany(
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
        with self._write_lock:
            row = self._write_conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM events").fetchone()
        return int(row[0] if row else 1)

    def _next_widget_point_id(self) -> int:
        with self._write_lock:
            row = self._write_conn.execute(
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
        with self._write_lock:
            self._write_conn.executemany(
                """
                INSERT INTO dashboard_widget_points (
                    id, project_id, widget_id, timestamp, label, value
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    def list_widget_points(
        self,
        *,
        project_id: UUID,
        from_timestamp: datetime,
        to_timestamp: datetime,
        max_rows: int | None = None,
    ) -> list[tuple[str, datetime, str | None, float]]:
        cap = int(max_rows) if max_rows is not None else MAX_DASHBOARD_WIDGET_POINTS_RETURNED
        cap = max(100, min(cap, 50_000))
        return self._fetchall_read(
            """
            SELECT widget_id, timestamp, label, value
            FROM (
                SELECT widget_id, timestamp, label, value
                FROM dashboard_widget_points
                WHERE project_id = ?
                  AND timestamp >= CAST(? AS TIMESTAMP)
                  AND timestamp <= CAST(? AS TIMESTAMP)
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            ) AS newest
            ORDER BY timestamp ASC, widget_id ASC
            """,
            [
                str(project_id),
                _as_duckdb_timestamp(from_timestamp),
                _as_duckdb_timestamp(to_timestamp),
                cap,
            ],
        )

    def _compile_filters(self, filters: EventStoreFilters) -> tuple[str, list[Any]]:
        clauses = ["project_id = ?"]
        params: list[Any] = [str(filters.project_id)]
        from_ts = _as_duckdb_timestamp(filters.from_timestamp)
        to_ts = _as_duckdb_timestamp(filters.to_timestamp)
        if filters.include_received_at_in_time_window:
            clauses.append(
                "("
                "(timestamp >= CAST(? AS TIMESTAMP) AND timestamp <= CAST(? AS TIMESTAMP))"
                " OR "
                "(received_at >= CAST(? AS TIMESTAMP) AND received_at <= CAST(? AS TIMESTAMP))"
                ")"
            )
            params.extend([from_ts, to_ts, from_ts, to_ts])
        else:
            clauses.append("timestamp >= CAST(? AS TIMESTAMP)")
            clauses.append("timestamp <= CAST(? AS TIMESTAMP)")
            params.extend([from_ts, to_ts])
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
        if filters.require_event_types:
            placeholders = ",".join("?" for _ in filters.require_event_types)
            clauses.append(f"type IN ({placeholders})")
            params.extend(filters.require_event_types)
        elif filters.http_events_only:
            clauses.append("type IN ('request', 'error')")
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
        return self._fetchall_read(sql, params)

    def query_events_sql(
        self,
        filters: EventStoreFilters,
        *,
        select_sql: str,
        suffix_sql: str = "",
        extra_params: list[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        where_sql, params = self._compile_filters(filters)
        sql = f"SELECT {select_sql} FROM events WHERE {where_sql} {suffix_sql}"  # nosec B608
        if extra_params:
            params.extend(extra_params)
        return self._fetchall_read(sql, params)

    def query_scoped_events_sql(
        self,
        filters: EventStoreFilters,
        query_sql: str,
        max_rows: int,
        extra_params: list[Any] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        where_sql, params = self._compile_filters(filters)
        sql = (
            f"WITH scoped_events AS MATERIALIZED ("
            f"SELECT * FROM events WHERE {where_sql}"
            f") SELECT * FROM ({query_sql}) AS user_query LIMIT ?"  # nosec B608
        )
        if extra_params:
            params.extend(extra_params)
        params.append(max_rows)
        return self._query_with_columns_read(sql, params)

    def fetch_events_with_total(
        self,
        filters: EventStoreFilters,
        *,
        columns: str | None = None,
        slim_payload: bool = False,
        order_by: str = "timestamp DESC, id DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[tuple[Any, ...]]]:
        if slim_payload:
            resolved_columns = (
                "id, timestamp, method, path, status_code, latency_ms, "
                "service_name, environment, request_id, type, "
                "CASE WHEN type = 'error' THEN json_object("
                "'exception_message', json_extract_string(payload, '$.exception_message'), "
                "'message', json_extract_string(payload, '$.message')"
                ") ELSE CAST('{}' AS JSON) END AS payload"
            )
        elif columns is None:
            resolved_columns = (
                "id, timestamp, method, path, status_code, latency_ms, "
                "service_name, environment, request_id, type, payload"
            )
        else:
            resolved_columns = columns
        where_sql, params = self._compile_filters(filters)
        # Avoid COUNT(*) OVER() on an unbounded inner result: that pattern scans
        # the full filter match before LIMIT. MATERIALIZED CTE + COUNT on the
        # cached result matches totals while keeping one pass over base events.
        sql = (
            f"WITH filtered AS MATERIALIZED ("
            f"SELECT {resolved_columns} FROM events WHERE {where_sql}"
            f"), agg AS (SELECT COUNT(*)::BIGINT AS __total FROM filtered) "
            f"SELECT page.*, agg.__total FROM ("
            f"SELECT * FROM filtered ORDER BY {order_by} LIMIT ? OFFSET ?"
            f") AS page CROSS JOIN agg"  # nosec B608
        )
        rows = self._fetchall_read(sql, [*params, limit, offset])
        if not rows:
            return 0, []
        total = int(rows[0][-1])
        trimmed = [tuple(row[:-1]) for row in rows]
        return total, trimmed

    def count_events(self, filters: EventStoreFilters) -> int:
        where_sql, params = self._compile_filters(filters)
        result = self._fetchone_read(
            f"SELECT COUNT(*) FROM events WHERE {where_sql}",  # nosec B608
            params,
        )
        return int(result[0] if result else 0)

    def delete_events_before(self, *, cutoff: datetime, project_id: UUID | None = None) -> int:
        sql = "DELETE FROM events WHERE received_at < ?"
        params: list[Any] = [_as_duckdb_timestamp(cutoff)]
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(str(project_id))
        with self._write_lock:
            count_predicate = sql.removeprefix("DELETE FROM events WHERE ")
            deleted = self._write_conn.execute(
                f"SELECT COUNT(*) FROM events WHERE {count_predicate}",  # nosec B608
                params,
            ).fetchone()
            self._write_conn.execute(sql, params)
        return int(deleted[0] if deleted else 0)

    def max_timestamp(self) -> datetime | None:
        row = self._fetchone_read("SELECT MAX(timestamp) FROM events")
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
        with self._write_lock:
            self._write_conn.execute("CHECKPOINT")

    def list_project_ids(self) -> list[str]:
        rows = self._fetchall_read("SELECT DISTINCT project_id FROM events ORDER BY project_id ASC")
        return [str(row[0]) for row in rows if row and row[0] is not None]

    def reassign_project_id(self, *, from_project_id: str, to_project_id: UUID) -> tuple[int, int]:
        """Move all rows from one project id to another.

        Local/dev recoverability helper for legacy databases where SQL metadata
        and DuckDB event rows drifted to different singleton project ids.
        """
        source = str(from_project_id).strip()
        target = str(to_project_id)
        if not source or source == target:
            return 0, 0
        with self._write_lock:
            events_row = self._write_conn.execute(
                "SELECT COUNT(*) FROM events WHERE project_id = ?",
                [source],
            ).fetchone()
            widgets_row = self._write_conn.execute(
                "SELECT COUNT(*) FROM dashboard_widget_points WHERE project_id = ?",
                [source],
            ).fetchone()
            events_count = int(events_row[0] if events_row else 0)
            widgets_count = int(widgets_row[0] if widgets_row else 0)
            if events_count > 0:
                self._write_conn.execute(
                    "UPDATE events SET project_id = ? WHERE project_id = ?",
                    [target, source],
                )
            if widgets_count > 0:
                self._write_conn.execute(
                    "UPDATE dashboard_widget_points SET project_id = ? WHERE project_id = ?",
                    [target, source],
                )
        return events_count, widgets_count

    def count_events_for_project(self, project_id: UUID | None = None) -> int:
        if project_id is None:
            row = self._fetchone_read("SELECT COUNT(*) FROM events")
            return int(row[0] if row else 0)
        row = self._fetchone_read(
            "SELECT COUNT(*) FROM events WHERE project_id = ?",
            [str(project_id)],
        )
        return int(row[0] if row else 0)

    def count_widget_points_for_project(self, project_id: UUID | None = None) -> int:
        if project_id is None:
            row = self._fetchone_read("SELECT COUNT(*) FROM dashboard_widget_points")
            return int(row[0] if row else 0)
        row = self._fetchone_read(
            "SELECT COUNT(*) FROM dashboard_widget_points WHERE project_id = ?",
            [str(project_id)],
        )
        return int(row[0] if row else 0)

    def delete_oldest_events(self, *, rows_to_delete: int, project_id: UUID | None = None) -> int:
        if rows_to_delete <= 0:
            return 0
        params: list[Any]
        if project_id is None:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM events ORDER BY timestamp ASC, received_at ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM events WHERE id IN ("
                "SELECT id FROM events ORDER BY timestamp ASC, received_at ASC, id ASC LIMIT ?"
                ")"
            )
            params = [rows_to_delete]
        else:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM events WHERE project_id = ? "
                "ORDER BY timestamp ASC, received_at ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM events WHERE id IN ("
                "SELECT id FROM events WHERE project_id = ? "
                "ORDER BY timestamp ASC, received_at ASC, id ASC LIMIT ?"
                ")"
            )
            params = [str(project_id), rows_to_delete]
        with self._write_lock:
            deleted_row = self._write_conn.execute(count_sql, params).fetchone()
            deleted = int(deleted_row[0] if deleted_row else 0)
            if deleted > 0:
                self._write_conn.execute(delete_sql, params)
        return deleted

    def delete_oldest_widget_points(
        self, *, rows_to_delete: int, project_id: UUID | None = None
    ) -> int:
        if rows_to_delete <= 0:
            return 0
        params_wp: list[Any]
        if project_id is None:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM dashboard_widget_points ORDER BY timestamp ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM dashboard_widget_points WHERE id IN ("
                "SELECT id FROM dashboard_widget_points ORDER BY timestamp ASC, id ASC LIMIT ?"
                ")"
            )
            params_wp = [rows_to_delete]
        else:
            count_sql = (
                "SELECT COUNT(*) FROM ("
                "SELECT id FROM dashboard_widget_points WHERE project_id = ? "
                "ORDER BY timestamp ASC, id ASC LIMIT ?"
                ")"
            )
            delete_sql = (
                "DELETE FROM dashboard_widget_points WHERE id IN ("
                "SELECT id FROM dashboard_widget_points WHERE project_id = ? "
                "ORDER BY timestamp ASC, id ASC LIMIT ?"
                ")"
            )
            params_wp = [str(project_id), rows_to_delete]
        with self._write_lock:
            deleted_row = self._write_conn.execute(count_sql, params_wp).fetchone()
            deleted = int(deleted_row[0] if deleted_row else 0)
            if deleted > 0:
                self._write_conn.execute(delete_sql, params_wp)
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


def shutdown_duckdb_event_store() -> None:
    global _duckdb_store
    with _duckdb_store_lock:
        store = _duckdb_store
        _duckdb_store = None
        if store is not None:
            store.close()


async def insert_events_duckdb(rows: list[dict[str, Any]]) -> None:
    if not event_store_enabled():
        return
    store = get_duckdb_event_store()
    await run_duckdb_write_sync(store.insert_rows, rows)
