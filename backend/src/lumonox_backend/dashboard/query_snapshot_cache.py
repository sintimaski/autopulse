from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from lumonox_backend.dashboard.overview_derived_widgets import merge_overview_derived_widgets
from lumonox_backend.metrics import service_metrics
from lumonox_backend.schemas import DashboardDataQueryRequest, DashboardDataQueryResponse
from lumonox_backend.schemas.dashboard_overview_models import DashboardRequestItem


@dataclass(frozen=True, slots=True)
class LiveIngestDelta:
    accepted: int
    error_count: int
    latency_total_ms: float
    count_2xx: int
    count_3xx: int
    count_4xx: int
    count_5xx: int
    requests: tuple[DashboardRequestItem, ...]


@dataclass(slots=True)
class _SnapshotEntry:
    response: DashboardDataQueryResponse
    version: int
    last_full_refresh_monotonic: float
    window_minutes: int


def _refresh_interval_seconds() -> float:
    raw = os.getenv("LUMONOX_DASHBOARD_QUERY_SNAPSHOT_REFRESH_SECONDS", "")
    if not raw.strip():
        return 30.0
    try:
        return max(2.0, min(float(raw), 300.0))
    except ValueError:
        return 30.0


def _is_scope_supported(payload: DashboardDataQueryRequest) -> bool:
    scope = payload.scope
    # Absolute time windows should remain canonical-query only.
    if scope.from_timestamp is not None or scope.to_timestamp is not None:
        return False
    if (
        scope.method
        or scope.status_class is not None
        or scope.path_contains
        or scope.environments
        or scope.services
        or scope.min_latency_ms is not None
        or scope.max_latency_ms is not None
        or scope.event_sql_filter
    ):
        return False
    if (
        payload.include_diagnosis
        or payload.include_alert_dispatches
        or payload.diagnosis_error_group_key
    ):
        return False
    return payload.requests.offset == 0 and payload.error_groups.offset == 0


class DashboardQuerySnapshotCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, _SnapshotEntry] = {}
        self._pending: dict[str, deque[tuple[int, LiveIngestDelta]]] = defaultdict(deque)

    @staticmethod
    def _key(project_id: UUID) -> str:
        return str(project_id)

    def read_if_fresh(
        self, *, project_id: UUID, payload: DashboardDataQueryRequest, current_version: int
    ) -> DashboardDataQueryResponse | None:
        if not _is_scope_supported(payload):
            return None
        key = self._key(project_id)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if now - entry.last_full_refresh_monotonic >= _refresh_interval_seconds():
                return None
            if entry.version != int(current_version):
                return None
            service_metrics.increment("dashboard.query.snapshot.hit")
            return entry.response.model_copy(deep=True)

    def seed(
        self,
        *,
        project_id: UUID,
        payload: DashboardDataQueryRequest,
        version: int,
        response: DashboardDataQueryResponse,
    ) -> None:
        if not _is_scope_supported(payload):
            return
        key = self._key(project_id)
        with self._lock:
            seeded = response.model_copy(deep=True)
            entry = _SnapshotEntry(
                response=seeded,
                version=int(version),
                last_full_refresh_monotonic=time.monotonic(),
                window_minutes=max(1, int(payload.scope.window_minutes or 60)),
            )
            pending = self._pending.pop(key, deque())
            while pending:
                pending_version, delta = pending.popleft()
                if pending_version <= entry.version:
                    continue
                _apply_delta_to_response(
                    entry.response,
                    delta,
                    window_minutes=max(1, int(entry.window_minutes)),
                )
                entry.version = pending_version
            self._entries[key] = entry
            service_metrics.increment("dashboard.query.snapshot.seed")

    def apply_live_ingest_delta(
        self,
        *,
        project_id: UUID,
        version: int,
        delta: LiveIngestDelta,
    ) -> None:
        key = self._key(project_id)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                queue = self._pending[key]
                queue.append((int(version), delta))
                while len(queue) > 256:
                    queue.popleft()
                service_metrics.increment("dashboard.query.snapshot.pending_delta")
                return
            if int(version) <= entry.version:
                return
            _apply_delta_to_response(
                entry.response,
                delta,
                window_minutes=max(1, int(entry.window_minutes)),
            )
            entry.version = int(version)
            service_metrics.increment("dashboard.query.snapshot.delta_applied")


