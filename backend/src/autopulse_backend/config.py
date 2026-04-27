from __future__ import annotations

from dataclasses import dataclass
from os import getenv


def _env_bool(name: str, default: bool) -> bool:
    raw = getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    if minimum is not None:
        return max(value, minimum)
    return value


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            value = default
    if minimum is not None:
        return max(value, minimum)
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    cors_allow_origins: tuple[str, ...]
    ingest_max_request_bytes: int = 1_048_576
    ingest_rate_limit_requests_per_window: int = 1200
    ingest_rate_limit_window_seconds: int = 60
    default_sdk_version: str = "unknown"
    alerts_enabled: bool = True
    alert_default_destination_email: str | None = None
    alert_error_spike_ratio_threshold: float = 0.4
    alert_error_spike_min_requests: int = 20
    alert_error_spike_window_minutes: int = 5
    alert_outage_min_requests: int = 10
    alert_outage_window_minutes: int = 5
    alert_cooldown_minutes: int = 15
    retention_raw_events_days: int = 14
    logs_query_max_window_minutes: int = 1440
    jobs_enable_scheduler: bool = False
    jobs_alert_interval_seconds: float = 60.0
    jobs_retention_interval_seconds: float = 3600.0
    alert_sender_mode: str = "stub"
    alert_webhook_url: str | None = None
    dev_scenarios_enabled: bool = False
    dev_scenarios_max_duration_seconds: int = 180
    dev_scenarios_max_events: int = 5000


def get_settings() -> Settings:
    raw_cors_origins = getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    cors_allow_origins = tuple(
        origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()
    )
    return Settings(
        database_url=getenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db"),
        cors_allow_origins=cors_allow_origins,
        ingest_max_request_bytes=_env_int("INGEST_MAX_REQUEST_BYTES", 1_048_576, minimum=1),
        ingest_rate_limit_requests_per_window=_env_int(
            "INGEST_RATE_LIMIT_REQUESTS_PER_WINDOW",
            1200,
            minimum=0,
        ),
        ingest_rate_limit_window_seconds=_env_int(
            "INGEST_RATE_LIMIT_WINDOW_SECONDS",
            60,
            minimum=1,
        ),
        alerts_enabled=_env_bool("ALERTS_ENABLED", True),
        alert_default_destination_email=getenv("ALERT_DEFAULT_DESTINATION_EMAIL"),
        alert_error_spike_ratio_threshold=_env_float(
            "ALERT_ERROR_SPIKE_RATIO_THRESHOLD",
            0.4,
            minimum=0.0,
        ),
        alert_error_spike_min_requests=_env_int(
            "ALERT_ERROR_SPIKE_MIN_REQUESTS",
            20,
            minimum=1,
        ),
        alert_error_spike_window_minutes=_env_int(
            "ALERT_ERROR_SPIKE_WINDOW_MINUTES",
            5,
            minimum=1,
        ),
        alert_outage_min_requests=_env_int(
            "ALERT_OUTAGE_MIN_REQUESTS",
            10,
            minimum=1,
        ),
        alert_outage_window_minutes=_env_int(
            "ALERT_OUTAGE_WINDOW_MINUTES",
            5,
            minimum=1,
        ),
        alert_cooldown_minutes=_env_int("ALERT_COOLDOWN_MINUTES", 15, minimum=1),
        retention_raw_events_days=_env_int("RETENTION_RAW_EVENTS_DAYS", 14, minimum=1),
        logs_query_max_window_minutes=_env_int("LOGS_QUERY_MAX_WINDOW_MINUTES", 1440, minimum=1),
        jobs_enable_scheduler=_env_bool("JOBS_ENABLE_SCHEDULER", False),
        jobs_alert_interval_seconds=_env_float(
            "JOBS_ALERT_INTERVAL_SECONDS",
            60.0,
            minimum=1.0,
        ),
        jobs_retention_interval_seconds=_env_float(
            "JOBS_RETENTION_INTERVAL_SECONDS",
            3600.0,
            minimum=30.0,
        ),
        alert_sender_mode=getenv("ALERT_SENDER_MODE", "stub").strip().lower() or "stub",
        alert_webhook_url=getenv("ALERT_WEBHOOK_URL"),
        dev_scenarios_enabled=_env_bool("DEV_SCENARIOS_ENABLED", False),
        dev_scenarios_max_duration_seconds=_env_int(
            "DEV_SCENARIOS_MAX_DURATION_SECONDS",
            180,
            minimum=5,
        ),
        dev_scenarios_max_events=_env_int("DEV_SCENARIOS_MAX_EVENTS", 5000, minimum=1),
    )
