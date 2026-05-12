"""Incident scope query strings (URL keys aligned with frontend ``buildScopedQuery``)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUEST_LIMIT_OPTIONS = frozenset({50, 100, 200})
ERROR_GROUP_LIMIT_OPTIONS = frozenset({10, 25, 50})


class DashboardIncidentScopedState(BaseModel):
    """Mirror of frontend ``DashboardScopedQueryState`` (camelCase aliases)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    is_absolute_window: bool = Field(default=False, alias="isAbsoluteWindow")
    window_minutes: int = Field(default=60, alias="windowMinutes")
    window_from_timestamp: str = Field(default="", alias="windowFromTimestamp")
    window_to_timestamp: str = Field(default="", alias="windowToTimestamp")
    method: str = Field(default="ALL", alias="method")
    status_class: str = Field(default="ALL", alias="statusClass")
    min_latency_ms: str = Field(default="", alias="minLatencyMs")
    max_latency_ms: str = Field(default="", alias="maxLatencyMs")
    path_query: str = Field(default="", alias="pathQuery")
    server_environment_query: str = Field(default="", alias="serverEnvironmentQuery")
    server_service_query: str = Field(default="", alias="serverServiceQuery")
    request_limit: int = Field(default=100, alias="requestLimit")
    request_page: int = Field(default=0, alias="requestPage")
    error_group_limit: int = Field(default=25, alias="errorGroupLimit")
    error_group_page: int = Field(default=0, alias="errorGroupPage")
    error_group_sort: str = Field(default="last_seen", alias="errorGroupSort")
    correlation_request_id: str = Field(default="", alias="correlationRequestId")
    sql_filter_applied: str | None = Field(default="", alias="sqlFilterApplied")
    sql_filter_enabled: bool | None = Field(default=False, alias="sqlFilterEnabled")

    @field_validator("error_group_sort")
    @classmethod
    def validate_error_group_sort(cls, value: str) -> str:
        return "count" if value == "count" else "last_seen"

    @field_validator("request_limit")
    @classmethod
    def validate_request_limit(cls, value: int) -> int:
        return value if value in REQUEST_LIMIT_OPTIONS else 100

    @field_validator("error_group_limit")
    @classmethod
    def validate_error_group_limit(cls, value: int) -> int:
        return value if value in ERROR_GROUP_LIMIT_OPTIONS else 25


def normalize_comma_separated(value: str) -> str:
    return ",".join(part.strip() for part in value.split(",") if part.strip())


def scoped_state_to_query_string(state: DashboardIncidentScopedState) -> str:
    params: dict[str, str] = {}
    if (
        state.is_absolute_window
        and state.window_from_timestamp.strip()
        and state.window_to_timestamp.strip()
    ):
        params["from_timestamp"] = state.window_from_timestamp.strip()
        params["to_timestamp"] = state.window_to_timestamp.strip()
    else:
        params["window_minutes"] = str(max(1, state.window_minutes))

    if state.method != "ALL":
        params["method"] = state.method
    if state.status_class != "ALL":
        params["status_class"] = state.status_class
    path = state.path_query.strip()
    if path:
        params["path_contains"] = path
    if state.min_latency_ms.strip():
        params["min_latency_ms"] = state.min_latency_ms.strip()
    if state.max_latency_ms.strip():
        params["max_latency_ms"] = state.max_latency_ms.strip()

    env_csv = normalize_comma_separated(state.server_environment_query)
    if env_csv:
        params["environments"] = env_csv
    svc_csv = normalize_comma_separated(state.server_service_query)
    if svc_csv:
        params["services"] = svc_csv

    if state.request_limit != 100:
        params["request_limit"] = str(state.request_limit)
    if state.request_page > 0:
        params["request_page"] = str(state.request_page)
    if state.error_group_limit != 25:
        params["error_group_limit"] = str(state.error_group_limit)
    if state.error_group_page > 0:
        params["error_group_page"] = str(state.error_group_page)
    if state.error_group_sort == "count":
        params["error_group_sort"] = "count"

    corr = state.correlation_request_id.strip()[:128]
    if corr:
        params["correlation"] = corr

    applied = (state.sql_filter_applied or "").strip()
    if state.sql_filter_enabled and applied:
        params["sql_filter"] = applied

    return urlencode(params)


def parse_scoped_state_payload(raw: dict[str, Any]) -> DashboardIncidentScopedState:
    return DashboardIncidentScopedState.model_validate(raw)
