from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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


class DashboardWidgetsResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    definitions: list[DashboardWidgetDefinition]
    points: list[DashboardWidgetPoint]


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


class DashboardDataQueryScope(BaseModel):
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    window_minutes: int = 60
    method: str | None = None
    status_class: int | None = None
    path_contains: str | None = None
    environments: str | None = None
    services: str | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    event_sql_filter: str | None = None


class DashboardDataQueryPagination(BaseModel):
    limit: int = 100
    offset: int = 0


class DashboardDataQueryRequest(BaseModel):
    scope: DashboardDataQueryScope
    include_extended: bool = False
    include_widgets: bool = False
    include_error_groups: bool = False
    include_diagnosis: bool = False
    include_alert_dispatches: bool = False
    include_recent_job_failures: bool = False
    requests: DashboardDataQueryPagination = DashboardDataQueryPagination()
    error_groups: DashboardDataQueryPagination = DashboardDataQueryPagination(limit=25, offset=0)
    alert_dispatches: DashboardDataQueryPagination = DashboardDataQueryPagination(
        limit=25, offset=0
    )
    diagnosis_error_group_key: str | None = None
    diagnosis_error_group_events: DashboardDataQueryPagination = DashboardDataQueryPagination(
        limit=20, offset=0
    )

    @model_validator(mode="before")
    @classmethod
    def clamp_query_pagination(cls, data: Any) -> Any:
        """Prevent oversized bundle responses from abusive client limits."""
        if not isinstance(data, dict):
            return data
        out = dict(data)

        def _clamp_section(key: str, *, max_limit: int) -> None:
            section = out.get(key)
            if not isinstance(section, dict):
                return
            s = dict(section)
            try:
                lim = int(s.get("limit", max_limit))
            except (TypeError, ValueError):
                lim = max_limit
            try:
                off = int(s.get("offset", 0))
            except (TypeError, ValueError):
                off = 0
            s["limit"] = min(max(lim, 1), max_limit)
            s["offset"] = max(off, 0)
            out[key] = s

        _clamp_section("requests", max_limit=250)
        _clamp_section("error_groups", max_limit=100)
        _clamp_section("alert_dispatches", max_limit=100)
        _clamp_section("diagnosis_error_group_events", max_limit=100)
        return out


class DashboardDataQueryResponse(BaseModel):
    overview: DashboardOverviewResponse
    overview_extended: DashboardOverviewExtendedResponse | None = None
    widgets: DashboardWidgetsResponse | None = None
    requests: DashboardRequestsResponse
    error_groups: DashboardErrorGroupsResponse | None = None
    diagnosis_timeline: DashboardDiagnosisTimelineResponse | None = None
    diagnosis_failures: DashboardDiagnosisFailureRoutesResponse | None = None
    diagnosis_error_group_events: DashboardDiagnosisErrorGroupEventsResponse | None = None
    recent_job_failures: DashboardRecentJobFailuresResponse | None = None
    alert_dispatches: DashboardAlertDispatchesResponse | None = None


class DashboardBootstrapResponse(BaseModel):
    retention_settings: DashboardRetentionSettings
    alert_settings: DashboardAlertSettings
    theme_settings: DashboardThemeSettings
    api_keys: DashboardApiKeyListResponse
    alert_capabilities: DashboardAlertCapabilitiesResponse
    onboarding_status: DashboardOnboardingStatusResponse | None = None


class DashboardInternalMetricsResponse(BaseModel):
    enabled: bool
    reason: str | None = None
    metrics: dict[str, Any] | None = None


class DashboardAlertSettings(BaseModel):
    enabled: bool
    destination_email: str | None = None
    email_enabled: bool = True
    slack_enabled: bool = False
    slack_webhook_url: str | None = None
    discord_enabled: bool = False
    discord_webhook_url: str | None = None
    webhook_enabled: bool = False
    webhook_url: str | None = None
    error_spike_ratio_threshold: float
    error_spike_min_requests: int
    error_spike_window_minutes: int
    outage_min_requests: int
    outage_window_minutes: int
    cooldown_minutes: int


