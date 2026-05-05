from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IngestEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["request", "error", "job"]
    timestamp: datetime
    service_name: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=120)
    method: str = Field(min_length=1, max_length=24)
    path: str = Field(min_length=1, max_length=2048)
    status_code: int
    latency_ms: float
    request_id: str | None = Field(default=None, max_length=128)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_job_and_extra_limits(self) -> IngestEvent:
        if self.type == "job":
            label = self.method.strip().upper()
            if label not in {"JOB", "CRON"}:
                raise ValueError("job events must use method JOB or CRON (cron vs ad-hoc work)")
        if len(self.model_extra or {}) > 32:
            raise ValueError("event contains too many additional fields")
        return self


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


def event_payload(event: IngestEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
