from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path
from urllib.parse import unquote, urlparse


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


def _env_optional_positive_int(name: str) -> int | None:
    """Parse a positive int from the environment, or None if unset / invalid / <= 0."""
    raw = getenv(name)
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    if value <= 0:
        return None
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
    event_store: str
    event_store_duckdb_path: str
    cors_allow_origins: tuple[str, ...]
    ingest_max_request_bytes: int = 1_048_576
    ingest_rate_limit_requests_per_window: int = 1200
    ingest_rate_limit_window_seconds: int = 60
    ingest_distributed_rate_limit_enabled: bool = False
    ingest_async_aggregate_enabled: bool = True
    ingest_async_aggregate_queue_max_size: int = 2000
    ingest_require_https: bool = False
    ingest_trust_forwarded_proto: bool = True
    ingest_drop_autopulse_traffic_from_db: bool = True
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
    # Global SQLite on-disk ceiling in MB
    # (``AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB``); counts main + WAL + SHM.
    embedded_sqlite_max_db_file_mb: int | None = None
    # If true with SQLite + file cap, keep newest data by size
    # (oldest-first trim) and skip age pruning.
    sqlite_size_retention_only: bool = False
    logs_query_max_window_minutes: int = 1440
    jobs_enable_scheduler: bool = False
    jobs_scheduler_lease_enabled: bool = False
    jobs_scheduler_lease_ttl_seconds: int = 120
    jobs_alert_interval_seconds: float = 60.0
    jobs_retention_interval_seconds: float = 3600.0
    # SQLite: poll file size / row caps; when over limit, run retention (see jobs pressure loop).
    retention_pressure_poll_seconds: float = 0.0
    retention_pressure_min_interval_seconds: float = 15.0
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
    dashboard_auth_allow_api_key_fallback: bool = False
    dashboard_auth_magic_link_base_url: str | None = None


def normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return normalized
    raw_path = unquote(parsed.path or "")
    if normalized.endswith(":memory:") or raw_path == ":memory:":
        return normalized
    if not raw_path:
        return normalized
    # Keep a single project-root DB path regardless of caller cwd.
    project_root = Path(__file__).resolve().parents[4]
    if (
        raw_path.startswith("/./")
        or raw_path.startswith("/../")
        or raw_path.startswith("/")
        and not parsed.netloc
    ):
        resolved = (project_root / raw_path[1:]).resolve()
    elif raw_path.startswith("/") and parsed.netloc:
        resolved = Path(raw_path).resolve()
    else:
        resolved = (project_root / raw_path).resolve()
    normalized_path = str(resolved).replace("\\", "/")
    return f"{parsed.scheme}:///{normalized_path}"


