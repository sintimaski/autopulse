from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HEX_DIGITS = frozenset("0123456789abcdef")


def _normalize_hex_id(value: str | None, *, length: int, label: str) -> str | None:
    """Lowercase + validate a fixed-length hex id (W3C / OTLP trace and span ids).

    Empty / missing values normalize to ``None``; malformed ids are rejected so
    junk never reaches the traces explorer's ``json_extract_string`` lookups.
    """
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if len(normalized) != length or any(char not in _HEX_DIGITS for char in normalized):
        raise ValueError(f"{label} must be {length}-char lowercase hex")
    return normalized


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
    # Lightweight per-request trace context. The SDK middleware stamps a span on
    # every captured request (continuing an inbound W3C ``traceparent`` when
    # present); the OTLP ingest path fills the same fields from real spans. Stored
    # in the event payload so the traces explorer can group/expand them. Ids are
    # normalized to lowercase hex (32 chars for trace, 16 for span) or dropped.
    trace_id: str | None = Field(default=None, max_length=32)
    span_id: str | None = Field(default=None, max_length=16)
    parent_span_id: str | None = Field(default=None, max_length=16)
    span_name: str | None = Field(default=None, max_length=255)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("trace_id")
    @classmethod
    def normalize_trace_id(cls, value: str | None) -> str | None:
        return _normalize_hex_id(value, length=32, label="trace_id")

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def normalize_span_id(cls, value: str | None) -> str | None:
        return _normalize_hex_id(value, length=16, label="span_id")

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
