from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

from autopulse_backend.core.config_env import (
    env_bool as _env_bool,
)
from autopulse_backend.core.config_env import (
    env_float as _env_float,
)
from autopulse_backend.core.config_env import (
    env_int as _env_int,
)
from autopulse_backend.core.config_env import (
    env_optional_positive_int as _env_optional_positive_int,
)
from autopulse_backend.core.config_env import (
    load_runtime_dotenv_once as _load_runtime_dotenv_once,
)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    event_store: str
    event_store_duckdb_path: str
    event_store_duckdb_single_writer_profile: bool = False
    cors_allow_origins: tuple[str, ...] = ()
    event_plane_mode: str = "duckdb_single_writer"
    event_plane_shards_path: str = "./.autopulse/events-log"
    event_plane_snapshots_path: str = "./.autopulse/events-duckdb"
    event_plane_shard_max_bytes: int = 134_217_728
    event_plane_shard_max_age_seconds: int = 300
    event_plane_compactor_interval_seconds: int = 60
    event_plane_compactor_max_concurrency: int = 1
    event_plane_compactor_max_shards_per_run: int = 1024
    event_plane_compactor_publish_timeout_seconds: int = 60
    event_plane_snapshot_retention_count: int = 3
    event_plane_backpressure_min_free_bytes: int = 536_870_912
    event_plane_backpressure_min_free_percent: int = 5
    event_plane_backpressure_max_pending_shards: int = 20_000
    ingest_max_request_bytes: int = 1_048_576
    ingest_max_events_per_batch: int = 500
    ingest_rate_limit_requests_per_window: int = 1200
    ingest_rate_limit_window_seconds: int = 60
    ingest_distributed_rate_limit_enabled: bool = False
    ingest_async_aggregate_enabled: bool = True
    ingest_async_aggregate_queue_max_size: int = 2000
    ingest_aggregate_worker_max_retries: int = 3
    ingest_sql_tail_repair_enabled: bool = True
    ingest_sql_tail_repair_interval_seconds: float = 30.0
    ingest_sql_tail_repair_batch_size: int = 50
    ingest_sql_tail_repair_max_retries: int = 12
    parquet_export_enabled: bool = False
    parquet_export_root: str = "./.autopulse/parquet/events"
    parquet_export_interval_seconds: float = 300.0
    parquet_export_window_seconds: int = 900
    parquet_query_enabled: bool = False
    parquet_hot_window_hours: int = 24
    parquet_lifecycle_enabled: bool = False
    parquet_lifecycle_interval_seconds: float = 3600.0
    parquet_lifecycle_retention_days: int = 90
    parquet_lifecycle_dry_run: bool = False
    parquet_lifecycle_compaction_min_files: int = 4
    parquet_lifecycle_verify_sample_size: int = 5
    parquet_object_storage_enabled: bool = False
    parquet_object_storage_uri: str | None = None
    parquet_object_storage_prefix: str = "autopulse-parquet"
    parquet_object_storage_interval_seconds: float = 900.0
    parquet_object_storage_verify_upload: bool = True
    parquet_object_storage_endpoint_url: str | None = None
    parquet_object_storage_region: str | None = None
    parquet_object_storage_access_key_id: str | None = None
    parquet_object_storage_secret_access_key: str | None = None
    parquet_object_storage_session_token: str | None = None
    parquet_object_storage_restore_root: str = "./.autopulse/parquet/restore"
    parquet_object_storage_restore_manifest_key: str | None = None
    ingest_idempotency_ttl_hours: int = 24
    ingest_idempotency_stale_seconds: int = 45
    ingest_require_https: bool = True
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
    # Global SQLite on-disk ceiling in MB (``AUTOPULSE_SQLITE_MAX_DB_FILE_MB``;
    # deprecated alias ``AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB``); counts main + WAL + SHM.
    sqlite_max_db_file_mb: int | None = None
    # If true with SQLite + file cap, keep newest data by size
    # (oldest-first trim) and skip age pruning.
    sqlite_size_retention_only: bool = False
    logs_query_max_window_minutes: int = 1440
    jobs_enable_scheduler: bool = False
    jobs_external_cron_ownership: bool = False
    jobs_scheduler_lease_enabled: bool = True
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
    autopulse_env: str = "development"
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
    internal_metrics_bearer_token: str | None = None
    # When > 0, broadcast dashboard_update over WS on this interval for projects with
    # an open dashboard connection (ingest alone can feel sparse).
    dashboard_ws_live_tick_seconds: float = 0.0
    dashboard_allowed_email_domains: tuple[str, ...] = ()
    dashboard_oidc_enabled: bool = False
    dashboard_oidc_issuer_url: str | None = None
    dashboard_oidc_client_id: str | None = None
    dashboard_oidc_client_secret: str | None = None
    dashboard_oidc_redirect_uri: str | None = None
    dashboard_oidc_scopes: str = "openid email profile"
    dashboard_oidc_state_secret: str | None = None
    dashboard_oidc_cookie_name: str = "autopulse_oidc_state"
    dashboard_oidc_post_login_redirect: str | None = None
    dashboard_enforce_origin_for_mutations: bool = False
    database_run_migrations_on_startup: bool = True
    dashboard_read_rate_limit_requests_per_window: int = 120
    dashboard_read_rate_limit_window_seconds: int = 60
    dashboard_realtime_bus_backend: str = "none"
    dashboard_realtime_bus_channel: str = "autopulse_dashboard_realtime"
    dashboard_rum_max_request_bytes: int = 8192
    dashboard_rum_log_payloads: bool = False