def _sqlite_resolved_file_path(normalized_sqlite_url: str) -> Path | None:
    """Filesystem path for a file-backed SQLite URL already normalized, or None."""
    if not normalized_sqlite_url.startswith("sqlite"):
        return None
    parsed = urlparse(normalized_sqlite_url)
    raw_path = unquote(parsed.path or "")
    if normalized_sqlite_url.endswith(":memory:") or raw_path == ":memory:" or not raw_path:
        return None
    project_root = Path(__file__).resolve().parents[4]
    # Keep rules aligned with ``maintenance.retention._resolve_sqlite_db_path``.
    if raw_path.startswith("//"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/./") or raw_path.startswith("/../"):
        return (project_root / raw_path[1:]).resolve()
    if raw_path.startswith("/") and parsed.netloc:
        return Path(raw_path).resolve()
    if raw_path.startswith("/") and not parsed.netloc:
        return Path(raw_path).resolve()
    return (project_root / raw_path).resolve()


def _is_autopulse_embedded_default_sqlite_file(normalized_database_url: str) -> bool:
    """True for known workspace-local SQLite files that ship as dev/embedded defaults.

    When ``JOBS_ENABLE_SCHEDULER`` is unset, ``get_settings()`` enables the full scheduler
    for these files. If it is set to ``false``, the API uses a retention-only loop instead
    (see ``lifespan``) so time-based cleanup still runs without the alert ticker.
    """
    path = _sqlite_resolved_file_path(normalized_database_url)
    return path is not None and path.name in {"autopulse.db", "autopulse_embedded.db"}


def get_settings() -> Settings:
    raw_cors_origins = getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    cors_allow_origins = tuple(
        origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()
    )
    database_url = normalize_database_url(
        getenv("DATABASE_URL", "sqlite+aiosqlite:///./autopulse.db")
    )
    embedded_cap_raw = getenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB")
    embedded_sqlite_max_db_file_mb = _env_optional_positive_int("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB")
    if (
        embedded_sqlite_max_db_file_mb is None
        and _is_autopulse_embedded_default_sqlite_file(database_url)
        and (embedded_cap_raw is None or embedded_cap_raw.strip() == "")
    ):
        embedded_sqlite_max_db_file_mb = 512
    jobs_scheduler_raw = getenv("JOBS_ENABLE_SCHEDULER")
    jobs_enable_scheduler = _env_bool("JOBS_ENABLE_SCHEDULER", False)
    if (
        jobs_scheduler_raw is None or jobs_scheduler_raw.strip() == ""
    ) and _is_autopulse_embedded_default_sqlite_file(database_url):
        jobs_enable_scheduler = True
    jobs_retention_interval_seconds = _env_float(
        "JOBS_RETENTION_INTERVAL_SECONDS",
        3600.0,
        minimum=5.0,
    )
    env_retention = getenv("JOBS_RETENTION_INTERVAL_SECONDS")
    if _is_autopulse_embedded_default_sqlite_file(database_url) and (
        env_retention is None or env_retention.strip() == ""
    ):
        jobs_retention_interval_seconds = min(float(jobs_retention_interval_seconds), 300.0)
    poll_raw = getenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS")
    if poll_raw is None or poll_raw.strip() == "":
        retention_pressure_poll_seconds = (
            1.0 if _is_autopulse_embedded_default_sqlite_file(database_url) else 0.0
        )
    else:
        retention_pressure_poll_seconds = _env_float(
            "AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS",
            0.0,
            minimum=0.0,
        )
    retention_pressure_min_interval_seconds = _env_float(
        "AUTOPULSE_RETENTION_PRESSURE_MIN_INTERVAL_SECONDS",
        15.0,
        minimum=5.0,
    )
    event_store = getenv("AUTOPULSE_EVENT_STORE", "duckdb").strip().lower() or "duckdb"
    if event_store not in {"duckdb", "sqlite"}:
        event_store = "duckdb"
    event_store_duckdb_path = (
        getenv("AUTOPULSE_DUCKDB_PATH", "./.autopulse/events.duckdb").strip()
        or "./.autopulse/events.duckdb"
    )
    return Settings(
        database_url=database_url,
        event_store=event_store,
        event_store_duckdb_path=event_store_duckdb_path,
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
        ingest_drop_autopulse_traffic_from_db=_env_bool(
            "INGEST_DROP_AUTOPULSE_TRAFFIC_FROM_DB",
            True,
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
        embedded_sqlite_max_db_file_mb=embedded_sqlite_max_db_file_mb,
        sqlite_size_retention_only=_env_bool(
            "AUTOPULSE_SQLITE_SIZE_RETENTION_ONLY",
            bool(database_url.startswith("sqlite") and embedded_sqlite_max_db_file_mb is not None),
        ),
        logs_query_max_window_minutes=_env_int("LOGS_QUERY_MAX_WINDOW_MINUTES", 1440, minimum=1),
        jobs_enable_scheduler=jobs_enable_scheduler,
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
        jobs_retention_interval_seconds=jobs_retention_interval_seconds,
        retention_pressure_poll_seconds=retention_pressure_poll_seconds,
        retention_pressure_min_interval_seconds=retention_pressure_min_interval_seconds,
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
        dashboard_auth_allow_api_key_fallback=_env_bool(
            "DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK",
            False,
        ),
        dashboard_auth_magic_link_base_url=(
            getenv("DASHBOARD_AUTH_MAGIC_LINK_BASE_URL", "").strip() or None
        ),
    )
