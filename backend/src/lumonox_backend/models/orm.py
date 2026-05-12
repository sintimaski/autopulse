from __future__ import annotations

from datetime import UTC, datetime
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
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLite has no now(); CURRENT_TIMESTAMP is valid on Postgres and SQLite for timestamptz columns.
_TS_DEFAULT = text("CURRENT_TIMESTAMP")


def _utc_now() -> datetime:
    """ORM insert/update default so SQLite never evaluates legacy DDL ``now()`` on old files."""
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
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
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
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


class MetricBucket(Base):
    __tablename__ = "metric_buckets"
    __table_args__ = (
        Index("ix_metric_buckets_project_minute", "project_id", "minute_start"),
        Index(
            "ux_metric_buckets_project_minute_service_env",
            "project_id",
            "minute_start",
            "service_name",
            "environment",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    minute_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False, default="unknown")
    environment: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    count_2xx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count_3xx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count_4xx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count_5xx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class ErrorGroupAggregate(Base):
    __tablename__ = "error_group_aggregates"
    __table_args__ = (
        Index("ix_error_group_aggregates_project_last_seen", "project_id", "last_seen"),
        Index(
            "ux_error_group_aggregates_project_group_key",
            "project_id",
            "group_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    group_key: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    exception_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class DashboardWidgetDefinition(Base):
    __tablename__ = "dashboard_widget_definitions"
    __table_args__ = (
        Index("ix_dashboard_widget_definitions_project_order", "project_id", "display_order"),
        Index(
            "ux_dashboard_widget_definitions_project_widget_id",
            "project_id",
            "widget_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    widget_id: Mapped[str] = mapped_column(String(128), nullable=False)
    widget_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class DashboardWidgetPoint(Base):
    __tablename__ = "dashboard_widget_points"
    __table_args__ = (
        Index("ix_dashboard_widget_points_project_timestamp", "project_id", "timestamp"),
        Index("ix_dashboard_widget_points_project_widget_id", "project_id", "widget_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    widget_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class IngestRateLimitWindow(Base):
    __tablename__ = "ingest_rate_limit_windows"
    __table_args__ = (
        Index(
            "ux_ingest_rate_limit_windows_project_window",
            "project_id",
            "window_start",
            unique=True,
        ),
        Index("ix_ingest_rate_limit_windows_window_start", "window_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class SchedulerJobLease(Base):
    __tablename__ = "scheduler_job_leases"
    __table_args__ = (
        Index("ux_scheduler_job_leases_job_name", "job_name", unique=True),
        Index("ix_scheduler_job_leases_expires_at", "lease_expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_token: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


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
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    slack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    discord_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discord_webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
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
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
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
    exclude_lumonox_traffic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    event_plane_use_snapshot_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    retention_raw_events_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_max_db_size_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_max_log_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_plan: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    archival_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archival_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="db_archive")
    archival_status: Mapped[str] = mapped_column(String(16), nullable=False, default="idle")
    archival_last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archival_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_query_max_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1440
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
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
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent")
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ArchivedEvent(Base):
    __tablename__ = "archived_events"
    __table_args__ = (
        Index("ix_archived_events_project_archived_at", "project_id", "archived_at"),
        Index("ix_archived_events_original_event_id", "original_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        Index("ix_org_memberships_org_user", "organization_id", "user_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    invited_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class GovernanceAuditEvent(Base):
    __tablename__ = "governance_audit_events"
    __table_args__ = (Index("ix_governance_audit_org_created_at", "organization_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idp_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idp_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DashboardMagicLink(Base):
    __tablename__ = "dashboard_magic_links"
    __table_args__ = (
        Index("ix_dashboard_magic_links_email_created_at", "email", "created_at"),
        Index("ix_dashboard_magic_links_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DashboardSession(Base):
    __tablename__ = "dashboard_sessions"
    __table_args__ = (
        Index("ix_dashboard_sessions_expires_at", "expires_at"),
        Index("ix_dashboard_sessions_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DashboardIncidentShare(Base):
    """Durable incident handoff links: scoped dashboard query + optional user ACL."""

    __tablename__ = "dashboard_incident_shares"
    __table_args__ = (
        Index("ix_dashboard_incident_shares_project_created", "project_id", "created_at"),
        Index("ix_dashboard_incident_shares_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(nullable=False, unique=True)
    scope_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    access_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_user_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )


class DashboardUserBookmark(Base):
    """Per-user saved deep links within a project (dashboard UI paths + query + hash)."""

    __tablename__ = "dashboard_user_bookmarks"
    __table_args__ = (
        Index(
            "ix_dashboard_user_bookmarks_user_project_updated",
            "user_id",
            "project_id",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("dashboard_users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    pathname: Mapped[str] = mapped_column(String(512), nullable=False)
    query_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_fragment: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=_TS_DEFAULT,
        onupdate=_utc_now,
    )


class IngestIdempotencyKey(Base):
    """Optional HTTP Idempotency-Key dedupe for ``POST /ingest`` (per project)."""

    __tablename__ = "ingest_idempotency_keys"
    __table_args__ = (
        UniqueConstraint("project_id", "key_hash", name="ux_ingest_idempotency_project_key"),
        Index("ix_ingest_idempotency_project_reserved", "project_id", "reserved_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_events: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IngestAggregateDeadLetter(Base):
    """Persisted aggregate upserts that exhausted the async worker retry budget."""

    __tablename__ = "ingest_aggregate_dead_letters"
    __table_args__ = (Index("ix_ingest_agg_dl_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestSqlTailRepairItem(Base):
    """Durable replay queue for SQL-tail writes that failed after DuckDB ingest succeeded."""

    __tablename__ = "ingest_sql_tail_repair_items"
    __table_args__ = (
        Index(
            "ix_ingest_sql_tail_repair_pending", "resolved_at", "dead_lettered_at", "next_retry_at"
        ),
        Index("ix_ingest_sql_tail_repair_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, server_default=_TS_DEFAULT
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
