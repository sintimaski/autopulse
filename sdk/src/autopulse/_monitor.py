from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import re
import sys
import traceback
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from time import perf_counter
from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from autopulse._infrastructure import InfrastructureSampler
from autopulse.widgets import BaseDashboardWidget, serialize_dashboard_widgets

logger = logging.getLogger("autopulse.monitor")

# Gzip ingest bodies at or above this UTF-8 JSON size to cut bandwidth (server decompresses).
_INGEST_JSON_GZIP_MIN_BYTES = 2048

DEFAULT_SCRUB_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "x-api-key",
        "access_token",
        "refresh_token",
    }
)


@dataclass(slots=True)
class _MonitorConfig:
    api_key: str | None
    ingest_url: str | None
    embedded_startup_ingest_ping: bool
    service_name: str
    environment: str
    queue_maxsize: int
    batch_size: int
    flush_interval_s: float
    max_retries: int
    retry_backoff_s: float
    debug: bool
    # When set (e.g. "/autopulse"), requests under this prefix use request.url.path so DB
    # "exclude internal traffic" filters match embedded dashboard/ingest routes.
    mount_prefix: str | None
    capture_headers: bool
    capture_query_params: bool
    scrub_keys: frozenset[str]
    dashboard_widgets: tuple[BaseDashboardWidget, ...]
    infrastructure_sampler: InfrastructureSampler | None
    infrastructure_probe_interval_s: float


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _debug_log(enabled: bool, message: str) -> None:
    if not enabled:
        return
    print(f"[autopulse] {message}", file=sys.stderr)


def _sdk_version() -> str:
    try:
        return metadata.version("autopulse")
    except metadata.PackageNotFoundError:
        return "unknown"


def _stable_error_hash(
    exception_type: str, exception_message: str, stack_trace: str, path: str
) -> str:
    # Keep grouping stable across equivalent traces where only line numbers differ.
    # Include route path so the same exception text on different endpoints does not share one hash.
    normalized_stack_trace = re.sub(r"line \d+", "line ?", stack_trace)
    digest = hashlib.sha256()
    digest.update(exception_type.encode("utf-8"))
    digest.update(b"|")
    digest.update(exception_message.encode("utf-8"))
    digest.update(b"|")
    digest.update(normalized_stack_trace.encode("utf-8"))
    digest.update(b"|")
    digest.update((path or "").encode("utf-8"))
    return digest.hexdigest()


def _normalize_mount_prefix(raw: object | None) -> str | None:
    if raw is None:
        return None
    prefix = str(raw).strip()
    if not prefix:
        return None
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if prefix != "/":
        prefix = prefix.rstrip("/")
    return prefix if prefix != "/" else None


def _resolve_route_path(request: Request, *, mount_prefix: str | None) -> str:
    wire = request.url.path
    base = _normalize_mount_prefix(mount_prefix)
    if base and (wire == base or wire.startswith(f"{base}/")):
        return wire
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return wire


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _is_sensitive_key(key: str, scrub_keys: frozenset[str]) -> bool:
    lowered = key.lower()
    if lowered in scrub_keys:
        return True
    return any(
        marker in lowered
        for marker in (
            "token",
            "secret",
            "password",
            "passwd",
            "api_key",
            "apikey",
            "api-key",
            "authorization",
            "cookie",
        )
    )


