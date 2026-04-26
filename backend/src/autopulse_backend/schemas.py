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


class DashboardOverviewResponse(BaseModel):
    from_timestamp: datetime
    to_timestamp: datetime
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    requests_per_minute: float
    series: list[DashboardOverviewBucket]


class DashboardRequestItem(BaseModel):
    timestamp: datetime
    method: str
    path: str
    status_code: int
    latency_ms: float
    service_name: str
    environment: str
    request_id: str | None = None


class DashboardRequestsResponse(BaseModel):
    from_timestamp: datetime
    to_timestamp: datetime
    total: int
    limit: int
    offset: int
    items: list[DashboardRequestItem]


def event_payload(event: IngestEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
