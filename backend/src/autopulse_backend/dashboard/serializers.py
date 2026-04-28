from __future__ import annotations

from autopulse_backend.models import ProjectAlertSettings, ProjectUiSettings
from autopulse_backend.schemas import (
    DashboardAlertSettings,
    DashboardRetentionSettings,
    DashboardThemeSettings,
)


def serialize_alert_settings(settings: ProjectAlertSettings) -> DashboardAlertSettings:
    return DashboardAlertSettings(
        enabled=settings.enabled,
        destination_email=settings.destination_email,
        error_spike_ratio_threshold=float(settings.error_spike_ratio_threshold),
        error_spike_min_requests=int(settings.error_spike_min_requests),
        error_spike_window_minutes=int(settings.error_spike_window_minutes),
        outage_min_requests=int(settings.outage_min_requests),
        outage_window_minutes=int(settings.outage_window_minutes),
        cooldown_minutes=int(settings.cooldown_minutes),
    )


def serialize_theme_settings(settings: ProjectUiSettings) -> DashboardThemeSettings:
    theme = (
        settings.theme_preference
        if settings.theme_preference in {"system", "light", "dark"}
        else "system"
    )
    return DashboardThemeSettings(
        theme_preference=theme,
        exclude_autopulse_traffic=bool(settings.exclude_autopulse_traffic),
    )


def serialize_retention_settings(
    settings: ProjectUiSettings,
    fallback_days: int,
    fallback_query_window_minutes: int,
) -> DashboardRetentionSettings:
    raw_days = (
        int(settings.retention_raw_events_days)
        if settings.retention_raw_events_days
        else fallback_days
    )
    return DashboardRetentionSettings(
        raw_events_days=max(1, raw_days),
        logs_query_max_window_minutes=max(
            1, int(settings.logs_query_max_window_minutes or fallback_query_window_minutes)
        ),
        retention_plan=(
            settings.retention_plan
            if settings.retention_plan in {"starter", "standard", "extended"}
            else "standard"
        ),
        archival_enabled=bool(settings.archival_enabled),
        archival_mode="db_archive",
        archival_status=(
            settings.archival_status
            if settings.archival_status in {"idle", "running", "failed"}
            else "idle"
        ),
        archival_last_success_at=settings.archival_last_success_at,
        archival_last_error=settings.archival_last_error,
    )