def _scrub_value(value: Any, scrub_keys: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            key: (
                "[REDACTED]"
                if _is_sensitive_key(key, scrub_keys)
                else _scrub_value(item, scrub_keys)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_value(item, scrub_keys) for item in value]
    return value


def _add_event_handler(app: Any, event: str, handler: Callable[[], Awaitable[None]]) -> bool:
    add_event_handler = getattr(app, "add_event_handler", None)
    if callable(add_event_handler):
        add_event_handler(event, handler)
        return True
    router = getattr(app, "router", None)
    router_add_event_handler = getattr(router, "add_event_handler", None)
    if callable(router_add_event_handler):
        router_add_event_handler(event, handler)
        return True
    return False


def _build_infrastructure_widget_payload(metrics: Mapping[str, Any]) -> dict[str, Any]:
    specs: tuple[tuple[str, str, str, str, int], ...] = (
        ("host_cpu_percent", "infra_host_cpu_percent", "Host CPU", "%", 500),
        ("host_memory_used_percent", "infra_host_memory_percent", "Host memory used", "%", 510),
        ("process_cpu_percent", "infra_process_cpu_percent", "App CPU", "%", 520),
        ("process_memory_percent", "infra_process_memory_percent", "App memory share", "%", 530),
        ("process_memory_rss_bytes", "infra_process_memory_rss_mb", "App RSS memory", "MB", 540),
        ("disk_used_percent", "infra_disk_used_percent", "Host disk used", "%", 550),
        ("disk_io_read_bytes", "infra_disk_io_read_mb", "Disk I/O read", "MB", 552),
        ("disk_io_write_bytes", "infra_disk_io_write_mb", "Disk I/O write", "MB", 553),
        ("network_bytes_recv", "infra_network_received_mb", "Network received", "MB", 560),
        ("network_bytes_sent", "infra_network_sent_mb", "Network sent", "MB", 570),
    )
    now = _utc_now_iso()
    definitions: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for source_key, widget_id, title, unit, order in specs:
        raw = metrics.get(source_key)
        if not isinstance(raw, int | float):
            continue
        value = float(raw)
        # psutil uses ..._recv / ..._sent for NIC counters (bytes cumulative since boot).
        if source_key.endswith("_bytes") or source_key in (
            "network_bytes_recv",
            "network_bytes_sent",
        ):
            value = value / (1024 * 1024)
        definitions.append(
            {
                "widget_id": widget_id,
                "type": "line",
                "title": title,
                "description": "Auto-captured infrastructure metric",
                "order": order,
                "config": {"unit": unit},
            }
        )
        points.append({"widget_id": widget_id, "timestamp": now, "value": value})
    return {"definitions": definitions, "points": points}


def _merge_widget_payloads(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    definitions_by_id: dict[str, dict[str, Any]] = {}
    for source in (primary, secondary):
        for item in source.get("definitions", []):
            if isinstance(item, dict) and isinstance(item.get("widget_id"), str):
                definitions_by_id[item["widget_id"]] = item
    points: list[dict[str, Any]] = []
    for source in (primary, secondary):
        for point in source.get("points", []):
            if isinstance(point, dict):
                points.append(point)
    return {"definitions": list(definitions_by_id.values()), "points": points}


class _EventDispatcher:
    def __init__(
        self,
        config: _MonitorConfig,
        *,
        client: httpx.AsyncClient | None = None,
        owns_client: bool | None = None,
    ) -> None:
        self._config = config
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=config.queue_maxsize)
        self._task: asyncio.Task[None] | None = None
        self._infrastructure_probe_task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._client = client
        self._owns_client = client is None if owns_client is None else owns_client
        self._send_enabled = bool(config.ingest_url and config.api_key)

    async def start(self) -> None:
        if self._task is not None:
            return
        if not self._send_enabled:
            _debug_log(
                self._config.debug,
                "sender disabled (missing api_key or ingest_url); no events will be sent",
            )
            return
        self._stopping.clear()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0)
        self._task = asyncio.create_task(self._sender_loop())
        if (
            self._config.infrastructure_sampler is not None
            and self._config.infrastructure_probe_interval_s > 0
        ):
            self._infrastructure_probe_task = asyncio.create_task(self._infrastructure_probe_loop())
        _debug_log(
            self._config.debug,
            "sender started "
            f"ingest_url={self._config.ingest_url} "
            f"batch_size={self._config.batch_size} "
            f"flush_interval_s={self._config.flush_interval_s}",
        )
        if self._config.embedded_startup_ingest_ping:
            # Synthetic request so dashboard onboarding can observe first ingest without
            # waiting for application traffic. Path avoids is_autopulse_internal_path filters.
            self.enqueue(
                {
                    "type": "request",
                    "timestamp": _utc_now_iso(),
                    "service_name": self._config.service_name,
                    "environment": self._config.environment,
                    "method": "GET",
                    "path": "/.well-known/autopulse-onboarding",
                    "status_code": 204,
                    "latency_ms": 0.0,
                    "request_id": None,
                }
            )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopping.set()
        await self._task
        self._task = None
        if self._infrastructure_probe_task is not None:
            await self._infrastructure_probe_task
            self._infrastructure_probe_task = None
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def enqueue(self, event: dict[str, Any]) -> None:
        if not self._send_enabled:
            return
        try:
            self._queue.put_nowait(_scrub_value(event, self._config.scrub_keys))
            _debug_log(
                self._config.debug,
                f"event enqueued type={event.get('type')} queue_size={self._queue.qsize()}",
            )
        except asyncio.QueueFull:
            _debug_log(self._config.debug, "event queue is full; dropping event")

    async def _sender_loop(self) -> None:
        if not self._send_enabled:
            return
        loop = asyncio.get_running_loop()
        batch: list[dict[str, Any]] = []
        next_flush = loop.time() + self._config.flush_interval_s
        while not self._stopping.is_set():
            timeout = max(0.0, next_flush - loop.time())
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                batch.append(event)
            except TimeoutError:
                if not batch:
                    next_flush = loop.time() + self._config.flush_interval_s
            if batch and (len(batch) >= self._config.batch_size or loop.time() >= next_flush):
                await self._send_batch(batch)
                batch = []
                next_flush = loop.time() + self._config.flush_interval_s
        if batch:
            await self._send_batch(batch)

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        if self._client is None or self._config.ingest_url is None or self._config.api_key is None:
            return
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        payload = {"events": batch, "sdk_version": _sdk_version()}
        body_json = json.dumps(payload).encode("utf-8")
        post_headers = dict(headers)
        post_kwargs: dict[str, Any]
        if len(body_json) >= _INGEST_JSON_GZIP_MIN_BYTES:
            post_headers["Content-Type"] = "application/json"
            post_headers["Content-Encoding"] = "gzip"
            post_kwargs = {"content": gzip.compress(body_json, compresslevel=6)}
        else:
            post_kwargs = {"json": payload}
        for attempt in range(self._config.max_retries + 1):
            try:
                _debug_log(
                    self._config.debug,
                    f"sending batch events={len(batch)} attempt={attempt + 1}/"
                    f"{self._config.max_retries + 1} url={self._config.ingest_url}",
                )
                response = await self._client.post(
                    self._config.ingest_url,
                    headers=post_headers,
                    **post_kwargs,
                )
                response.raise_for_status()
                _debug_log(
                    self._config.debug,
                    "batch sent successfully "
                    f"status={response.status_code} accepted_events={len(batch)}",
                )
                return
            except Exception as exc:
                _debug_log(
                    self._config.debug,
                    f"batch send failed attempt={attempt + 1} error={type(exc).__name__}: {exc}",
                )
                if attempt >= self._config.max_retries:
                    _debug_log(self._config.debug, "dropping batch after retries exhausted")
                    return
                sleep_seconds = self._config.retry_backoff_s * (2**attempt)
                await asyncio.sleep(sleep_seconds)

    async def _infrastructure_probe_loop(self) -> None:
        while not self._stopping.is_set():
            sampler = self._config.infrastructure_sampler
            if sampler is None:
                return
            metrics = sampler.sample()
            if metrics:
                infra_widgets = _build_infrastructure_widget_payload(metrics)
                self.enqueue(
                    {
                        "type": "request",
                        "timestamp": _utc_now_iso(),
                        "service_name": self._config.service_name,
                        "environment": self._config.environment,
                        "method": "GET",
                        "path": "/autopulse/internal/infrastructure-probe",
                        "status_code": 204,
                        "latency_ms": 0.0,
                        "request_id": None,
                        "infrastructure_metrics": metrics,
                        "dashboard_widgets": infra_widgets,
                    }
                )
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=self._config.infrastructure_probe_interval_s,
                )
            except TimeoutError:
                continue


