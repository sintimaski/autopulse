from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.sql import ColumnElement

from lumonox_backend.models import Event

LOG_QUERY_SQL_RE = re.compile(
    r"^\s*select\s+(?P<select>[\w\s,.*]+)\s+from\s+events(?:\s+where\s+(?P<where>.+?))?"
    r"(?:\s+order\s+by\s+(?P<order>[\w_]+)\s*(?P<direction>asc|desc)?)?"
    r"(?:\s+limit\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE,
)
LOG_QUERY_MAX_LIMIT = 200
SUPPORTED_SELECT_ALL_COLUMNS = (
    "id,timestamp,method,path,status_code,latency_ms,service_name,environment,request_id"
)
SUPPORTED_SELECT_ALL_COLUMNS_SPACED = (
    "id, timestamp, method, path, status_code, latency_ms, service_name, environment, request_id"
)


@dataclass(slots=True)
class ParsedLogQuery:
    normalized_query: str
    where_clauses: list[str]
    order_by: str
    order_desc: bool
    limit: int


def percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return float(ordered[rank])


def parse_log_query(query: str) -> ParsedLogQuery:
    normalized = " ".join(query.strip().split())
    if not normalized:
        raise HTTPException(status_code=422, detail="query must not be empty")
    match = LOG_QUERY_SQL_RE.match(normalized)
    if not match:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unsupported query syntax. Use: SELECT ... FROM events "
                "WHERE ... ORDER BY timestamp|id ASC|DESC LIMIT n"
            ),
        )

    select_part = (match.group("select") or "").strip().lower()
    if select_part not in {
        "*",
        SUPPORTED_SELECT_ALL_COLUMNS,
        SUPPORTED_SELECT_ALL_COLUMNS_SPACED,
    }:
        raise HTTPException(
            status_code=422,
            detail=(
                "Only SELECT * or explicit columns "
                "(id,timestamp,method,path,status_code,latency_ms,service_name,environment,"
                "request_id) "
                "is supported."
            ),
        )

    order_by = (match.group("order") or "timestamp").strip().lower()
    if order_by not in {"timestamp", "id"}:
        raise HTTPException(status_code=422, detail="ORDER BY supports only timestamp or id")
    direction = (match.group("direction") or "desc").strip().lower()
    order_desc = direction != "asc"

    limit_value = int(match.group("limit") or 100)
    limit = max(1, min(limit_value, LOG_QUERY_MAX_LIMIT))

    where_raw = (match.group("where") or "").strip()
    where_clauses = [
        part.strip()
        for part in re.split(r"\s+and\s+", where_raw, flags=re.IGNORECASE)
        if part.strip()
    ]
    return ParsedLogQuery(
        normalized_query=normalized,
        where_clauses=where_clauses,
        order_by=order_by,
        order_desc=order_desc,
        limit=limit,
    )


def apply_log_query_filters(filters: list[ColumnElement[bool]], where_clauses: list[str]) -> None:
    for clause in where_clauses:
        eq_match = re.match(
            r"^(method|environment|service_name)\s*=\s*'([^']+)'\s*$",
            clause,
            flags=re.IGNORECASE,
        )
        if eq_match:
            field, value = eq_match.groups()
            field_name = field.lower()
            if field_name == "method":
                filters.append(Event.method == value.upper())
            elif field_name == "environment":
                filters.append(Event.environment == value)
            else:
                filters.append(Event.service_name == value)
            continue

        path_like = re.match(r"^path\s+like\s+'([^']+)'\s*$", clause, flags=re.IGNORECASE)
        if path_like:
            filters.append(Event.path.like(path_like.group(1)))
            continue

        status_ge = re.match(r"^status_code\s*>=\s*(\d+)\s*$", clause, flags=re.IGNORECASE)
        if status_ge:
            filters.append(Event.status_code >= int(status_ge.group(1)))
            continue
        status_le = re.match(r"^status_code\s*<=\s*(\d+)\s*$", clause, flags=re.IGNORECASE)
        if status_le:
            filters.append(Event.status_code <= int(status_le.group(1)))
            continue

        latency_ge = re.match(
            r"^latency_ms\s*>=\s*(\d+(?:\.\d+)?)\s*$", clause, flags=re.IGNORECASE
        )
        if latency_ge:
            filters.append(Event.latency_ms >= float(latency_ge.group(1)))
            continue
        latency_le = re.match(
            r"^latency_ms\s*<=\s*(\d+(?:\.\d+)?)\s*$", clause, flags=re.IGNORECASE
        )
        if latency_le:
            filters.append(Event.latency_ms <= float(latency_le.group(1)))
            continue

        raise HTTPException(
            status_code=422,
            detail=f"Unsupported WHERE clause fragment: '{clause}'",
        )


def append_event_sql_filters(
    filters: list[ColumnElement[bool]], event_sql_filter: str | None
) -> None:
    """Apply log-query WHERE fragments (AND-separated) to an existing Event filter list."""
    if not event_sql_filter or not event_sql_filter.strip():
        return
    wrapped = (
        "SELECT * FROM events WHERE "
        f"{event_sql_filter.strip()} "  # nosec B608
        "ORDER BY timestamp DESC LIMIT 100"
    )
    parsed = parse_log_query(wrapped)
    apply_log_query_filters(filters, parsed.where_clauses)