def _apply_delta_to_response(
    response: DashboardDataQueryResponse,
    delta: LiveIngestDelta,
    *,
    window_minutes: int,
) -> None:
    accepted = max(0, int(delta.accepted))
    if accepted <= 0:
        return
    overview = response.overview
    requests = response.requests
    updated_at = datetime.now(tz=UTC)
    window_start = updated_at - timedelta(minutes=max(1, int(window_minutes)))
    window_start_minute = window_start.replace(second=0, microsecond=0)

    next_series = [bucket for bucket in overview.series if bucket.minute >= window_start_minute]
    overview.series = next_series
    overview.server_now = updated_at
    overview.from_timestamp = window_start
    overview.to_timestamp = updated_at

    minute = updated_at.replace(second=0, microsecond=0)
    if overview.series and overview.series[-1].minute == minute:
        bucket = overview.series[-1]
        prev_bucket_count = int(bucket.request_count)
        next_bucket_count = prev_bucket_count + accepted
        bucket_latency_total = float(bucket.avg_latency_ms) * max(0, prev_bucket_count)
        bucket.request_count = next_bucket_count
        bucket.error_count = int(bucket.error_count) + max(0, int(delta.error_count))
        bucket.avg_latency_ms = (
            bucket_latency_total + max(0.0, float(delta.latency_total_ms))
        ) / max(1, next_bucket_count)
        bucket.count_2xx = int(bucket.count_2xx) + max(0, int(delta.count_2xx))
        bucket.count_3xx = int(bucket.count_3xx) + max(0, int(delta.count_3xx))
        bucket.count_4xx = int(bucket.count_4xx) + max(0, int(delta.count_4xx))
        bucket.count_5xx = int(bucket.count_5xx) + max(0, int(delta.count_5xx))
    else:
        from lumonox_backend.schemas.dashboard_overview_models import DashboardOverviewBucket

        overview.series.append(
            DashboardOverviewBucket(
                minute=minute,
                request_count=accepted,
                error_count=max(0, int(delta.error_count)),
                avg_latency_ms=max(0.0, float(delta.latency_total_ms)) / max(1, accepted),
                count_2xx=max(0, int(delta.count_2xx)),
                count_3xx=max(0, int(delta.count_3xx)),
                count_4xx=max(0, int(delta.count_4xx)),
                count_5xx=max(0, int(delta.count_5xx)),
            )
        )

    total_requests = 0
    total_errors = 0
    total_latency_ms = 0.0
    for bucket in overview.series:
        total_requests += max(0, int(bucket.request_count))
        total_errors += max(0, int(bucket.error_count))
        total_latency_ms += max(0.0, float(bucket.avg_latency_ms)) * max(
            0, int(bucket.request_count)
        )
    overview.request_count = total_requests
    overview.error_count = total_errors
    overview.avg_latency_ms = total_latency_ms / max(1, total_requests)
    overview.error_rate = total_errors / max(1, total_requests)
    overview.requests_per_minute = total_requests / max(1.0, float(window_minutes))
    overview.release_markers = [m for m in overview.release_markers if m.at >= window_start]

    requests.server_now = updated_at
    requests.from_timestamp = window_start
    requests.to_timestamp = updated_at
    live_items = list(delta.requests)[: max(1, int(requests.limit))]
    merged = live_items + list(requests.items)
    filtered: list[DashboardRequestItem] = []
    for item in merged:
        if item.timestamp >= window_start:
            filtered.append(item)
        if len(filtered) >= max(1, int(requests.limit)):
            break
    requests.items = filtered
    requests.total = overview.request_count

    # Keep dependent optional slices coherent enough for the short refresh interval.
    if response.error_groups is not None:
        response.error_groups.server_now = updated_at
        response.error_groups.from_timestamp = window_start
        response.error_groups.to_timestamp = updated_at
    if response.recent_job_failures is not None:
        response.recent_job_failures.server_now = updated_at
        response.recent_job_failures.from_timestamp = window_start
        response.recent_job_failures.to_timestamp = updated_at
    if response.widgets is not None:
        response.widgets.server_now = updated_at
        response.widgets.from_timestamp = window_start
        response.widgets.to_timestamp = updated_at
        response.widgets = merge_overview_derived_widgets(response.widgets, overview)
    if response.overview_extended is not None:
        response.overview_extended.server_now = updated_at
        response.overview_extended.from_timestamp = window_start
        response.overview_extended.to_timestamp = updated_at


dashboard_query_snapshot_cache = DashboardQuerySnapshotCache()


def _try_parse_request_item(item: object) -> DashboardRequestItem | None:
    if not isinstance(item, dict):
        return None
    try:
        return DashboardRequestItem.model_validate(item)
    except ValidationError:
        return None


def live_ingest_delta_from_payload(payload: dict[str, Any] | None) -> LiveIngestDelta | None:
    if not payload:
        return None
    raw = payload.get("live_ingest")
    if not isinstance(raw, dict):
        return None
    requests: list[DashboardRequestItem] = []
    for item in raw.get("requests", []):
        parsed = _try_parse_request_item(item)
        if parsed is not None:
            requests.append(parsed)
    try:
        return LiveIngestDelta(
            accepted=max(0, int(raw.get("accepted", 0))),
            error_count=max(0, int(raw.get("error_count", 0))),
            latency_total_ms=max(0.0, float(raw.get("latency_total_ms", 0.0))),
            count_2xx=max(0, int(raw.get("count_2xx", 0))),
            count_3xx=max(0, int(raw.get("count_3xx", 0))),
            count_4xx=max(0, int(raw.get("count_4xx", 0))),
            count_5xx=max(0, int(raw.get("count_5xx", 0))),
            requests=tuple(requests),
        )
    except Exception:
        return None