class _AutoPulseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, dispatcher: _EventDispatcher, config: _MonitorConfig) -> None:
        super().__init__(app)
        self._dispatcher = dispatcher
        self._config = config

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_at = perf_counter()
        common: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "method": request.method,
            "request_id": request.headers.get("x-request-id"),
        }
        send_ok = self._dispatcher._send_enabled
        if send_ok and self._config.dashboard_widgets:
            widget_payload = serialize_dashboard_widgets(list(self._config.dashboard_widgets))
            if widget_payload["definitions"] or widget_payload["points"]:
                common["dashboard_widgets"] = widget_payload
        if send_ok and self._config.infrastructure_sampler is not None:
            infrastructure_metrics = self._config.infrastructure_sampler.sample()
            if infrastructure_metrics:
                common["infrastructure_metrics"] = infrastructure_metrics
                infra_widget_payload = _build_infrastructure_widget_payload(infrastructure_metrics)
                existing_widgets = common.get("dashboard_widgets")
                if (
                    isinstance(existing_widgets, dict)
                    and isinstance(existing_widgets.get("definitions"), list)
                    and isinstance(existing_widgets.get("points"), list)
                ):
                    common["dashboard_widgets"] = _merge_widget_payloads(
                        existing_widgets, infra_widget_payload
                    )
                else:
                    common["dashboard_widgets"] = infra_widget_payload
        if send_ok and self._config.capture_headers:
            common["headers"] = dict(request.headers.items())
        if send_ok and self._config.capture_query_params:
            common["query_params"] = dict(request.query_params.multi_items())
        try:
            response = await call_next(request)
        except Exception as exc:
            latency_ms = (perf_counter() - started_at) * 1000
            stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": _resolve_route_path(request, mount_prefix=self._config.mount_prefix),
                    "type": "request",
                    "status_code": 500,
                    "latency_ms": round(latency_ms, 3),
                }
            )
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": _resolve_route_path(request, mount_prefix=self._config.mount_prefix),
                    "type": "error",
                    "status_code": 500,
                    "latency_ms": round(latency_ms, 3),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "stack_trace": stack_trace,
                    "error_hash": _stable_error_hash(
                        type(exc).__name__,
                        str(exc),
                        stack_trace,
                        _resolve_route_path(request, mount_prefix=self._config.mount_prefix),
                    ),
                }
            )
            raise
        latency_ms = (perf_counter() - started_at) * 1000
        self._dispatcher.enqueue(
            {
                **common,
                "path": _resolve_route_path(request, mount_prefix=self._config.mount_prefix),
                "type": "request",
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 3),
            }
        )
        return response


