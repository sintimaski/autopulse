from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class IngestEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["request", "error"]
    timestamp: datetime
    service_name: str
    environment: str
    method: str
    path: str
    status_code: int
    latency_ms: float
    request_id: str | None = None

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class IngestBatchRequest(BaseModel):
    events: list[IngestEvent]
    sdk_version: str | None = None

    @field_validator("events")
    @classmethod
    def require_non_empty_batch(cls, value: list[IngestEvent]) -> list[IngestEvent]:
        if not value:
            raise ValueError("events must not be empty")
        return value


class IngestBatchResponse(BaseModel):
    accepted: int


class DashboardOverviewBucket(BaseModel):
    minute: datetime
    request_count: int
    error_count: int
    avg_latency_ms: float
    count_2xx: int
    count_3xx: int
    count_4xx: int
    count_5xx: int


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


class DashboardBreakdownItem(BaseModel):
    key: str
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float


class DashboardOverviewExtendedResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_burst_count: int
    active_incident_count: int
    service_breakdown: list[DashboardBreakdownItem]
    route_breakdown: list[DashboardBreakdownItem]


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


class DashboardAlertSettings(BaseModel):
    enabled: bool
    destination_email: str | None = None
    error_spike_ratio_threshold: float
    error_spike_min_requests: int
    error_spike_window_minutes: int
    outage_min_requests: int
    outage_window_minutes: int
    cooldown_minutes: int


class DashboardAlertSettingsUpdate(BaseModel):
    enabled: bool
    destination_email: str | None = None
    error_spike_ratio_threshold: float
    error_spike_min_requests: int
    error_spike_window_minutes: int
    outage_min_requests: int
    outage_window_minutes: int
    cooldown_minutes: int

    @field_validator("destination_email")
    @classmethod
    def normalize_destination_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("error_spike_ratio_threshold")
    @classmethod
    def validate_error_spike_ratio_threshold(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("error_spike_ratio_threshold must be between 0 and 1")
        return value

    @field_validator(
        "error_spike_min_requests",
        "error_spike_window_minutes",
        "outage_min_requests",
        "outage_window_minutes",
        "cooldown_minutes",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value


class DashboardAlertDispatchItem(BaseModel):
    id: int
    alert_type: str
    destination_email: str | None
    delivered_via: str
    triggered_at: datetime
    window_start: datetime
    window_end: datetime
    detail: dict[str, Any]


class DashboardAlertDispatchesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DashboardAlertDispatchItem]


class DashboardThemeSettings(BaseModel):
    theme_preference: Literal["system", "light", "dark"]
    exclude_autopulse_traffic: bool


class DashboardThemeSettingsUpdate(BaseModel):
    theme_preference: Literal["system", "light", "dark"]
    exclude_autopulse_traffic: bool


class DashboardRetentionSettings(BaseModel):
    raw_events_days: int
    logs_query_max_window_minutes: int


class DashboardRetentionSettingsUpdate(BaseModel):
    raw_events_days: int
    logs_query_max_window_minutes: int

    @field_validator("raw_events_days", "logs_query_max_window_minutes")
    @classmethod
    def validate_positive_values(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value


class DashboardLogQueryRequest(BaseModel):
    query: str
    cursor: str | None = None
    page_size: int = 100
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        return max(1, min(value, 200))


class DashboardLogQueryValidationResponse(BaseModel):
    valid: bool
    normalized_query: str
    error: str | None = None


class DashboardLogQueryItem(BaseModel):
    id: int
    timestamp: datetime
    method: str
    path: str
    status_code: int
    latency_ms: float
    service_name: str
    environment: str
    request_id: str | None = None


class DashboardLogQueryPageResponse(BaseModel):
    server_now: datetime
    query: str
    next_cursor: str | None
    items: list[DashboardLogQueryItem]


class DashboardMagicLinkRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must be valid")
        return normalized


class DashboardMagicLinkRequestResponse(BaseModel):
    accepted: bool
    expires_in_seconds: int
    dev_magic_link_token: str | None = None


class DashboardMagicLinkVerifyRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("token must not be empty")
        return normalized


class DashboardSessionResponse(BaseModel):
    authenticated: bool
    email: str | None = None
    expires_at: datetime | None = None


def event_payload(event: IngestEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
