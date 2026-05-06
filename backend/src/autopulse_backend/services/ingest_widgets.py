from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from autopulse_backend.dashboard.payload_limits import MAX_WIDGET_POINTS_PER_INGEST_BATCH
from autopulse_backend.models import Event


def as_utc_datetime(raw: object, *, fallback: datetime) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    else:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def extract_dashboard_widget_rows(
    *,
    project_id: UUID,
    rows: list[Event],
    max_points: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    definitions_by_id: dict[str, dict[str, object]] = {}
    points: list[dict[str, object]] = []
    point_cap = max_points if max_points is not None else MAX_WIDGET_POINTS_PER_INGEST_BATCH
    remaining = max(0, int(point_cap))
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        widget_payload = payload.get("dashboard_widgets")
        if not isinstance(widget_payload, dict):
            continue
        definitions = widget_payload.get("definitions")
        if isinstance(definitions, list):
            for item in definitions:
                if not isinstance(item, dict):
                    continue
                widget_id = item.get("widget_id")
                widget_type = item.get("type")
                title = item.get("title")
                if not isinstance(widget_id, str) or not widget_id.strip():
                    continue
                if widget_type not in {
                    "card",
                    "line",
                    "bar",
                    "donut",
                    "histogram",
                    "scatter",
                    "stacked_area",
                }:
                    continue
                if not isinstance(title, str) or not title.strip():
                    continue
                definitions_by_id[widget_id] = {
                    "project_id": project_id,
                    "widget_id": widget_id,
                    "widget_type": widget_type,
                    "title": title.strip()[:255],
                    "description": (
                        str(item.get("description"))[:2000]
                        if isinstance(item.get("description"), str)
                        else None
                    ),
                    "display_order": int(item.get("order") or 100),
                    "config": item.get("config") if isinstance(item.get("config"), dict) else {},
                    "updated_at": row.timestamp,
                }
        datapoints = widget_payload.get("points")
        if isinstance(datapoints, list):
            for point in datapoints:
                if remaining <= 0:
                    break
                if not isinstance(point, dict):
                    continue
                widget_id = point.get("widget_id")
                value = point.get("value")
                if not isinstance(widget_id, str) or not widget_id.strip():
                    continue
                if not isinstance(value, int | float):
                    continue
                points.append(
                    {
                        "project_id": project_id,
                        "widget_id": widget_id,
                        "timestamp": as_utc_datetime(
                            point.get("timestamp"), fallback=row.timestamp
                        ),
                        "label": str(point.get("label"))[:255]
                        if isinstance(point.get("label"), str)
                        else None,
                        "value": float(value),
                    }
                )
                remaining -= 1
        infra_payload = payload.get("infrastructure_metrics")
        if isinstance(infra_payload, dict) and remaining > 0:
            infra_definitions, infra_points = extract_infrastructure_widget_rows(
                project_id=project_id,
                timestamp=row.timestamp,
                payload=infra_payload,
            )
            for definition in infra_definitions:
                definitions_by_id[str(definition["widget_id"])] = definition
            for ip in infra_points:
                if remaining <= 0:
                    break
                points.append(ip)
                remaining -= 1
    return list(definitions_by_id.values()), points


def extract_infrastructure_widget_rows(
    *,
    project_id: UUID,
    timestamp: datetime,
    payload: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metric_specs: tuple[tuple[str, str, str, str, str, int], ...] = (
        ("host_cpu_percent", "infra_host_cpu_percent", "Host CPU", "%", "line", 500),
        (
            "host_memory_used_percent",
            "infra_host_memory_percent",
            "Host memory used",
            "%",
            "line",
            510,
        ),
        ("process_cpu_percent", "infra_process_cpu_percent", "App CPU", "%", "line", 520),
        (
            "process_memory_percent",
            "infra_process_memory_percent",
            "App memory share",
            "%",
            "line",
            530,
        ),
        (
            "process_memory_rss_bytes",
            "infra_process_memory_rss_mb",
            "App RSS memory",
            "MB",
            "line",
            540,
        ),
        ("disk_used_percent", "infra_disk_used_percent", "Host disk used", "%", "line", 550),
        ("network_bytes_recv", "infra_network_received_mb", "Network received", "MB", "line", 560),
        ("network_bytes_sent", "infra_network_sent_mb", "Network sent", "MB", "line", 570),
    )
    definitions: list[dict[str, object]] = []
    points: list[dict[str, object]] = []
    for source_key, widget_id, title, unit, widget_type, order in metric_specs:
        raw_value = payload.get(source_key)
        if not isinstance(raw_value, int | float):
            continue
        value = float(raw_value)
        if source_key.endswith("_bytes") or source_key in (
            "network_bytes_recv",
            "network_bytes_sent",
        ):
            value = value / (1024 * 1024)
        definitions.append(
            {
                "project_id": project_id,
                "widget_id": widget_id,
                "widget_type": widget_type,
                "title": title,
                "description": "AutoPulse SDK host/app infrastructure metric",
                "display_order": order,
                "config": {"unit": unit},
                "updated_at": timestamp,
            }
        )
        points.append(
            {
                "project_id": project_id,
                "widget_id": widget_id,
                "timestamp": timestamp,
                "value": value,
            }
        )
    return definitions, points


def extract_operational_widget_rows(
    *,
    project_id: UUID,
    timestamp: datetime,
    rows: list[Event],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not rows:
        return [], []
    definitions: list[dict[str, object]] = [
        {
            "project_id": project_id,
            "widget_id": "infra_dependency_map",
            "widget_type": "bar",
            "title": "Dependency map",
            "description": "Observed inbound edge to each service",
            "display_order": 610,
            "config": {"unit": "req"},
            "updated_at": timestamp,
        },
        {
            "project_id": project_id,
            "widget_id": "infra_cache_hit_miss",
            "widget_type": "bar",
            "title": "Cache hit/miss",
            "description": "Estimated request hit/miss split for current traffic",
            "display_order": 620,
            "config": {"unit": "req"},
            "updated_at": timestamp,
        },
        {
            "project_id": project_id,
            "widget_id": "infra_db_query_performance",
            "widget_type": "bar",
            "title": "DB query performance",
            "description": "Estimated DB-facing request latency statistics",
            "display_order": 630,
            "config": {"unit": "ms"},
            "updated_at": timestamp,
        },
    ]

    service_counts: dict[str, int] = {}
    hit_count = 0
    miss_count = 0
    db_latencies: list[float] = []
    for row in rows:
        service = row.service_name or "unknown"
        service_counts[service] = service_counts.get(service, 0) + 1
        if int(row.status_code or 0) < 500:
            hit_count += 1
        else:
            miss_count += 1
        path = (row.path or "").lower()
        service_name = (row.service_name or "").lower()
        if any(token in path for token in ("db", "sql", "query")) or any(
            token in service_name for token in ("db", "sql")
        ):
            db_latencies.append(float(row.latency_ms or 0.0))

    if not db_latencies:
        db_latencies = [float(row.latency_ms or 0.0) for row in rows]
    db_latencies.sort()
    avg_latency = sum(db_latencies) / max(1, len(db_latencies))
    p95_index = max(0, int(round((len(db_latencies) - 1) * 0.95)))
    p95_latency = db_latencies[p95_index]

    points: list[dict[str, object]] = []
    for service, count in service_counts.items():
        points.append(
            {
                "project_id": project_id,
                "widget_id": "infra_dependency_map",
                "timestamp": timestamp,
                "label": f"edge->{service}",
                "value": float(count),
            }
        )
    points.extend(
        [
            {
                "project_id": project_id,
                "widget_id": "infra_cache_hit_miss",
                "timestamp": timestamp,
                "label": "hit",
                "value": float(hit_count),
            },
            {
                "project_id": project_id,
                "widget_id": "infra_cache_hit_miss",
                "timestamp": timestamp,
                "label": "miss",
                "value": float(miss_count),
            },
            {
                "project_id": project_id,
                "widget_id": "infra_db_query_performance",
                "timestamp": timestamp,
                "label": "avg_ms",
                "value": float(avg_latency),
            },
            {
                "project_id": project_id,
                "widget_id": "infra_db_query_performance",
                "timestamp": timestamp,
                "label": "p95_ms",
                "value": float(p95_latency),
            },
            {
                "project_id": project_id,
                "widget_id": "infra_db_query_performance",
                "timestamp": timestamp,
                "label": "samples",
                "value": float(len(db_latencies)),
            },
        ]
    )
    return definitions, points