def monitor(app: Any, **kwargs: Any) -> None:
    """Attach AutoPulse monitoring to a FastAPI application.

    The SDK always fails silent by default: monitoring failures never block
    user requests.
    """
    if not all(hasattr(app, attr) for attr in ("state", "add_middleware")):
        return
    if getattr(app.state, "_autopulse_configured", False):
        return
    resolved_kwargs = dict(kwargs)
    env_api_key = os.getenv("AUTOPULSE_API_KEY")
    env_ingest_url = os.getenv("AUTOPULSE_INGEST_URL") or os.getenv("AUTOPULSE_ENDPOINT")
    mode = str(kwargs.get("mode", "remote")).strip().lower()
    if mode == "embedded":
        try:
            from autopulse._embedded import configure_embedded

            resolved_kwargs.update(configure_embedded(app, kwargs=kwargs))
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("autopulse_backend"):
                _debug_log(
                    bool(kwargs.get("debug", False)),
                    "embedded mode unavailable: install the backend package or use mode='remote'",
                )
            else:
                _debug_log(bool(kwargs.get("debug", False)), f"embedded setup failed: {exc}")
        except Exception as exc:
            _debug_log(bool(kwargs.get("debug", False)), f"embedded setup failed: {exc}")
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
    config = _MonitorConfig(
        api_key=resolved_kwargs.get("api_key", env_api_key),
        ingest_url=resolved_kwargs.get("ingest_url", env_ingest_url),
        embedded_startup_ingest_ping=bool(
            resolved_kwargs.get("embedded_startup_ingest_ping", False)
        ),
        service_name=resolved_kwargs.get("service_name", "api"),
        environment=resolved_kwargs.get("environment", "production"),
        queue_maxsize=int(
            resolved_kwargs.get(
                "queue_maxsize",
                _env_int("AUTOPULSE_MAX_QUEUE_SIZE", 1000),
            )
        ),
        batch_size=int(
            resolved_kwargs.get(
                "batch_size",
                _env_int("AUTOPULSE_BATCH_MAX_EVENTS", 50),
            )
        ),
        flush_interval_s=float(
            resolved_kwargs.get(
                "flush_interval_s",
                _env_float("AUTOPULSE_FLUSH_INTERVAL_SECONDS", 2.0),
            )
        ),
        max_retries=int(resolved_kwargs.get("max_retries", 3)),
        retry_backoff_s=float(resolved_kwargs.get("retry_backoff_s", 0.1)),
        debug=bool(
            resolved_kwargs.get(
                "debug",
                os.getenv("AUTOPULSE_DEBUG", "").strip() in {"1", "true", "yes"},
            )
        ),
        mount_prefix=_normalize_mount_prefix(resolved_kwargs.get("mount_prefix")),
        capture_headers=bool(resolved_kwargs.get("capture_headers", True)),
        capture_query_params=bool(resolved_kwargs.get("capture_query_params", True)),
        scrub_keys=scrub_keys,
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
                        _env_float("AUTOPULSE_INFRA_PROBE_INTERVAL_MS", 0.0),
                    )
                ),
            )
            / 1000.0
        ),
    )
    dispatcher = _EventDispatcher(
        config,
        client=resolved_kwargs.get("http_client"),
        owns_client=resolved_kwargs.get("owns_http_client"),
    )
    if mode != "embedded" and not dispatcher._send_enabled:
        logger.warning(
            "autopulse.monitor: remote ingest is disabled because AUTOPULSE_INGEST_URL and "
            "AUTOPULSE_API_KEY are not both set; middleware is attached but events will not "
            "be sent."
        )
    app.add_middleware(_AutoPulseMiddleware, dispatcher=dispatcher, config=config)
    if not _add_event_handler(app, "startup", dispatcher.start):
        return
    if not _add_event_handler(app, "shutdown", dispatcher.stop):
        return
    app.state._autopulse_config = config
    app.state._autopulse_configured = True
