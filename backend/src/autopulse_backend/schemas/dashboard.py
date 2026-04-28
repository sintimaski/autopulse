from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator


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
    status: str
    reason_code: str | None = None
    attempt_count: int
    triggered_at: datetime
    window_start: datetime
    window_end: datetime
    delivered_at: datetime | None = None
    provider_message_id: str | None = None
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
    retention_plan: Literal["starter", "standard", "extended"] = "standard"
    archival_enabled: bool = False
    archival_mode: Literal["db_archive"] = "db_archive"
    archival_status: Literal["idle", "running", "failed"] = "idle"
    archival_last_success_at: datetime | None = None
    archival_last_error: str | None = None


class DashboardRetentionSettingsUpdate(BaseModel):
    raw_events_days: int
    logs_query_max_window_minutes: int
    retention_plan: Literal["starter", "standard", "extended"] = "standard"
    archival_enabled: bool = False
    archival_mode: Literal["db_archive"] = "db_archive"

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
    project_id: str | None = None
    organization_id: str | None = None
    membership_role: Literal["owner", "member"] | None = None


class DashboardBootstrapTenantRequest(BaseModel):
    organization_name: str = "Default Organization"
    project_name: str = "Default Project"

    @field_validator("organization_name", "project_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized[:255]


class DashboardBootstrapTenantResponse(BaseModel):
    organization_id: str
    project_id: str
    organization_name: str
    project_name: str
    api_key: str


class DashboardApiKeyItem(BaseModel):
    key_id: str
    created_at: datetime
    revoked_at: datetime | None = None


class DashboardApiKeyListResponse(BaseModel):
    items: list[DashboardApiKeyItem]


class DashboardApiKeyIssueResponse(BaseModel):
    key_id: str
    api_key: str
    created_at: datetime


class DashboardApiKeyRotateRequest(BaseModel):
    key_id: str

    @field_validator("key_id")
    @classmethod
    def normalize_key_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("key_id must not be empty")
        return normalized


class DashboardApiKeyRotateResponse(BaseModel):
    revoked_key_id: str
    replacement_key_id: str
    replacement_api_key: str
    rotated_at: datetime


class DashboardApiKeyRevokeRequest(BaseModel):
    key_id: str

    @field_validator("key_id")
    @classmethod
    def normalize_revoke_key_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("key_id must not be empty")
        return normalized


class DashboardProjectSummary(BaseModel):
    project_id: str
    project_name: str
    organization_id: str | None = None


class DashboardOrganizationSummary(BaseModel):
    organization_id: str
    organization_name: str
    projects: list[DashboardProjectSummary]
    role: Literal["owner", "member"]


class DashboardOrganizationListResponse(BaseModel):
    organizations: list[DashboardOrganizationSummary]


class DashboardMembershipItem(BaseModel):
    user_id: str
    email: str
    role: Literal["owner", "member"]
    invited_email: str | None = None
    created_at: datetime


class DashboardMembershipListResponse(BaseModel):
    organization_id: str
    members: list[DashboardMembershipItem]


class DashboardInviteMemberRequest(BaseModel):
    email: str
    role: Literal["owner", "member"] = "member"

    @field_validator("email")
    @classmethod
    def normalize_invite_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must be valid")
        return normalized


class DashboardUpdateMemberRoleRequest(BaseModel):
    role: Literal["owner", "member"]
