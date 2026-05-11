from __future__ import annotations

import json
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from os import getenv
from pathlib import Path
from threading import Lock, local
from typing import Any, cast
from uuid import UUID

import duckdb

from lumonox_backend.core.config import Settings, get_settings
from lumonox_backend.dashboard.log_query import parse_log_query
from lumonox_backend.dashboard.payload_limits import MAX_DASHBOARD_WIDGET_POINTS_RETURNED
from lumonox_backend.services.duckdb_async import run_duckdb_write_sync
from lumonox_backend.services.event_store_utils import (
    as_duckdb_timestamp,
    as_utc,
    duckdb_connect_config,
)


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
    exclude_lumonox_traffic: bool = False
    event_sql_filter: str | None = None
    #: When True (default), dashboard aggregations only include HTTP-shaped rows.
    http_events_only: bool = True
    #: If set, restricts to these ``type`` values (``http_events_only`` is ignored).
    require_event_types: tuple[str, ...] | None = None
    #: When True, rows match the window if either ``timestamp`` or ``received_at`` falls
    #: inside ``[from_timestamp, to_timestamp]``. Used by trace explorer so OTLP spans
    #: with stale or synthetic clock times still appear after ingest.
    include_received_at_in_time_window: bool = False
    #: When True, omit timestamp bounds in SQL (still ``project_id``-scoped). Used by
    #: dashboard Query Explorer "whole project" mode against the live DuckDB ``events``
    #: table; parquet cold paths are skipped so exports are not scanned day-by-day.
    skip_timestamp_filter: bool = False
    #: When True, add the dashboard ``error_like`` predicate (matches ORM error-groups scope).
    dashboard_error_like_only: bool = False
    #: Exact ``request_id`` match (HTTP requests, errors, and correlated job rows).
    correlation_request_id: str | None = None
    #: Keyset continuation for log-style pagination (applied in SQL, avoids rescanning head rows).
    log_keyset_timestamp: datetime | None = None
    log_keyset_id: int | None = None
    log_keyset_order: str = "timestamp"
    log_keyset_desc: bool = True


