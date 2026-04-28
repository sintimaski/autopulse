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
    ingest_distributed_rate_limit_enabled: bool = False
    ingest_async_aggregate_enabled: bool = True
    ingest_async_aggregate_queue_max_size: int = 2000
    ingest_require_https: bool = False
    ingest_trust_forwarded_proto: bool = True
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
    jobs_scheduler_lease_enabled: bool = False
    jobs_scheduler_lease_ttl_seconds: int = 120
    jobs_alert_interval_seconds: float = 60.0
    jobs_retention_interval_seconds: float = 3600.0
    alert_sender_mode: str = "stub"
    alert_webhook_url: str | None = None
    alert_email_provider: str = "resend"
    alert_email_api_key: str | None = None
    alert_email_from: str | None = None
    alert_email_file_outbox_dir: str = "./.autopulse/emails"
    alert_email_smtp_host: str | None = None
    alert_email_smtp_port: int = 25
    alert_email_smtp_use_tls: bool = False
    alert_email_smtp_username: str | None = None
    alert_email_smtp_password: str | None = None
    alert_slack_webhook_url: str | None = None
    alert_discord_webhook_url: str | None = None
    dev_scenarios_enabled: bool = False
    dev_scenarios_max_duration_seconds: int = 180
    dev_scenarios_max_events: int = 5000
    dashboard_auth_enabled: bool = True
    dashboard_auth_allowed_email: str | None = None
    dashboard_auth_session_cookie_name: str = "autopulse_dashboard_session"
    dashboard_auth_session_ttl_minutes: int = 720
    dashboard_auth_magic_link_ttl_minutes: int = 15
    dashboard_auth_magic_link_dev_expose_token: bool = False
    dashboard_auth_allow_api_key_fallback: bool = False
    dashboard_auth_magic_link_base_url: str | None = None


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
        ingest_distributed_rate_limit_enabled=_env_bool(
            "INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED",
            False,
        ),
        ingest_async_aggregate_enabled=_env_bool(
            "INGEST_ASYNC_AGGREGATE_ENABLED",
            True,
        ),
        ingest_async_aggregate_queue_max_size=_env_int(
            "INGEST_ASYNC_AGGREGATE_QUEUE_MAX_SIZE",
            2000,
            minimum=1,
        ),
        ingest_require_https=_env_bool("INGEST_REQUIRE_HTTPS", False),
        ingest_trust_forwarded_proto=_env_bool("INGEST_TRUST_FORWARDED_PROTO", True),
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
        jobs_scheduler_lease_enabled=_env_bool("JOBS_SCHEDULER_LEASE_ENABLED", False),
        jobs_scheduler_lease_ttl_seconds=_env_int(
            "JOBS_SCHEDULER_LEASE_TTL_SECONDS",
            120,
            minimum=5,
        ),
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
        alert_email_provider=getenv("ALERT_EMAIL_PROVIDER", "resend").strip().lower() or "resend",
        alert_email_api_key=getenv("ALERT_EMAIL_API_KEY"),
        alert_email_from=getenv("ALERT_EMAIL_FROM"),
        alert_email_file_outbox_dir=(
            getenv("ALERT_EMAIL_FILE_OUTBOX_DIR", "./.autopulse/emails").strip()
            or "./.autopulse/emails"
        ),
        alert_email_smtp_host=getenv("ALERT_EMAIL_SMTP_HOST"),
        alert_email_smtp_port=_env_int("ALERT_EMAIL_SMTP_PORT", 25, minimum=1),
        alert_email_smtp_use_tls=_env_bool("ALERT_EMAIL_SMTP_USE_TLS", False),
        alert_email_smtp_username=getenv("ALERT_EMAIL_SMTP_USERNAME"),
        alert_email_smtp_password=getenv("ALERT_EMAIL_SMTP_PASSWORD"),
        alert_slack_webhook_url=getenv("ALERT_SLACK_WEBHOOK_URL"),
        alert_discord_webhook_url=getenv("ALERT_DISCORD_WEBHOOK_URL"),
        dev_scenarios_enabled=_env_bool("DEV_SCENARIOS_ENABLED", False),
        dev_scenarios_max_duration_seconds=_env_int(
            "DEV_SCENARIOS_MAX_DURATION_SECONDS",
            180,
            minimum=5,
        ),
        dev_scenarios_max_events=_env_int("DEV_SCENARIOS_MAX_EVENTS", 5000, minimum=1),
        dashboard_auth_enabled=_env_bool("DASHBOARD_AUTH_ENABLED", True),
        dashboard_auth_allowed_email=getenv("DASHBOARD_AUTH_ALLOWED_EMAIL"),
        dashboard_auth_session_cookie_name=(
            getenv("DASHBOARD_AUTH_SESSION_COOKIE_NAME", "autopulse_dashboard_session").strip()
            or "autopulse_dashboard_session"
        ),
        dashboard_auth_session_ttl_minutes=_env_int(
            "DASHBOARD_AUTH_SESSION_TTL_MINUTES",
            720,
            minimum=5,
        ),
        dashboard_auth_magic_link_ttl_minutes=_env_int(
            "DASHBOARD_AUTH_MAGIC_LINK_TTL_MINUTES",
            15,
            minimum=1,
        ),
        dashboard_auth_magic_link_dev_expose_token=_env_bool(
            "DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN",
            False,
        ),
        dashboard_auth_allow_api_key_fallback=_env_bool(
            "DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK",
            False,
        ),
        dashboard_auth_magic_link_base_url=(
            getenv("DASHBOARD_AUTH_MAGIC_LINK_BASE_URL", "").strip() or None
        ),
    )