class DashboardAlertSettingsUpdate(BaseModel):
    enabled: bool
    destination_email: str | None = None
    email_enabled: bool = True
    slack_enabled: bool = False
    slack_webhook_url: str | None = None
    discord_enabled: bool = False
    discord_webhook_url: str | None = None
    webhook_enabled: bool = False
    webhook_url: str | None = None
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

    @field_validator("slack_webhook_url", "discord_webhook_url", "webhook_url")
    @classmethod
    def normalize_optional_webhook_url(cls, value: str | None) -> str | None:
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
    reason_message: str | None = None
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


class DashboardAlertChannelCapability(BaseModel):
    channel: Literal["email", "slack", "discord", "webhook"]
    status: Literal["active", "configured", "planned", "unavailable"]
    enabled: bool
    reason: str


class DashboardAlertCapabilitiesResponse(BaseModel):
    channels: list[DashboardAlertChannelCapability]


class DashboardAlertTestResponse(BaseModel):
    status: str
    delivered_via: str
    reason_code: str | None = None
    reason_message: str | None = None
    attempt_count: int
    delivered_at: datetime | None = None
    provider_message_id: str | None = None
    destination_email: str | None = None


class DashboardThemeSettings(BaseModel):
    theme_preference: Literal["system", "light", "dark"]
    exclude_autopulse_traffic: bool


class DashboardThemeSettingsUpdate(BaseModel):
    theme_preference: Literal["system", "light", "dark"]
    exclude_autopulse_traffic: bool


class DashboardEventPlaneCutoverSettings(BaseModel):
    use_snapshot_read: bool


class DashboardEventPlaneCutoverSettingsUpdate(BaseModel):
    use_snapshot_read: bool


class DashboardRetentionSettings(BaseModel):
    raw_events_days: int
    logs_query_max_window_minutes: int
    retention_max_db_size_mb: int | None = None
    retention_max_log_rows: int | None = None
    retention_plan: Literal["starter", "standard", "extended"] = "standard"
    archival_enabled: bool = False
    archival_mode: Literal["db_archive"] = "db_archive"
    archival_status: Literal["idle", "running", "failed"] = "idle"
    archival_last_success_at: datetime | None = None
    archival_last_error: str | None = None