def _parse_email_domains(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return ()
    domains: list[str] = []
    for part in raw.split(","):
        d = part.strip().lower().lstrip("@")
        if d and "@" not in d:
            domains.append(d)
    return tuple(domains)


def _oidc_fully_configured(settings: Settings) -> bool:
    if not settings.dashboard_oidc_enabled:
        return False
    return bool(
        (settings.dashboard_oidc_issuer_url or "").strip()
        and (settings.dashboard_oidc_client_id or "").strip()
        and (settings.dashboard_oidc_client_secret or "").strip()
        and (settings.dashboard_oidc_redirect_uri or "").strip()
        and (settings.dashboard_oidc_state_secret or "").strip()
    )


def scheduler_required_for_env(settings: Settings) -> bool:
    """Whether this deployment must run the in-process scheduler."""
    env = (settings.autopulse_env or "development").strip().lower()
    if env not in {"staging", "production"}:
        return False
    return not settings.jobs_external_cron_ownership


def validate_deployment_settings(settings: Settings) -> None:
    """Raise ``ValueError`` when production invariants are violated."""
    env = (settings.autopulse_env or "development").strip().lower()
    if scheduler_required_for_env(settings) and not settings.jobs_enable_scheduler:
        raise ValueError(
            "JOBS_ENABLE_SCHEDULER must be true when AUTOPULSE_ENV is staging/production unless "
            "JOBS_EXTERNAL_CRON_OWNERSHIP=true is explicitly set and documented"
        )
    if (
        env == "production"
        and settings.event_store == "duckdb"
        and settings.event_plane_mode == "duckdb_single_writer"
        and not settings.event_store_duckdb_single_writer_profile
    ):
        raise ValueError(
            "AUTOPULSE_DUCKDB_SINGLE_WRITER_PROFILE must be true when "
            "AUTOPULSE_ENV=production uses AUTOPULSE_EVENT_STORE=duckdb with "
            "AUTOPULSE_EVENT_PLANE_MODE=duckdb_single_writer"
        )
    if env != "production":
        return
    if settings.dashboard_auth_magic_link_dev_expose_token:
        raise ValueError(
            "DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN must be false when AUTOPULSE_ENV=production"
        )
    if settings.dev_scenarios_enabled:
        raise ValueError("DEV_SCENARIOS_ENABLED must be false when AUTOPULSE_ENV=production")
    if not settings.dashboard_auth_enabled:
        return
    if settings.dashboard_auth_allow_api_key_fallback:
        raise ValueError(
            "DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK must be false when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )
    if settings.dashboard_auth_session_ttl_minutes < 30:
        raise ValueError(
            "DASHBOARD_AUTH_SESSION_TTL_MINUTES must be >= 30 when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )
    if settings.dashboard_auth_magic_link_ttl_minutes < 5:
        raise ValueError(
            "DASHBOARD_AUTH_MAGIC_LINK_TTL_MINUTES must be >= 5 when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )
    if settings.dashboard_auth_magic_link_ttl_minutes > 30:
        raise ValueError(
            "DASHBOARD_AUTH_MAGIC_LINK_TTL_MINUTES must be <= 30 when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )
    if settings.dashboard_auth_magic_link_base_url:
        parsed_magic_link_base = urlparse(settings.dashboard_auth_magic_link_base_url.strip())
        if parsed_magic_link_base.scheme.lower() != "https":
            raise ValueError(
                "DASHBOARD_AUTH_MAGIC_LINK_BASE_URL must use https when AUTOPULSE_ENV=production "
                "and DASHBOARD_AUTH_ENABLED is true"
            )
    if settings.dashboard_oidc_enabled and settings.dashboard_oidc_redirect_uri:
        parsed_oidc_redirect = urlparse(settings.dashboard_oidc_redirect_uri.strip())
        if parsed_oidc_redirect.scheme.lower() != "https":
            raise ValueError(
                "DASHBOARD_OIDC_REDIRECT_URI must use https when AUTOPULSE_ENV=production "
                "and DASHBOARD_AUTH_ENABLED is true"
            )
    if not settings.ingest_require_https:
        raise ValueError("INGEST_REQUIRE_HTTPS must be true when AUTOPULSE_ENV=production")
    if not (settings.internal_metrics_bearer_token or "").strip():
        raise ValueError("INTERNAL_METRICS_BEARER_TOKEN must be set when AUTOPULSE_ENV=production")
    if any(origin.strip() == "*" for origin in settings.cors_allow_origins):
        raise ValueError(
            "CORS_ALLOW_ORIGINS must not include '*' when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )
    allow = (settings.dashboard_auth_allowed_email or "").strip()
    domains = settings.dashboard_allowed_email_domains
    if not allow and not domains and not _oidc_fully_configured(settings):
        raise ValueError(
            "Production dashboard auth requires DASHBOARD_AUTH_ALLOWED_EMAIL, "
            "DASHBOARD_ALLOWED_EMAIL_DOMAINS, or fully configured OIDC "
            "(DASHBOARD_OIDC_ENABLED plus issuer, client id/secret, redirect URI, state secret)"
        )
    if not settings.dashboard_enforce_origin_for_mutations:
        raise ValueError(
            "DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS must be true when AUTOPULSE_ENV=production "
            "and DASHBOARD_AUTH_ENABLED is true"
        )


def validate_event_plane_settings(settings: Settings) -> None:
    """Raise ``ValueError`` when event-plane config combinations are invalid."""
    if settings.event_plane_mode not in {"duckdb_single_writer", "duckdb_log_shards"}:
        raise ValueError(
            "AUTOPULSE_EVENT_PLANE_MODE must be one of: duckdb_single_writer, duckdb_log_shards"
        )
    if settings.event_plane_mode == "duckdb_log_shards" and settings.event_store != "duckdb":
        raise ValueError(
            "AUTOPULSE_EVENT_PLANE_MODE=duckdb_log_shards requires AUTOPULSE_EVENT_STORE=duckdb"
        )


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
    # Anchor relative SQLite paths to the same data root as DuckDB (AUTOPULSE_DATA_DIR / …).
    data_root = resolve_autopulse_data_root()
    if (
        raw_path.startswith("/./")
        or raw_path.startswith("/../")
        or raw_path.startswith("/")
        and not parsed.netloc
    ):
        resolved = (data_root / raw_path[1:]).resolve()
    elif raw_path.startswith("/") and parsed.netloc:
        resolved = Path(raw_path).resolve()
    else:
        resolved = (data_root / raw_path).resolve()
    # Workspace default filenames used to live at the data root; keep them under
    # ``.autopulse/`` with DuckDB and the email outbox.
    _legacy_root_sqlite = frozenset({"autopulse.db", "autopulse_embedded.db"})
    data_root_resolved = data_root.resolve()
    if resolved.name in _legacy_root_sqlite and resolved.parent.resolve() == data_root_resolved:
        resolved = (data_root_resolved / ".autopulse" / resolved.name).resolve()
    normalized_path = str(resolved).replace("\\", "/")
    out = f"{parsed.scheme}:///{normalized_path}"
    # SQLite does not create parents; nested defaults live under `.autopulse/` like DuckDB.
    with suppress(OSError):
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return out


def redact_database_url_for_log(database_url: str) -> str:
    """Return a log-safe ``DATABASE_URL`` with user password redacted.

    URLs without a password (typical SQLite file paths) are returned unchanged.
    """
    normalized = database_url.strip()
    parsed = urlparse(normalized)
    if not parsed.password:
        return normalized
    user = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{quote(user, safe='')}:***" if user else "***"
    netloc = f"{auth}@{host}{port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def resolve_autopulse_data_root() -> Path:
    """Directory used to anchor relative ``AUTOPULSE_DUCKDB_PATH`` values.

    Precedence:

    1. ``AUTOPULSE_DATA_DIR`` (preferred)
    2. ``AUTOPULSE_PROJECT_ROOT`` (alias for the same semantics)
    3. Monorepo checkout: parent of ``backend/`` when ``backend/pyproject.toml`` exists
       (same layout as ``normalize_database_url`` SQLite anchoring)
    4. Current working directory (installed wheel / non-checkout layouts)
    """
    for key in ("AUTOPULSE_DATA_DIR", "AUTOPULSE_PROJECT_ROOT"):
        raw = getenv(key, "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    backend_dir = Path(__file__).resolve().parents[3]
    if (backend_dir / "pyproject.toml").is_file():
        return backend_dir.parent.resolve()
    return Path.cwd().resolve()


def normalize_event_store_duckdb_path(raw: str, *, data_root: Path | None = None) -> str:
    """Resolve ``AUTOPULSE_DUCKDB_PATH`` to an absolute path independent of process cwd.

    Relative paths are joined under ``data_root`` (default: :func:`resolve_autopulse_data_root`).
    Absolute paths are expanded and resolved as-is.

    Raises:
        ValueError: if a relative path escapes ``data_root`` after resolution.
    """
    text = (raw or "").strip() or "./.autopulse/events.duckdb"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"AUTOPULSE_DUCKDB_PATH={raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def normalize_event_plane_shards_path(raw: str, *, data_root: Path | None = None) -> str:
    """Resolve ``AUTOPULSE_EVENT_PLANE_SHARDS_PATH`` to an absolute path."""
    text = (raw or "").strip() or "./.autopulse/events-log"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "AUTOPULSE_EVENT_PLANE_SHARDS_PATH="
            f"{raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def normalize_event_plane_snapshots_path(raw: str, *, data_root: Path | None = None) -> str:
    """Resolve ``AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH`` to an absolute path."""
    text = (raw or "").strip() or "./.autopulse/events-duckdb"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH="
            f"{raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def normalize_alert_email_file_outbox_dir(raw: str | None, *, data_root: Path | None = None) -> str:
    """Resolve ``ALERT_EMAIL_FILE_OUTBOX_DIR`` to an absolute path.

    Relative values are anchored under ``data_root`` (default: :func:`resolve_autopulse_data_root`)
    so magic-link and alert ``file`` delivery lands beside other workspace data regardless of
    process ``cwd`` when starting uvicorn (monorepo uses repo ``.autopulse/emails``).
    """
    text = (raw or "").strip() or "./.autopulse/emails"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"ALERT_EMAIL_FILE_OUTBOX_DIR={raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def normalize_parquet_export_root(raw: str | None, *, data_root: Path | None = None) -> str:
    """Resolve ``AUTOPULSE_PARQUET_EXPORT_ROOT`` to an absolute path."""
    text = (raw or "").strip() or "./.autopulse/parquet/events"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"AUTOPULSE_PARQUET_EXPORT_ROOT={raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def normalize_parquet_restore_root(raw: str | None, *, data_root: Path | None = None) -> str:
    """Resolve ``AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_ROOT`` to absolute path."""
    text = (raw or "").strip() or "./.autopulse/parquet/restore"
    root = (data_root or resolve_autopulse_data_root()).resolve()
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return str(candidate.resolve())
    anchored = (root / text).resolve()
    try:
        anchored.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_ROOT="
            f"{raw!r} resolves outside data root {root}: {anchored}"
        ) from exc
    return str(anchored)


def _sqlite_resolved_file_path(normalized_sqlite_url: str) -> Path | None:
    """Filesystem path for a file-backed SQLite URL already normalized, or None."""
    if not normalized_sqlite_url.startswith("sqlite"):
        return None
    parsed = urlparse(normalized_sqlite_url)
    raw_path = unquote(parsed.path or "")
    if normalized_sqlite_url.endswith(":memory:") or raw_path == ":memory:" or not raw_path:
        return None
    data_root = resolve_autopulse_data_root()
    # Keep rules aligned with ``maintenance.retention._resolve_sqlite_db_path``.
    if raw_path.startswith("//"):
        return Path(raw_path[1:]).resolve()
    if raw_path.startswith("/./") or raw_path.startswith("/../"):
        return (data_root / raw_path[1:]).resolve()
    if raw_path.startswith("/") and parsed.netloc:
        return Path(raw_path).resolve()
    if raw_path.startswith("/") and not parsed.netloc:
        return Path(raw_path).resolve()
    return (data_root / raw_path).resolve()


def _is_workspace_default_dev_sqlite_file(normalized_database_url: str) -> bool:
    """True for known workspace-local SQLite files used as local dev defaults.

    When ``JOBS_ENABLE_SCHEDULER`` is unset, ``get_settings()`` enables the full scheduler
    for these files. If it is set to ``false``, the API uses a retention-only loop instead
    (see ``lifespan``) so time-based cleanup still runs without the alert ticker.
    """
    path = _sqlite_resolved_file_path(normalized_database_url)
    return path is not None and path.name in {"autopulse.db", "autopulse_embedded.db"}


def get_settings() -> Settings:
    _load_runtime_dotenv_once()
    raw_cors_origins = getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:8000,http://127.0.0.1:8000",
    )
    cors_allow_origins = tuple(
        origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()
    )
    database_url = normalize_database_url(
        getenv("DATABASE_URL", "sqlite+aiosqlite:///./.autopulse/autopulse.db")
    )
    sqlite_cap_raw = getenv("AUTOPULSE_SQLITE_MAX_DB_FILE_MB")
    if sqlite_cap_raw is None or sqlite_cap_raw.strip() == "":
        sqlite_cap_raw = getenv("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB")
    sqlite_max_db_file_mb = _env_optional_positive_int("AUTOPULSE_SQLITE_MAX_DB_FILE_MB")
    if sqlite_max_db_file_mb is None:
        sqlite_max_db_file_mb = _env_optional_positive_int("AUTOPULSE_EMBEDDED_MAX_DB_SIZE_MB")
    if (
        sqlite_max_db_file_mb is None
        and _is_workspace_default_dev_sqlite_file(database_url)
        and (sqlite_cap_raw is None or sqlite_cap_raw.strip() == "")
    ):
        sqlite_max_db_file_mb = 512
    jobs_scheduler_raw = getenv("JOBS_ENABLE_SCHEDULER")
    jobs_enable_scheduler = _env_bool("JOBS_ENABLE_SCHEDULER", False)
    if (
        jobs_scheduler_raw is None or jobs_scheduler_raw.strip() == ""
    ) and _is_workspace_default_dev_sqlite_file(database_url):
        jobs_enable_scheduler = True
    jobs_retention_interval_seconds = _env_float(
        "JOBS_RETENTION_INTERVAL_SECONDS",
        3600.0,
        minimum=5.0,
    )
    env_retention = getenv("JOBS_RETENTION_INTERVAL_SECONDS")
    if _is_workspace_default_dev_sqlite_file(database_url) and (
        env_retention is None or env_retention.strip() == ""
    ):
        jobs_retention_interval_seconds = min(float(jobs_retention_interval_seconds), 300.0)
    poll_raw = getenv("AUTOPULSE_RETENTION_PRESSURE_POLL_SECONDS")
    if poll_raw is None or poll_raw.strip() == "":
        retention_pressure_poll_seconds = (
            1.0 if _is_workspace_default_dev_sqlite_file(database_url) else 0.0
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
    _data_root = resolve_autopulse_data_root()
    event_store_duckdb_path = normalize_event_store_duckdb_path(
        getenv("AUTOPULSE_DUCKDB_PATH", "./.autopulse/events.duckdb").strip()
        or "./.autopulse/events.duckdb",
        data_root=_data_root,
    )
    event_plane_mode = (
        getenv("AUTOPULSE_EVENT_PLANE_MODE", "duckdb_single_writer").strip().lower()
        or "duckdb_single_writer"
    )
    event_plane_shards_path = normalize_event_plane_shards_path(
        getenv("AUTOPULSE_EVENT_PLANE_SHARDS_PATH", "./.autopulse/events-log").strip()
        or "./.autopulse/events-log",
        data_root=_data_root,
    )
    event_plane_snapshots_path = normalize_event_plane_snapshots_path(
        getenv("AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH", "./.autopulse/events-duckdb").strip()
        or "./.autopulse/events-duckdb",
        data_root=_data_root,
    )
    dashboard_allowed_email_domains = _parse_email_domains(
        getenv("DASHBOARD_ALLOWED_EMAIL_DOMAINS")
    )
    dashboard_oidc_enabled = _env_bool("DASHBOARD_OIDC_ENABLED", False)
    dashboard_oidc_issuer_url = getenv("DASHBOARD_OIDC_ISSUER_URL", "").strip() or None
    dashboard_oidc_client_id = getenv("DASHBOARD_OIDC_CLIENT_ID", "").strip() or None
    dashboard_oidc_client_secret = getenv("DASHBOARD_OIDC_CLIENT_SECRET", "").strip() or None
    dashboard_oidc_redirect_uri = getenv("DASHBOARD_OIDC_REDIRECT_URI", "").strip() or None
    dashboard_oidc_scopes = (
        getenv("DASHBOARD_OIDC_SCOPES", "openid email profile").strip() or "openid email profile"
    )
    dashboard_oidc_state_secret = getenv("DASHBOARD_OIDC_STATE_SECRET", "").strip() or None
    dashboard_oidc_cookie_name = (
        getenv("DASHBOARD_OIDC_COOKIE_NAME", "autopulse_oidc_state").strip()
        or "autopulse_oidc_state"
    )
    dashboard_oidc_post_login_redirect = (
        getenv("DASHBOARD_OIDC_POST_LOGIN_REDIRECT", "").strip() or None
    )
    dashboard_realtime_bus_backend = (
        getenv("DASHBOARD_REALTIME_BUS_BACKEND", "none").strip().lower() or "none"
    )
    if dashboard_realtime_bus_backend not in {"none", "postgres_notify"}:
        dashboard_realtime_bus_backend = "none"
    dashboard_realtime_bus_channel = (
        getenv("DASHBOARD_REALTIME_BUS_CHANNEL", "autopulse_dashboard_realtime").strip()
        or "autopulse_dashboard_realtime"
    )
    autopulse_env = getenv("AUTOPULSE_ENV", "development").strip().lower() or "development"
    settings = Settings(
        database_url=database_url,
        event_store=event_store,
        event_plane_mode=event_plane_mode,
        event_store_duckdb_path=event_store_duckdb_path,
        event_store_duckdb_single_writer_profile=_env_bool(
            "AUTOPULSE_DUCKDB_SINGLE_WRITER_PROFILE",
            False,
        ),
        event_plane_shards_path=event_plane_shards_path,
        event_plane_snapshots_path=event_plane_snapshots_path,
        event_plane_shard_max_bytes=_env_int(
            "AUTOPULSE_SHARD_MAX_BYTES",
            134_217_728,
            minimum=1_048_576,
        ),
        event_plane_shard_max_age_seconds=_env_int(
            "AUTOPULSE_SHARD_MAX_AGE_SECONDS",
            300,
            minimum=10,
        ),
        event_plane_compactor_interval_seconds=_env_int(
            "AUTOPULSE_COMPACTOR_INTERVAL_SECONDS",
            60,
            minimum=1,
        ),
        event_plane_compactor_max_concurrency=_env_int(
            "AUTOPULSE_COMPACTOR_MAX_CONCURRENCY",
            1,
            minimum=1,
        ),
        event_plane_compactor_max_shards_per_run=_env_int(
            "AUTOPULSE_COMPACTOR_MAX_SHARDS_PER_RUN",
            1024,
            minimum=1,
        ),
        event_plane_compactor_publish_timeout_seconds=_env_int(
            "AUTOPULSE_COMPACTOR_PUBLISH_TIMEOUT_SECONDS",
            60,
            minimum=1,
        ),
        event_plane_snapshot_retention_count=_env_int(
            "AUTOPULSE_SNAPSHOT_RETENTION_COUNT",
            3,
            minimum=1,
        ),
        event_plane_backpressure_min_free_bytes=_env_int(
            "AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_BYTES",
            536_870_912,
            minimum=1,
        ),
        event_plane_backpressure_min_free_percent=_env_int(
            "AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MIN_FREE_PERCENT",
            5,
            minimum=0,
        ),
        event_plane_backpressure_max_pending_shards=_env_int(
            "AUTOPULSE_EVENT_PLANE_BACKPRESSURE_MAX_PENDING_SHARDS",
            20_000,
            minimum=1,
        ),
        cors_allow_origins=cors_allow_origins,
        ingest_max_request_bytes=_env_int("INGEST_MAX_REQUEST_BYTES", 1_048_576, minimum=1),
        ingest_max_events_per_batch=_env_int(
            "INGEST_MAX_EVENTS_PER_BATCH",
            500,
            minimum=1,
        ),
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
        ingest_aggregate_worker_max_retries=_env_int(
            "INGEST_AGGREGATE_WORKER_MAX_RETRIES",
            3,
            minimum=0,
        ),
        ingest_sql_tail_repair_enabled=_env_bool(
            "INGEST_SQL_TAIL_REPAIR_ENABLED",
            True,
        ),
        ingest_sql_tail_repair_interval_seconds=_env_float(
            "INGEST_SQL_TAIL_REPAIR_INTERVAL_SECONDS",
            30.0,
            minimum=1.0,
        ),
        ingest_sql_tail_repair_batch_size=_env_int(
            "INGEST_SQL_TAIL_REPAIR_BATCH_SIZE",
            50,
            minimum=1,
        ),
        ingest_sql_tail_repair_max_retries=_env_int(
            "INGEST_SQL_TAIL_REPAIR_MAX_RETRIES",
            12,
            minimum=1,
        ),
        parquet_export_enabled=_env_bool("AUTOPULSE_PARQUET_EXPORT_ENABLED", False),
        parquet_export_root=normalize_parquet_export_root(
            getenv("AUTOPULSE_PARQUET_EXPORT_ROOT", "").strip() or None,
            data_root=_data_root,
        ),
        parquet_export_interval_seconds=_env_float(
            "AUTOPULSE_PARQUET_EXPORT_INTERVAL_SECONDS",
            300.0,
            minimum=5.0,
        ),
        parquet_export_window_seconds=_env_int(
            "AUTOPULSE_PARQUET_EXPORT_WINDOW_SECONDS",
            900,
            minimum=60,
        ),
        parquet_query_enabled=_env_bool("AUTOPULSE_PARQUET_QUERY_ENABLED", False),
        parquet_hot_window_hours=_env_int(
            "AUTOPULSE_PARQUET_HOT_WINDOW_HOURS",
            24,
            minimum=1,
        ),
        parquet_lifecycle_enabled=_env_bool("AUTOPULSE_PARQUET_LIFECYCLE_ENABLED", False),
        parquet_lifecycle_interval_seconds=_env_float(
            "AUTOPULSE_PARQUET_LIFECYCLE_INTERVAL_SECONDS",
            3600.0,
            minimum=5.0,
        ),
        parquet_lifecycle_retention_days=_env_int(
            "AUTOPULSE_PARQUET_LIFECYCLE_RETENTION_DAYS",
            90,
            minimum=1,
        ),
        parquet_lifecycle_dry_run=_env_bool("AUTOPULSE_PARQUET_LIFECYCLE_DRY_RUN", False),
        parquet_lifecycle_compaction_min_files=_env_int(
            "AUTOPULSE_PARQUET_LIFECYCLE_COMPACTION_MIN_FILES",
            4,
            minimum=2,
        ),
        parquet_lifecycle_verify_sample_size=_env_int(
            "AUTOPULSE_PARQUET_LIFECYCLE_VERIFY_SAMPLE_SIZE",
            5,
            minimum=1,
        ),
        parquet_object_storage_enabled=_env_bool(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_ENABLED",
            False,
        ),
        parquet_object_storage_uri=getenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_URI", "").strip()
        or None,
        parquet_object_storage_prefix=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_PREFIX",
            "autopulse-parquet",
        ).strip()
        or "autopulse-parquet",
        parquet_object_storage_interval_seconds=_env_float(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_INTERVAL_SECONDS",
            900.0,
            minimum=5.0,
        ),
        parquet_object_storage_verify_upload=_env_bool(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_VERIFY_UPLOAD",
            True,
        ),
        parquet_object_storage_endpoint_url=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_ENDPOINT_URL",
            "",
        ).strip()
        or None,
        parquet_object_storage_region=getenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_REGION", "").strip()
        or None,
        parquet_object_storage_access_key_id=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_ACCESS_KEY_ID",
            "",
        ).strip()
        or None,
        parquet_object_storage_secret_access_key=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_SECRET_ACCESS_KEY",
            "",
        ).strip()
        or None,
        parquet_object_storage_session_token=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_SESSION_TOKEN",
            "",
        ).strip()
        or None,
        parquet_object_storage_restore_root=normalize_parquet_restore_root(
            getenv("AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_ROOT", "").strip() or None,
            data_root=_data_root,
        ),
        parquet_object_storage_restore_manifest_key=getenv(
            "AUTOPULSE_PARQUET_OBJECT_STORAGE_RESTORE_MANIFEST_KEY",
            "",
        ).strip()
        or None,
        ingest_idempotency_ttl_hours=_env_int("INGEST_IDEMPOTENCY_TTL_HOURS", 24, minimum=1),
        ingest_idempotency_stale_seconds=_env_int(
            "INGEST_IDEMPOTENCY_STALE_SECONDS", 45, minimum=5
        ),
        ingest_require_https=_env_bool("INGEST_REQUIRE_HTTPS", True),
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
        sqlite_max_db_file_mb=sqlite_max_db_file_mb,
        sqlite_size_retention_only=_env_bool(
            "AUTOPULSE_SQLITE_SIZE_RETENTION_ONLY",
            bool(database_url.startswith("sqlite") and sqlite_max_db_file_mb is not None),
        ),
        logs_query_max_window_minutes=_env_int("LOGS_QUERY_MAX_WINDOW_MINUTES", 1440, minimum=1),
        jobs_enable_scheduler=jobs_enable_scheduler,
        jobs_external_cron_ownership=_env_bool("JOBS_EXTERNAL_CRON_OWNERSHIP", False),
        jobs_scheduler_lease_enabled=_env_bool("JOBS_SCHEDULER_LEASE_ENABLED", True),
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
        alert_email_file_outbox_dir=normalize_alert_email_file_outbox_dir(
            getenv("ALERT_EMAIL_FILE_OUTBOX_DIR", "").strip() or None
        ),
        alert_email_smtp_host=getenv("ALERT_EMAIL_SMTP_HOST"),
        alert_email_smtp_port=_env_int("ALERT_EMAIL_SMTP_PORT", 25, minimum=1),
        alert_email_smtp_use_tls=_env_bool("ALERT_EMAIL_SMTP_USE_TLS", False),
        alert_email_smtp_username=getenv("ALERT_EMAIL_SMTP_USERNAME"),
        alert_email_smtp_password=getenv("ALERT_EMAIL_SMTP_PASSWORD"),
        alert_slack_webhook_url=getenv("ALERT_SLACK_WEBHOOK_URL"),
        alert_discord_webhook_url=getenv("ALERT_DISCORD_WEBHOOK_URL"),
        autopulse_env=autopulse_env,
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
        internal_metrics_bearer_token=(getenv("INTERNAL_METRICS_BEARER_TOKEN", "").strip() or None),
        dashboard_ws_live_tick_seconds=_env_float(
            "AUTOPULSE_DASHBOARD_WS_LIVE_TICK_SECONDS",
            4.0,
            minimum=0.0,
        ),
        dashboard_allowed_email_domains=dashboard_allowed_email_domains,
        dashboard_oidc_enabled=dashboard_oidc_enabled,
        dashboard_oidc_issuer_url=dashboard_oidc_issuer_url,
        dashboard_oidc_client_id=dashboard_oidc_client_id,
        dashboard_oidc_client_secret=dashboard_oidc_client_secret,
        dashboard_oidc_redirect_uri=dashboard_oidc_redirect_uri,
        dashboard_oidc_scopes=dashboard_oidc_scopes,
        dashboard_oidc_state_secret=dashboard_oidc_state_secret,
        dashboard_oidc_cookie_name=dashboard_oidc_cookie_name,
        dashboard_oidc_post_login_redirect=dashboard_oidc_post_login_redirect,
        dashboard_enforce_origin_for_mutations=_env_bool(
            "DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS", False
        ),
        database_run_migrations_on_startup=_env_bool("DATABASE_RUN_MIGRATIONS_ON_STARTUP", True),
        dashboard_read_rate_limit_requests_per_window=_env_int(
            "DASHBOARD_READ_RATE_LIMIT_REQUESTS_PER_WINDOW",
            120,
            minimum=0,
        ),
        dashboard_read_rate_limit_window_seconds=_env_int(
            "DASHBOARD_READ_RATE_LIMIT_WINDOW_SECONDS",
            60,
            minimum=1,
        ),
        dashboard_realtime_bus_backend=dashboard_realtime_bus_backend,
        dashboard_realtime_bus_channel=dashboard_realtime_bus_channel,
        dashboard_rum_max_request_bytes=_env_int(
            "DASHBOARD_RUM_MAX_REQUEST_BYTES",
            8192,
            minimum=256,
        ),
        dashboard_rum_log_payloads=_env_bool("DASHBOARD_RUM_LOG_PAYLOADS", False),
    )
    validate_event_plane_settings(settings)
    validate_deployment_settings(settings)
    return settings