class DuckDbEventStore:
    _EVENT_SOURCE_COLUMNS = (
        "id, project_id, timestamp, received_at, sdk_version, type, "
        "service_name, environment, method, path, status_code, latency_ms, payload, request_id"
    )

    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _cfg = duckdb_connect_config()
        self._connect_config = _cfg
        self._write_conn = self._open_connection(str(self._path), _cfg)
        self._write_lock = Lock()
        self._read_local = local()
        self._read_conn_init_lock = Lock()
        self._read_connections: list[Any] = []
        self._read_connections_lock = Lock()
        self._ensure_schema()

    def _open_connection(self, path: str, config: dict[str, Any]) -> Any:
        attempts = int(getenv("LUMONOX_DUCKDB_CONNECT_RETRIES", "16").strip() or "16")
        attempts = max(1, min(attempts, 64))
        base_delay_s = float(
            getenv("LUMONOX_DUCKDB_CONNECT_RETRY_BASE_S", "0.08").strip() or "0.08"
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
                as_duckdb_timestamp(row["timestamp"]),
                as_duckdb_timestamp(row["received_at"]),
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
                    as_duckdb_timestamp(timestamp),
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
                as_duckdb_timestamp(from_timestamp),
                as_duckdb_timestamp(to_timestamp),
                cap,
            ],
        )

    def _compile_filters(self, filters: EventStoreFilters) -> tuple[str, list[Any]]:
        clauses = ["project_id = ?"]
        params: list[Any] = [str(filters.project_id)]
        if not filters.skip_timestamp_filter:
            from_ts = as_duckdb_timestamp(filters.from_timestamp)
            to_ts = as_duckdb_timestamp(filters.to_timestamp)
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
        if filters.exclude_lumonox_traffic:
            clauses.append("path NOT LIKE '/lumonox/%'")
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
        if filters.correlation_request_id and str(filters.correlation_request_id).strip():
            clauses.append("request_id = ?")
            params.append(str(filters.correlation_request_id).strip()[:128])
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
        if filters.log_keyset_timestamp is not None and filters.log_keyset_id is not None:
            ks_ts = as_duckdb_timestamp(filters.log_keyset_timestamp)
            kid = int(filters.log_keyset_id)
            order = (filters.log_keyset_order or "timestamp").strip().lower()
            desc = bool(filters.log_keyset_desc)
            if order == "id":
                if desc:
                    clauses.append("id < ?")
                else:
                    clauses.append("id > ?")
                params.append(kid)
            else:
                if desc:
                    clauses.append(
                        "(timestamp < CAST(? AS TIMESTAMP) OR "
                        "(timestamp = CAST(? AS TIMESTAMP) AND id < ?))"
                    )
                    params.extend([ks_ts, ks_ts, kid])
                else:
                    clauses.append(
                        "(timestamp > CAST(? AS TIMESTAMP) OR "
                        "(timestamp = CAST(? AS TIMESTAMP) AND id > ?))"
                    )
                    params.extend([ks_ts, ks_ts, kid])
        if filters.dashboard_error_like_only:
            from_ts = as_duckdb_timestamp(filters.from_timestamp)
            to_ts = as_duckdb_timestamp(filters.to_timestamp)
            clauses.append(
                "("
                "type = 'error' OR (type = 'request' AND status_code >= 500 AND ("
                "request_id IS NULL OR NOT EXISTS ("
                "SELECT 1 FROM events paired WHERE "
                "paired.project_id = scoped_events.project_id "
                "AND paired.type = 'error' "
                "AND paired.request_id = scoped_events.request_id "
                "AND paired.request_id IS NOT NULL "
                "AND scoped_events.request_id IS NOT NULL "
                "AND paired.timestamp >= CAST(? AS TIMESTAMP) "
                "AND paired.timestamp <= CAST(? AS TIMESTAMP)"
                ")))"
                ")"
            )
            params.extend([from_ts, to_ts])
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

    @staticmethod
    def _sql_string_literal(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _list_parquet_export_files(
        self,
        *,
        export_root: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
    ) -> list[Path]:
        def _utc_date(value: datetime) -> date:
            if value.tzinfo is None:
                return value.date()
            return value.astimezone(UTC).date()

        root = Path(export_root).expanduser().resolve()
        if not root.is_dir():
            return []
        start_day = _utc_date(from_timestamp)
        end_day = _utc_date(to_timestamp)
        if end_day < start_day:
            return []
        files: list[Path] = []
        day = start_day
        while day <= end_day:
            day_dir = root / f"date={day.isoformat()}"
            if day_dir.is_dir():
                files.extend(day_dir.glob("service=*/environment=*/part-*.parquet"))
            day = day + timedelta(days=1)
        unique_sorted = sorted({path.resolve() for path in files if path.is_file()})
        return unique_sorted

    def _resolve_events_source_sql(self, filters: EventStoreFilters) -> tuple[str, list[Any]]:
        if filters.skip_timestamp_filter:
            return "events", []
        settings = get_settings()
        if not settings.parquet_query_enabled or settings.event_store != "duckdb":
            return "events", []
        cutoff = datetime.now(tz=UTC) - timedelta(
            hours=max(1, int(settings.parquet_hot_window_hours))
        )
        cutoff_utc = as_utc(cutoff)
        cutoff_naive = as_duckdb_timestamp(cutoff)
        if as_utc(filters.from_timestamp) >= cutoff_utc:
            return "events", []
        cold_window_end = min(as_utc(filters.to_timestamp), cutoff_utc)
        if cold_window_end <= as_utc(filters.from_timestamp):
            return "events", []
        parquet_files = self._list_parquet_export_files(
            export_root=settings.parquet_export_root,
            from_timestamp=as_utc(filters.from_timestamp),
            to_timestamp=cold_window_end,
        )
        if not parquet_files:
            return "events", []
        parquet_files_sql = ",".join(self._sql_string_literal(str(path)) for path in parquet_files)
        # Paths are filesystem literals from export layout, not user SQL.
        source_sql = (
            "(SELECT "  # nosec B608
            + self._EVENT_SOURCE_COLUMNS
            + " FROM events WHERE timestamp > CAST(? AS TIMESTAMP) "  # nosec B608
            "UNION ALL SELECT "
            + self._EVENT_SOURCE_COLUMNS
            + " FROM read_parquet(["  # nosec B608
            + parquet_files_sql
            + "], hive_partitioning=1) WHERE timestamp <= CAST(? AS TIMESTAMP))"  # nosec B608
        )
        return source_sql, [cutoff_naive, cutoff_naive]

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
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        sql = (
            f"SELECT {columns} FROM {source_sql} AS scoped_events "
            f"WHERE {where_sql} ORDER BY {order_by}"  # nosec B608
        )
        bound_params = [*source_params, *params]
        if limit is not None:
            sql += " LIMIT ?"
            bound_params.append(limit)
        if offset:
            sql += " OFFSET ?"
            bound_params.append(offset)
        return self._fetchall_read(sql, bound_params)

    def fetch_dashboard_error_groups(
        self,
        filters: EventStoreFilters,
        *,
        scan_limit: int,
        limit: int,
        offset: int,
    ) -> tuple[int, list[tuple[Any, ...]]]:
        """Aggregate error groups in DuckDB (bounded scan + SQL grouping).

        Mirrors ``duckdb_queries.error_groups`` semantics: consider up to ``scan_limit``
        newest matching rows, then group and page. Uses ``dashboard_error_like_only`` on
        ``filters`` (caller should ``dataclasses.replace``).
        """
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        scan = max(1, min(int(scan_limit), 20_000))
        lim = max(0, int(limit))
        off = max(0, int(offset))
        gk_sql = (
            "CASE WHEN trim(coalesce(json_extract_string(payload, '$.error_hash'), '')) <> '' "
            "THEN concat(trim(json_extract_string(payload, '$.error_hash')), "
            "chr(30), coalesce(path, '')) "
            "ELSE sha256(concat("
            "coalesce(json_extract_string(payload, '$.exception_type'), ''), '|', "
            "coalesce(json_extract_string(payload, '$.exception_message'), ''), '|', "
            "coalesce(path, ''))) END"
        )
        sql = (
            "WITH cand AS MATERIALIZED ("
            f"SELECT id, timestamp, path, status_code, payload, {gk_sql} AS gk "  # nosec B608
            f"FROM {source_sql} AS scoped_events "  # nosec B608
            f"WHERE {where_sql} "  # nosec B608
            "ORDER BY timestamp DESC, id DESC "
            "LIMIT ?"
            "), "
            "grouped AS ("
            "SELECT gk, COUNT(*)::BIGINT AS cnt, "
            "MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen "
            "FROM cand GROUP BY gk"
            "), "
            "ranked AS ("
            "SELECT c.gk, c.id, c.timestamp, c.path, c.status_code, c.payload, "
            "ROW_NUMBER() OVER (PARTITION BY c.gk ORDER BY c.timestamp DESC, c.id DESC) AS rn "
            "FROM cand AS c"
            "), "
            "page AS ("
            "SELECT g.gk, g.cnt, g.first_seen, g.last_seen, r.path, r.status_code, "
            "json_extract_string(r.payload, '$.exception_type') AS exception_type, "
            "json_extract_string(r.payload, '$.exception_message') AS exception_message, "
            "json_extract_string(r.payload, '$.stack_trace') AS stack_trace "
            "FROM grouped AS g "
            "INNER JOIN ranked AS r ON r.gk = g.gk AND r.rn = 1 "
            "ORDER BY g.last_seen DESC, g.cnt DESC "
            "LIMIT ? OFFSET ?"
            ") "
            "SELECT t.__total, p.gk, p.cnt, p.first_seen, p.last_seen, p.path, p.status_code, "
            "p.exception_type, p.exception_message, p.stack_trace "
            "FROM page AS p "
            "CROSS JOIN (SELECT COUNT(*)::BIGINT AS __total FROM grouped) AS t"
        )
        bound = [*source_params, *params, scan, lim, off]
        rows = self._fetchall_read(sql, bound)
        if not rows:
            return 0, []
        total = int(rows[0][0])
        out: list[tuple[Any, ...]] = []
        for row in rows:
            out.append(
                (
                    str(row[1]),
                    int(row[2]),
                    row[3],
                    row[4],
                    row[5],
                    int(row[6]),
                    row[7],
                    row[8],
                    row[9],
                )
            )
        return total, out

    def query_events_sql(
        self,
        filters: EventStoreFilters,
        *,
        select_sql: str,
        suffix_sql: str = "",
        extra_params: list[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        sql = (
            f"SELECT {select_sql} FROM {source_sql} AS scoped_events "
            f"WHERE {where_sql} {suffix_sql}"  # nosec B608
        )
        bound_params = [*source_params, *params]
        if extra_params:
            bound_params.extend(extra_params)
        return self._fetchall_read(sql, bound_params)

    def query_scoped_events_sql(
        self,
        filters: EventStoreFilters,
        query_sql: str,
        max_rows: int,
        extra_params: list[Any] | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        sql = (
            f"WITH scoped_events AS MATERIALIZED ("
            f"SELECT * FROM {source_sql} AS events_source WHERE {where_sql}"
            f") SELECT * FROM ({query_sql}) AS user_query LIMIT ?"  # nosec B608
        )
        bound_params = [*source_params, *params]
        if extra_params:
            bound_params.extend(extra_params)
        bound_params.append(max_rows)
        return self._query_with_columns_read(sql, bound_params)

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
                ") ELSE CAST('{}' AS JSON) END AS payload, "
                "received_at, sdk_version, "
                "json_extract_string(payload, '$.trace_id') AS trace_id, "
                "json_extract_string(payload, '$.traceId') AS trace_id_alt, "
                "json_extract_string(payload, '$.span_id') AS span_id, "
                "json_extract_string(payload, '$.spanId') AS span_id_alt"
            )
        elif columns is None:
            resolved_columns = (
                "id, timestamp, method, path, status_code, latency_ms, "
                "service_name, environment, request_id, type, payload"
            )
        else:
            resolved_columns = columns
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        # Fast path for dashboard requests: avoid materializing transformed payload
        # fields for every matching row before LIMIT/OFFSET.
        #
        # We first page on lightweight keys (id,timestamp), then join back to source
        # to compute selected columns for only the requested page.
        if order_by.strip().lower() == "timestamp desc, id desc":
            sql = (
                "WITH filtered AS MATERIALIZED ("
                f"SELECT id, timestamp FROM {source_sql} AS scoped_events "  # nosec B608
                f"WHERE {where_sql}"
                "), agg AS (SELECT COUNT(*)::BIGINT AS __total FROM filtered), "
                "page AS MATERIALIZED ("
                "SELECT id AS __page_id, timestamp AS __page_timestamp FROM filtered "
                "ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?"
                ") "
                f"SELECT {resolved_columns}, agg.__total "  # nosec B608
                f"FROM {source_sql} AS scoped_events "  # nosec B608
                "INNER JOIN page ON page.__page_id = scoped_events.id "
                "CROSS JOIN agg "
                "ORDER BY page.__page_timestamp DESC, page.__page_id DESC"
            )
            rows = self._fetchall_read(
                sql,
                [*source_params, *params, limit, offset, *source_params],
            )
        else:
            # Generic fallback for non-default orderings.
            sql = (
                f"WITH filtered AS MATERIALIZED ("
                f"SELECT {resolved_columns} FROM {source_sql} AS scoped_events WHERE {where_sql}"
                f"), agg AS (SELECT COUNT(*)::BIGINT AS __total FROM filtered) "
                f"SELECT page.*, agg.__total FROM ("
                f"SELECT * FROM filtered ORDER BY {order_by} LIMIT ? OFFSET ?"
                f") AS page CROSS JOIN agg"  # nosec B608
            )
            rows = self._fetchall_read(sql, [*source_params, *params, limit, offset])
        if not rows:
            return 0, []
        total = int(rows[0][-1])
        trimmed = [tuple(row[:-1]) for row in rows]
        return total, trimmed

    def count_events(self, filters: EventStoreFilters) -> int:
        source_sql, source_params = self._resolve_events_source_sql(filters)
        where_sql, params = self._compile_filters(filters)
        result = self._fetchone_read(
            f"SELECT COUNT(*) FROM {source_sql} AS scoped_events WHERE {where_sql}",  # nosec B608
            [*source_params, *params],
        )
        return int(result[0] if result else 0)

    def delete_events_before(self, *, cutoff: datetime, project_id: UUID | None = None) -> int:
        sql = "DELETE FROM events WHERE received_at < ?"
        params: list[Any] = [as_duckdb_timestamp(cutoff)]
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

    def delete_widget_points_before(
        self, *, cutoff: datetime, project_id: UUID | None = None
    ) -> int:
        """Delete widget samples at or before ``cutoff`` (same horizon as event retention)."""
        sql = "DELETE FROM dashboard_widget_points WHERE timestamp < ?"
        params: list[Any] = [as_duckdb_timestamp(cutoff)]
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(str(project_id))
        with self._write_lock:
            count_predicate = sql.removeprefix("DELETE FROM dashboard_widget_points WHERE ")
            deleted = self._write_conn.execute(
                f"SELECT COUNT(*) FROM dashboard_widget_points WHERE {count_predicate}",  # nosec B608
                params,
            ).fetchone()
            self._write_conn.execute(sql, params)
        return int(deleted[0] if deleted else 0)

    def max_timestamp(self) -> datetime | None:
        row = self._fetchone_read("SELECT MAX(timestamp) FROM events")
        value = row[0] if row else None
        if value is None:
            return None
        return as_utc(value)

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
_duckdb_read_stores_by_path: dict[Path, DuckDbEventStore] = {}


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


def get_duckdb_read_store_for_path(db_path: str | Path) -> DuckDbEventStore:
    """Return a cached read-only DuckDB store for a specific on-disk database path."""
    resolved_path = Path(db_path).expanduser().resolve()
    global _duckdb_read_stores_by_path
    with _duckdb_store_lock:
        existing = _duckdb_read_stores_by_path.get(resolved_path)
        if existing is not None:
            return existing
        created = DuckDbEventStore(str(resolved_path))
        _duckdb_read_stores_by_path[resolved_path] = created
        return created


def try_get_duckdb_event_store() -> DuckDbEventStore | None:
    try:
        return get_duckdb_event_store()
    except duckdb.IOException:
        return None


def shutdown_duckdb_event_store() -> None:
    global _duckdb_store, _duckdb_read_stores_by_path
    with _duckdb_store_lock:
        store = _duckdb_store
        _duckdb_store = None
        if store is not None:
            store.close()
        for read_store in _duckdb_read_stores_by_path.values():
            read_store.close()
        _duckdb_read_stores_by_path = {}


async def insert_events_duckdb(rows: list[dict[str, Any]]) -> None:
    if not event_store_enabled():
        return
    store = get_duckdb_event_store()
    await run_duckdb_write_sync(store.insert_rows, rows)
