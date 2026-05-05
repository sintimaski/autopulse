from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RumValue = str | int | float | bool | None


class DashboardRumEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["route_view", "runtime_error", "unhandled_rejection", "session_performance"]
    path: str = Field(min_length=1, max_length=160)
    session_id: str = Field(min_length=8, max_length=128)
    ts: datetime
    data: dict[str, RumValue] = Field(default_factory=dict)

    @field_validator("ts")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        text = value.strip() or "/"
        if not text.startswith("/"):
            text = f"/{text}"
        return text[:160]

    @model_validator(mode="after")
    def validate_data(self) -> DashboardRumEvent:
        if len(self.data) > 24:
            raise ValueError("data contains too many fields")
        for key, value in self.data.items():
            if len(key) > 64:
                raise ValueError("data key is too long")
            if isinstance(value, str) and len(value) > 240:
                raise ValueError("data string value is too long")
        return self


class DashboardRumIngestResponse(BaseModel):
    accepted: bool
