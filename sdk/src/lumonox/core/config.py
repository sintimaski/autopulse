"""Framework-agnostic ingest configuration.

``_MonitorConfig`` is the central config dataclass used by the dispatcher and
by every framework adapter. It carries enough information to (a) decide
whether the SDK is allowed to send, (b) shape every captured event, and
(c) bound the runtime cost of the send path (queue size, batch budget,
concurrent-send cap, circuit breaker, etc.). The constructor is build-once
at ``monitor()`` time; adapters do not mutate it after construction.

``build_monitor_config(**kwargs)`` resolves the standard mix of explicit
kwargs + ``LUMONOX_*`` environment variables + defaults. Every framework
adapter calls this so the behavioral contract (which env vars are honored,
which keys get scrubbed by default, what the queue/batch/circuit defaults
are) lives in one place.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lumonox.core.env import (
    _env_bool,
    _env_float,
    _env_int,
    _optional_metadata_str,
)
from lumonox.core.paths import _normalize_mount_prefix, _resolve_ignore_path_prefixes
from lumonox.core.sampling import _clamp_sample_rate
from lumonox.core.scrubbing import DEFAULT_SCRUB_KEYS

if TYPE_CHECKING:
    from lumonox.core.infrastructure import InfrastructureSampler
    from lumonox.widgets import BaseDashboardWidget


@dataclass(slots=True)
class _MonitorConfig:
    api_key: str | None
    ingest_url: str | None
    startup_ingest_ping: bool
    service_name: str
    environment: str
    queue_maxsize: int
    batch_size: int
    flush_interval_s: float
    max_retries: int
    retry_backoff_s: float
    debug: bool
    # When set (e.g. "/lumonox"), requests under this prefix use request.url.path so DB
    # "exclude internal traffic" filters match submounted dashboard/ingest routes.
    mount_prefix: str | None
    capture_headers: bool
    capture_query_params: bool
    scrub_keys: frozenset[str]
    request_sample_rate: float
    ignore_path_prefixes: tuple[str, ...]
    dashboard_widgets: tuple[BaseDashboardWidget, ...]
    infrastructure_sampler: InfrastructureSampler | None
    infrastructure_probe_interval_s: float
    # Min seconds between attaching widget payloads to each captured HTTP event (0 = every event).
    dashboard_widgets_attach_interval_s: float
    # Serialized JSON body budget per POST (UTF-8 bytes, pre-gzip).
    # Aligns with server INGEST_MAX_REQUEST_BYTES.
    ingest_max_batch_bytes: int
    # Optional sync observer for SDK pressure (off by default; must not raise).
    telemetry_observer: Callable[[Mapping[str, Any]], None] | None
    # Bounded parallel ingest POSTs (1 preserves strict ordering).
    max_concurrent_sends: int
    # After this many consecutive terminal send failures (per process), fast-fail POSTs for
    # ``circuit_open_seconds`` (half-open: next POST after cooldown tries again). ``0`` disables.
    circuit_failure_threshold: int
    circuit_open_seconds: float
    release: str | None
    git_sha: str | None


def build_monitor_config(**kwargs: Any) -> _MonitorConfig:
    """Resolve kwargs + ``LUMONOX_*`` env vars + defaults into a ``_MonitorConfig``.

    The single place every framework adapter funnels through to construct
    config, so the contract (which env vars matter, what the defaults are,
    which scrub keys ship by default) cannot drift between adapters.
    """
    # Lazy import so ``lumonox.core.config`` can be imported without pulling
    # psutil — keeps the SDK degradable when psutil is missing.
    from lumonox.core.infrastructure import InfrastructureSampler
    from lumonox.widgets import BaseDashboardWidget

    resolved_kwargs = dict(kwargs)

    # Pip-installed "drop a .env, add one line" config: populate LUMONOX_* keys
    # from a nearby .env before reading them. Never overrides real env vars;
    # opt out with ``load_dotenv=False`` or target a file with ``dotenv_path``.
    if bool(resolved_kwargs.get("load_dotenv", True)):
        from lumonox.core.dotenv import load_lumonox_dotenv

        dotenv_path_arg = resolved_kwargs.get("dotenv_path")
        load_lumonox_dotenv(dotenv_path_arg if isinstance(dotenv_path_arg, str) else None)

    env_api_key = os.getenv("LUMONOX_API_KEY")
    env_ingest_url = os.getenv("LUMONOX_INGEST_URL") or os.getenv("LUMONOX_ENDPOINT")

    extra_scrub = resolved_kwargs.get("scrub_keys", ())
    scrub_keys = frozenset(
        {
            *DEFAULT_SCRUB_KEYS,
            *(
                str(value).strip().lower()
                for value in (extra_scrub if isinstance(extra_scrub, list | tuple | set) else [])
                if str(value).strip()
            ),
        }
    )

    raw_dashboard_widgets = resolved_kwargs.get("dashboard_widgets")
    widgets_iterable = (
        raw_dashboard_widgets if isinstance(raw_dashboard_widgets, list | tuple) else ()
    )

    telemetry_observer_arg = resolved_kwargs.get("telemetry_observer")
    telemetry_observer = telemetry_observer_arg if callable(telemetry_observer_arg) else None

    return _MonitorConfig(
        api_key=resolved_kwargs.get("api_key", env_api_key),
        ingest_url=resolved_kwargs.get("ingest_url", env_ingest_url),
        startup_ingest_ping=bool(
            resolved_kwargs.get(
                "startup_ingest_ping",
                resolved_kwargs.get("embedded_startup_ingest_ping", False),
            )
        ),
        service_name=resolved_kwargs.get("service_name", "api"),
        environment=resolved_kwargs.get("environment", "production"),
        queue_maxsize=int(
            resolved_kwargs.get(
                "queue_maxsize",
                _env_int("LUMONOX_MAX_QUEUE_SIZE", 1000),
            )
        ),
        batch_size=int(
            resolved_kwargs.get(
                "batch_size",
                _env_int("LUMONOX_BATCH_MAX_EVENTS", 50),
            )
        ),
        flush_interval_s=float(
            resolved_kwargs.get(
                "flush_interval_s",
                _env_float("LUMONOX_FLUSH_INTERVAL_SECONDS", 2.0),
            )
        ),
        max_retries=int(resolved_kwargs.get("max_retries", 3)),
        retry_backoff_s=float(resolved_kwargs.get("retry_backoff_s", 0.1)),
        debug=bool(
            resolved_kwargs.get(
                "debug",
                os.getenv("LUMONOX_DEBUG", "").strip() in {"1", "true", "yes"},
            )
        ),
        mount_prefix=_normalize_mount_prefix(resolved_kwargs.get("mount_prefix")),
        capture_headers=bool(
            resolved_kwargs.get(
                "capture_headers",
                _env_bool("LUMONOX_CAPTURE_HEADERS", False),
            )
        ),
        capture_query_params=bool(
            resolved_kwargs.get(
                "capture_query_params",
                _env_bool("LUMONOX_CAPTURE_QUERY_PARAMS", False),
            )
        ),
        scrub_keys=scrub_keys,
        request_sample_rate=_clamp_sample_rate(
            float(
                resolved_kwargs.get(
                    "request_sample_rate",
                    _env_float("LUMONOX_REQUEST_SAMPLE_RATE", 1.0),
                )
            )
        ),
        ignore_path_prefixes=_resolve_ignore_path_prefixes(
            resolved_kwargs.get("ignore_path_prefixes")
        ),
        dashboard_widgets=tuple(
            widget for widget in widgets_iterable if isinstance(widget, BaseDashboardWidget)
        ),
        infrastructure_sampler=(
            InfrastructureSampler()
            if bool(resolved_kwargs.get("capture_infrastructure_metrics", True))
            else None
        ),
        infrastructure_probe_interval_s=(
            max(
                0.0,
                float(
                    resolved_kwargs.get(
                        "infrastructure_probe_interval_ms",
                        _env_float("LUMONOX_INFRA_PROBE_INTERVAL_MS", 0.0),
                    )
                ),
            )
            / 1000.0
        ),
        dashboard_widgets_attach_interval_s=max(
            0.0,
            float(
                resolved_kwargs.get(
                    "dashboard_widgets_attach_interval_s",
                    _env_float("LUMONOX_DASHBOARD_WIDGET_ATTACH_INTERVAL_S", 15.0),
                )
            ),
        ),
        ingest_max_batch_bytes=max(
            256,
            int(
                resolved_kwargs.get(
                    "ingest_max_batch_bytes",
                    _env_int("LUMONOX_INGEST_MAX_BATCH_BYTES", 786_432),
                )
            ),
        ),
        telemetry_observer=telemetry_observer,
        max_concurrent_sends=max(
            1,
            int(
                resolved_kwargs.get(
                    "max_concurrent_sends",
                    _env_int("LUMONOX_MAX_CONCURRENT_SENDS", 1),
                )
            ),
        ),
        circuit_failure_threshold=max(
            0,
            int(
                resolved_kwargs.get(
                    "circuit_failure_threshold",
                    _env_int("LUMONOX_CIRCUIT_FAILURE_THRESHOLD", 0),
                )
            ),
        ),
        circuit_open_seconds=max(
            0.5,
            float(
                resolved_kwargs.get(
                    "circuit_open_seconds",
                    _env_float("LUMONOX_CIRCUIT_OPEN_SECONDS", 30.0),
                )
            ),
        ),
        release=_optional_metadata_str(
            resolved_kwargs.get("release"), "LUMONOX_RELEASE", max_len=200
        ),
        git_sha=_optional_metadata_str(
            resolved_kwargs.get("git_sha"), "LUMONOX_GIT_SHA", max_len=120
        ),
    )