class DashboardRetentionSettingsUpdate(BaseModel):
    raw_events_days: int
    logs_query_max_window_minutes: int
    retention_max_db_size_mb: int | None = None
    retention_max_log_rows: int | None = None
    retention_plan: Literal["starter", "standard", "extended"] = "standard"
    archival_enabled: bool = False
    archival_mode: Literal["db_archive"] = "db_archive"

    @field_validator("raw_events_days", "logs_query_max_window_minutes")
    @classmethod
    def validate_positive_values(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value

    @field_validator("retention_max_db_size_mb", "retention_max_log_rows")
    @classmethod
    def validate_optional_positive_values(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1:
            raise ValueError("must be at least 1 when set")
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


class DashboardQueryExplorerRequest(BaseModel):
    query: str
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    window_minutes: int = 60
    row_limit: int = 200

    @field_validator("window_minutes")
    @classmethod
    def validate_window_minutes(cls, value: int) -> int:
        return max(1, min(value, 10_080))

    @field_validator("row_limit")
    @classmethod
    def validate_row_limit(cls, value: int) -> int:
        return max(1, min(value, 500))


class DashboardQueryExplorerResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    query: str
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


class DashboardTraceSpanItem(BaseModel):
    timestamp: datetime
    service_name: str
    environment: str
    span_name: str
    path: str
    method: str
    status_code: int
    latency_ms: float
    trace_id: str
    span_id: str | None = None
    parent_span_id: str | None = None
    request_id: str | None = None
    otlp_status_code: int | None = None


class DashboardTraceSummaryItem(BaseModel):
    trace_id: str
    first_seen: datetime
    last_seen: datetime
    span_count: int
    error_count: int
    services: list[str]
    root_span_name: str | None = None


class DashboardTraceSearchResponse(BaseModel):
    server_now: datetime
    from_timestamp: datetime
    to_timestamp: datetime
    project_id: UUID
    total: int
    items: list[DashboardTraceSummaryItem]


class DashboardTraceDetailResponse(BaseModel):
    trace_id: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    error_count: int
    items: list[DashboardTraceSpanItem]


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
    dev_token: str | None = None
    dev_magic_link_url: str | None = None


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
    membership_role: Literal["owner", "admin", "member", "viewer"] | None = None


class DashboardSetActiveProjectRequest(BaseModel):
    """Switch the signed-in session to another project the user may access."""

    project_id: UUID


class DashboardOnboardingStatusResponse(BaseModel):
    session_authenticated: bool
    project_ready: bool
    ingest_key_ready: bool
    first_event_received: bool
    first_diagnostic_signal_ready: bool
    onboarding_completed: bool
    next_recommended_action: str = ""
    current_step: Literal[
        "authenticate_session",
        "confirm_project",
        "provision_ingest_key",
        "send_first_event",
        "open_diagnosis",
        "completed",
    ]


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
    role: Literal["owner", "admin", "member", "viewer"]


class DashboardOrganizationListResponse(BaseModel):
    organizations: list[DashboardOrganizationSummary]


class DashboardMembershipItem(BaseModel):
    user_id: str
    email: str
    role: Literal["owner", "admin", "member", "viewer"]
    invited_email: str | None = None
    created_at: datetime


class DashboardMembershipListResponse(BaseModel):
    organization_id: str
    members: list[DashboardMembershipItem]


class DashboardInviteMemberRequest(BaseModel):
    email: str
    role: Literal["owner", "admin", "member", "viewer"] = "member"

    @field_validator("email")
    @classmethod
    def normalize_invite_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must be valid")
        return normalized


class DashboardUpdateMemberRoleRequest(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]


class DashboardBookmarkItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    pathname: str
    query_string: str | None = None
    hash_fragment: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    project_id: UUID
    project_name: str = ""


class DashboardBookmarksListResponse(BaseModel):
    items: list[DashboardBookmarkItem]


class DashboardBookmarkCreate(BaseModel):
    title: str
    pathname: str
    query_string: str | None = None
    hash_fragment: str | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        t = value.strip()
        if not t:
            raise ValueError("title is required")
        if len(t) > 200:
            raise ValueError("title too long")
        return t

    @field_validator("pathname")
    @classmethod
    def validate_pathname(cls, value: str) -> str:
        p = value.strip()
        if not p.startswith("/") or len(p) > 512:
            raise ValueError("invalid pathname")
        if ".." in p or "//" in p or "\n" in p or "\r" in p:
            raise ValueError("invalid pathname")
        return p

    @field_validator("query_string")
    @classmethod
    def validate_query_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        q = value.strip()
        if not q:
            return None
        if len(q) > 8192:
            raise ValueError("query_string too long")
        return q

    @field_validator("hash_fragment")
    @classmethod
    def validate_hash_fragment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        h = value.strip()
        if h.startswith("#"):
            h = h[1:]
        if not h:
            return None
        if len(h) > 2048:
            raise ValueError("hash_fragment too long")
        return h

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        n = value.strip()
        if not n:
            return None
        if len(n) > 8000:
            raise ValueError("notes too long")
        return n


class DashboardBookmarkUpdate(BaseModel):
    title: str | None = None
    pathname: str | None = None
    query_string: str | None = None
    hash_fragment: str | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        t = value.strip()
        if not t:
            raise ValueError("title cannot be empty")
        if len(t) > 200:
            raise ValueError("title too long")
        return t

    @field_validator("pathname")
    @classmethod
    def validate_pathname_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        p = value.strip()
        if not p.startswith("/") or len(p) > 512:
            raise ValueError("invalid pathname")
        if ".." in p or "//" in p or "\n" in p or "\r" in p:
            raise ValueError("invalid pathname")
        return p

    @field_validator("query_string")
    @classmethod
    def validate_query_string_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        q = value.strip()
        if not q:
            return None
        if len(q) > 8192:
            raise ValueError("query_string too long")
        return q

    @field_validator("hash_fragment")
    @classmethod
    def validate_hash_fragment_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        h = value.strip()
        if h.startswith("#"):
            h = h[1:]
        if not h:
            return None
        if len(h) > 2048:
            raise ValueError("hash_fragment too long")
        return h

    @field_validator("notes")
    @classmethod
    def validate_notes_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        n = value.strip()
        if not n:
            return None
        if len(n) > 8000:
            raise ValueError("notes too long")
        return n
