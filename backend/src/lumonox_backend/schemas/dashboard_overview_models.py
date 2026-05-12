from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DashboardOverviewBucket(BaseModel):
    minute: datetime
    request_count: int
    error_count: int
    avg_latency_ms: float
    count_2xx: int
    count_3xx: int
    count_4xx: int
    count_5xx: int


class DashboardReleaseMarker(BaseModel):
    """First-seen timestamp for a distinct (release, git_sha) pair in the overview window."""

    at: datetime
    release: str
    git_sha: str | None = None


class DashboardOverviewResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    requests_per_minute: float
    series: list[DashboardOverviewBucket]
    release_markers: list[DashboardReleaseMarker] = Field(default_factory=list)


class DashboardBreakdownItem(BaseModel):
    key: str
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float


class DashboardErrorTypeBreakdownItem(BaseModel):
    error_type: str
    count: int


class DashboardAlertTimelineItem(BaseModel):
    triggered_at: datetime
    alert_type: str
    status: str


class DashboardOverviewExtendedResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    apdex_score: float
    active_sessions_estimate: int
    error_burst_count: int
    active_incident_count: int
    error_type_breakdown: list[DashboardErrorTypeBreakdownItem]
    alerts_timeline: list[DashboardAlertTimelineItem]
    service_breakdown: list[DashboardBreakdownItem]
    route_breakdown: list[DashboardBreakdownItem]


class DashboardWidgetDefinition(BaseModel):
    widget_id: str
    type: Literal["card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"]
    title: str
    description: str | None = None
    order: int
    config: dict[str, Any] = {}


class DashboardWidgetPoint(BaseModel):
    widget_id: str
    timestamp: datetime
    label: str | None = None
    value: float


class DashboardWidgetPlacement(BaseModel):
    widget_id: str
    order: int
    section: str
    column_span: int = 1
    row_span: int = 1


class DashboardWidgetPageLayout(BaseModel):
    page_id: str
    title: str
    description: str | None = None
    order: int
    widgets: list[DashboardWidgetPlacement]


class DashboardWidgetLayout(BaseModel):
    default_page_id: str
    pages: list[DashboardWidgetPageLayout]
    unplaced_widget_ids: list[str] = []


class DashboardWidgetsResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    definitions: list[DashboardWidgetDefinition]
    points: list[DashboardWidgetPoint]
    layout: DashboardWidgetLayout | None = None


class DashboardRequestItem(BaseModel):
    timestamp: datetime
    method: str
    path: str
    status_code: int
    latency_ms: float
    service_name: str
    environment: str
    request_id: str | None = None
    log_message: str | None = None
    event_id: int | None = None
    received_at: datetime | None = None
    sdk_version: str | None = None
    event_kind: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


class DashboardRequestsResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    total: int
    limit: int
    offset: int
    items: list[DashboardRequestItem]


class DashboardErrorGroupItem(BaseModel):
    group_key: str
    exception_type: str | None
    message: str | None
    path: str
    count: int
    first_seen: datetime
    last_seen: datetime
    sample_stack_trace: str | None


class DashboardErrorGroupsResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    total: int
    limit: int
    offset: int
    items: list[DashboardErrorGroupItem]


class DashboardDiagnosisTimelineBucket(BaseModel):
    minute: datetime
    request_count: int
    error_count: int


class DashboardDiagnosisTimelineResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    buckets: list[DashboardDiagnosisTimelineBucket]


class DashboardDiagnosisFailureRouteItem(BaseModel):
    path: str
    failure_count: int
    error_rate: float
    avg_latency_ms: float


class DashboardDiagnosisFailureRoutesResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    items: list[DashboardDiagnosisFailureRouteItem]


class DashboardRecentJobFailureItem(BaseModel):
    timestamp: datetime
    job_name: str
    trigger: str
    status_code: int
    latency_ms: float
    service_name: str
    environment: str
    message: str | None = None
    correlated_request_id: str | None = None


class DashboardRecentJobFailuresResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    items: list[DashboardRecentJobFailureItem]


class DashboardDiagnosisErrorGroupEventItem(BaseModel):
    id: int
    timestamp: datetime
    method: str
    path: str
    status_code: int
    latency_ms: float
    service_name: str
    environment: str
    request_id: str | None = None
    stack_trace: str | None = None
    message: str | None = None
    exception_type: str | None = None


class DashboardDiagnosisErrorGroupEventsResponse(BaseModel):
    total: int
    items: list[DashboardDiagnosisErrorGroupEventItem]
