from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    key_salt: Mapped[bytes] = mapped_column(nullable=False)
    key_hash: Mapped[bytes] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_project_timestamp_desc", "project_id", "timestamp"),
        Index("ix_events_project_type_timestamp_desc", "project_id", "type", "timestamp"),
        Index("ix_events_project_path_timestamp_desc", "project_id", "path", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sdk_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectAlertSettings(Base):
    __tablename__ = "project_alert_settings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    destination_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    error_spike_ratio_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    error_spike_min_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    error_spike_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    outage_min_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    outage_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    last_error_spike_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_outage_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProjectUiSettings(Base):
    __tablename__ = "project_ui_settings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    theme_preference: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    exclude_autopulse_traffic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retention_raw_events_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logs_query_max_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1440
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertDispatch(Base):
    __tablename__ = "alert_dispatches"
    __table_args__ = (
        Index("ix_alert_dispatches_project_triggered_at", "project_id", "triggered_at"),
        Index(
            "ix_alert_dispatches_project_type_triggered_at",
            "project_id",
            "alert_type",
            "triggered_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    destination_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    delivered_via: Mapped[str] = mapped_column(String(32), nullable=False, default="stub")
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
