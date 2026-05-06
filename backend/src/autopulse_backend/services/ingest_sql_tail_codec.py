from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from autopulse_backend.repositories.aggregates import ErrorGroupAggregateDelta, MetricBucketDelta
from autopulse_backend.services.aggregate_delta_codec import (
    decode_aggregate_payload,
    encode_aggregate_payload,
)


def _as_datetime(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("invalid_sql_tail_datetime")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _encode_widget_definitions(definitions: list[dict[str, object]]) -> list[dict[str, object]]:
    encoded: list[dict[str, object]] = []
    for row in definitions:
        project_id = row.get("project_id")
        updated_at = row.get("updated_at")
        widget_id = row.get("widget_id")
        widget_type = row.get("widget_type")
        title = row.get("title")
        display_order = row.get("display_order")
        config = row.get("config")
        if not isinstance(project_id, UUID) or not isinstance(updated_at, datetime):
            raise ValueError("invalid_sql_tail_widget_definition")
        if (
            not isinstance(widget_id, str)
            or not isinstance(widget_type, str)
            or not isinstance(title, str)
        ):
            raise ValueError("invalid_sql_tail_widget_definition")
        if not isinstance(display_order, int):
            raise ValueError("invalid_sql_tail_widget_definition")
        if not isinstance(config, dict):
            config = {}
        encoded.append(
            {
                "project_id": str(project_id),
                "widget_id": widget_id,
                "widget_type": widget_type,
                "title": title,
                "description": (
                    str(row.get("description")) if isinstance(row.get("description"), str) else None
                ),
                "display_order": int(display_order),
                "config": dict(config),
                "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
            }
        )
    return encoded


def _decode_widget_definitions(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise ValueError("invalid_sql_tail_widget_definitions")
    decoded: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid_sql_tail_widget_definition")
        project_id_raw = item.get("project_id")
        if not isinstance(project_id_raw, str):
            raise ValueError("invalid_sql_tail_widget_definition")
        decoded.append(
            {
                "project_id": UUID(project_id_raw),
                "widget_id": str(item.get("widget_id") or "")[:128],
                "widget_type": str(item.get("widget_type") or "")[:32],
                "title": str(item.get("title") or "")[:255],
                "description": (
                    str(item.get("description"))
                    if isinstance(item.get("description"), str)
                    else None
                ),
                "display_order": int(item.get("display_order") or 100),
                "config": item.get("config") if isinstance(item.get("config"), dict) else {},
                "updated_at": _as_datetime(item.get("updated_at")),
            }
        )
    return decoded


@dataclass(frozen=True, slots=True)
class IngestSqlTailReplayPayload:
    widget_definitions: list[dict[str, object]]
    metric_bucket_deltas: list[MetricBucketDelta]
    error_group_deltas: list[ErrorGroupAggregateDelta]
    persist_aggregates: bool


def encode_ingest_sql_tail_payload(
    *,
    widget_definitions: list[dict[str, object]],
    metric_bucket_deltas: list[MetricBucketDelta],
    error_group_deltas: list[ErrorGroupAggregateDelta],
    persist_aggregates: bool,
) -> dict[str, object]:
    return {
        "widget_definitions": _encode_widget_definitions(widget_definitions),
        "aggregate_payload": encode_aggregate_payload(
            metric_bucket_deltas=metric_bucket_deltas,
            error_group_deltas=error_group_deltas,
        ),
        "persist_aggregates": bool(persist_aggregates),
    }


def decode_ingest_sql_tail_payload(payload: dict[str, object]) -> IngestSqlTailReplayPayload:
    definitions = _decode_widget_definitions(payload.get("widget_definitions"))
    aggregate_payload = payload.get("aggregate_payload")
    if not isinstance(aggregate_payload, dict):
        raise ValueError("invalid_sql_tail_aggregate_payload")
    metric_bucket_deltas, error_group_deltas = decode_aggregate_payload(aggregate_payload)
    persist_aggregates = bool(payload.get("persist_aggregates"))
    return IngestSqlTailReplayPayload(
        widget_definitions=definitions,
        metric_bucket_deltas=metric_bucket_deltas,
        error_group_deltas=error_group_deltas,
        persist_aggregates=persist_aggregates,
    )
