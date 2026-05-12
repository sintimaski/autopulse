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
from email.utils import parsedate_to_datetime
from importlib import metadata
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from lumonox._infrastructure import InfrastructureSampler
from lumonox._runtime_context import reset_correlation_id, set_correlation_id
from lumonox.widgets import BaseDashboardWidget, serialize_dashboard_widgets

logger = logging.getLogger("lumonox.monitor")

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


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _debug_log(enabled: bool, message: str) -> None:
    if not enabled:
        return
    print(f"[lumonox] {message}", file=sys.stderr)


def _sdk_version() -> str:
    """Resolve the installed distribution version (PyPI ``lumonox-sdk`` or API ``lumonox``)."""
    for dist_name in ("lumonox-sdk", "lumonox"):
        try:
            return metadata.version(dist_name)
        except metadata.PackageNotFoundError:
            continue
    return "unknown"


def _split_events_for_ingest_json_budget(
    events: list[dict[str, Any]], *, max_bytes: int, sdk_version: str
) -> list[list[dict[str, Any]]]:
    """Split ``events`` so each chunk's JSON body stays under ``max_bytes`` (best-effort).

    If a single event still exceeds ``max_bytes``, it is sent alone so operators see 413s
    instead of silently merging oversized payloads.
    """
    if not events:
        return []
    if max_bytes <= 0:
        return [list(events)]
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for ev in events:
        trial = current + [ev]
        trial_bytes = len(json.dumps({"events": trial, "sdk_version": sdk_version}).encode("utf-8"))
        if trial_bytes <= max_bytes:
            current = trial
            continue
        if current:
            chunks.append(current)
            current = []
        single_bytes = len(json.dumps({"events": [ev], "sdk_version": sdk_version}).encode("utf-8"))
        if single_bytes <= max_bytes:
            current = [ev]
        else:
            chunks.append([ev])
    if current:
        chunks.append(current)
    return chunks


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


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


def _normalize_path_prefix(prefix: str) -> str:
    cleaned = str(prefix).strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    if cleaned != "/":
        cleaned = cleaned.rstrip("/")
    return cleaned


def _resolve_ignore_path_prefixes(raw: object | None) -> tuple[str, ...]:
    if raw is None:
        return tuple(
            prefix
            for prefix in (
                _normalize_path_prefix(value)
                for value in _env_csv("LUMONOX_IGNORE_PATH_PREFIXES", "/health,/ready")
            )
            if prefix
        )
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, list | tuple | set):
        candidates = [str(value) for value in raw]
    else:
        return ()
    normalized = []
    for candidate in candidates:
        for part in candidate.split(","):
            prefix = _normalize_path_prefix(part)
            if prefix:
                normalized.append(prefix)
    return tuple(dict.fromkeys(normalized))


def _path_is_ignored(path: str, ignore_path_prefixes: tuple[str, ...]) -> bool:
    if not ignore_path_prefixes:
        return False
    return any(path.startswith(prefix) for prefix in ignore_path_prefixes)


def _clamp_sample_rate(value: float) -> float:
    return min(1.0, max(0.0, value))


def _should_sample_request(
    *,
    request_sample_rate: float,
    method: str,
    path: str,
    request_id: str | None,
) -> bool:
    if request_sample_rate >= 1.0:
        return True
    if request_sample_rate <= 0.0:
        return False
    key = request_id.strip() if request_id else f"{method}:{path}:{_utc_now_iso()}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], byteorder="big", signed=False) / float(1 << 64)
    return fraction < request_sample_rate


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


def _remove_event_handler(app: Any, event: str, handler: Callable[[], Awaitable[None]]) -> None:
    """Best-effort rollback for previously added startup/shutdown handlers."""
    handlers_attr = "on_startup" if event == "startup" else "on_shutdown"
    candidates = [
        getattr(app, handlers_attr, None),
        getattr(getattr(app, "router", None), handlers_attr, None),
    ]
    for handlers in candidates:
        if isinstance(handlers, list):
            while handler in handlers:
                handlers.remove(handler)


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


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = (response.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    now = datetime.now(tz=UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0.0, (dt - now).total_seconds())


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
        self._send_semaphore: asyncio.Semaphore | None = None
        self._pending_send_tasks: set[asyncio.Task[None]] = set()

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
        self._send_semaphore = asyncio.Semaphore(max(1, self._config.max_concurrent_sends))
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
        if self._config.startup_ingest_ping:
            # Synthetic request so dashboard onboarding can observe first ingest without
            # waiting for application traffic. Path avoids is_lumonox_internal_path filters.
            self.enqueue(
                {
                    "type": "request",
                    "timestamp": _utc_now_iso(),
                    "service_name": self._config.service_name,
                    "environment": self._config.environment,
                    "method": "GET",
                    "path": "/.well-known/lumonox-onboarding",
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

    def _emit_telemetry(self, payload: Mapping[str, Any]) -> None:
        observer = self._config.telemetry_observer
        if observer is None:
            return
        try:
            observer(dict(payload))
        except Exception:
            return

    async def _sender_loop(self) -> None:
        if not self._send_enabled:
            return
        loop = asyncio.get_running_loop()
        batch: list[dict[str, Any]] = []
        next_flush = loop.time() + self._config.flush_interval_s
        sem = self._send_semaphore
        if sem is None:
            return

        async def _bounded_send(payload: list[dict[str, Any]]) -> None:
            async with sem:
                await self._send_batch(payload)

        try:
            while not self._stopping.is_set():
                timeout = max(0.0, next_flush - loop.time())
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                    batch.append(event)
                except TimeoutError:
                    if not batch:
                        next_flush = loop.time() + self._config.flush_interval_s
                if batch and (len(batch) >= self._config.batch_size or loop.time() >= next_flush):
                    to_send = list(batch)
                    batch.clear()
                    next_flush = loop.time() + self._config.flush_interval_s
                    task = asyncio.create_task(_bounded_send(to_send))
                    self._pending_send_tasks.add(task)
                    task.add_done_callback(self._pending_send_tasks.discard)
        finally:
            if self._pending_send_tasks:
                await asyncio.gather(*list(self._pending_send_tasks), return_exceptions=True)
            if batch:
                async with sem:
                    await self._send_batch(list(batch))

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        if self._client is None or self._config.ingest_url is None or self._config.api_key is None:
            return
        sdk_ver = _sdk_version()
        parts = _split_events_for_ingest_json_budget(
            batch, max_bytes=self._config.ingest_max_batch_bytes, sdk_version=sdk_ver
        )
        for part in parts:
            await self._send_single_json_chunk(part, sdk_ver)

    async def _send_single_json_chunk(self, batch: list[dict[str, Any]], sdk_ver: str) -> None:
        if not batch:
            return
        if self._client is None or self._config.ingest_url is None or self._config.api_key is None:
            return
        started = monotonic()
        # One key per HTTP POST; retries reuse the same key to enable backend dedup.
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Idempotency-Key": uuid4().hex,
        }
        payload = {"events": batch, "sdk_version": sdk_ver}
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
                self._emit_telemetry(
                    {
                        "kind": "ingest_batch",
                        "ok": True,
                        "events": len(batch),
                        "attempt": attempt + 1,
                        "duration_ms": round((monotonic() - started) * 1000.0, 3),
                        "queue_depth": self._queue.qsize(),
                    }
                )
                return
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                retryable_4xx = {408, 409, 425, 429}
                should_retry = code >= 500 or code in retryable_4xx
                if not should_retry:
                    _debug_log(
                        self._config.debug,
                        f"batch send got non-retryable status={code}; not retrying",
                    )
                    self._emit_telemetry(
                        {
                            "kind": "ingest_batch",
                            "ok": False,
                            "events": len(batch),
                            "attempt": attempt + 1,
                            "http_status": code,
                            "queue_depth": self._queue.qsize(),
                        }
                    )
                    return
                _debug_log(
                    self._config.debug,
                    f"batch send failed attempt={attempt + 1} error={type(exc).__name__}: {exc}",
                )
                if attempt >= self._config.max_retries:
                    _debug_log(self._config.debug, "dropping batch after retries exhausted")
                    self._emit_telemetry(
                        {
                            "kind": "ingest_batch",
                            "ok": False,
                            "events": len(batch),
                            "attempt": attempt + 1,
                            "http_status": code,
                            "queue_depth": self._queue.qsize(),
                            "terminal": True,
                        }
                    )
                    return
                retry_after = _retry_after_seconds(exc.response) if code == 429 else None
                sleep_seconds = (
                    retry_after
                    if retry_after is not None
                    else self._config.retry_backoff_s * (2**attempt)
                )
                await asyncio.sleep(sleep_seconds)
            except Exception as exc:
                _debug_log(
                    self._config.debug,
                    f"batch send failed attempt={attempt + 1} error={type(exc).__name__}: {exc}",
                )
                if attempt >= self._config.max_retries:
                    _debug_log(self._config.debug, "dropping batch after retries exhausted")
                    self._emit_telemetry(
                        {
                            "kind": "ingest_batch",
                            "ok": False,
                            "events": len(batch),
                            "attempt": attempt + 1,
                            "queue_depth": self._queue.qsize(),
                            "terminal": True,
                            "error": type(exc).__name__,
                        }
                    )
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
                        "path": "/lumonox/internal/infrastructure-probe",
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


class _LumonoxMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, dispatcher: _EventDispatcher, config: _MonitorConfig) -> None:
        super().__init__(app)
        self._dispatcher = dispatcher
        self._config = config
        self._last_dashboard_widgets_attach_monotonic = 0.0

    def _attach_dashboard_widgets_if_due(self, common: dict[str, Any]) -> None:
        """Attach widget + infrastructure payloads at a bounded rate to avoid DB blowups."""
        cfg = self._config
        if not cfg.dashboard_widgets and cfg.infrastructure_sampler is None:
            return
        now = monotonic()
        interval = cfg.dashboard_widgets_attach_interval_s
        if (
            interval > 0
            and self._last_dashboard_widgets_attach_monotonic > 0.0
            and now - self._last_dashboard_widgets_attach_monotonic < interval
        ):
            return
        self._last_dashboard_widgets_attach_monotonic = now

        if cfg.dashboard_widgets:
            widget_payload = serialize_dashboard_widgets(list(cfg.dashboard_widgets))
            if widget_payload["definitions"] or widget_payload["points"]:
                common["dashboard_widgets"] = widget_payload

        if cfg.infrastructure_sampler is not None:
            infrastructure_metrics = cfg.infrastructure_sampler.sample()
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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_at = perf_counter()
        header_rid = (request.headers.get("x-request-id") or "").strip()
        header_cid = (request.headers.get("x-correlation-id") or "").strip()
        correlation_id = (header_rid or header_cid or str(uuid4()))[:128]
        correlation_token = set_correlation_id(correlation_id)

        def _stamp_response(resp: Response) -> Response:
            if correlation_id:
                resp.headers.setdefault("X-Request-ID", correlation_id)
            return resp

        common: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "method": request.method,
            "request_id": correlation_id,
        }
        send_ok = getattr(
            self._dispatcher,
            "_send_enabled",
            bool(self._config.api_key and self._config.ingest_url),
        )
        if send_ok:
            self._attach_dashboard_widgets_if_due(common)
        if send_ok and self._config.capture_headers:
            common["headers"] = dict(request.headers.items())
        if send_ok and self._config.capture_query_params:
            common["query_params"] = dict(request.query_params.multi_items())
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                resolved_path = _resolve_route_path(request, mount_prefix=self._config.mount_prefix)
                if _path_is_ignored(resolved_path, self._config.ignore_path_prefixes):
                    raise
                latency_ms = (perf_counter() - started_at) * 1000
                stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                self._dispatcher.enqueue(
                    {
                        **common,
                        "path": resolved_path,
                        "type": "request",
                        "status_code": 500,
                        "latency_ms": round(latency_ms, 3),
                    }
                )
                self._dispatcher.enqueue(
                    {
                        **common,
                        "path": resolved_path,
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
                            resolved_path,
                        ),
                    }
                )
                raise
            resolved_path = _resolve_route_path(request, mount_prefix=self._config.mount_prefix)
            if _path_is_ignored(resolved_path, self._config.ignore_path_prefixes):
                return _stamp_response(response)
            latency_ms = (perf_counter() - started_at) * 1000
            should_capture_request = response.status_code >= 500 or _should_sample_request(
                request_sample_rate=self._config.request_sample_rate,
                method=request.method,
                path=resolved_path,
                request_id=correlation_id,
            )
            if not should_capture_request:
                return _stamp_response(response)
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": resolved_path,
                    "type": "request",
                    "status_code": response.status_code,
                    "latency_ms": round(latency_ms, 3),
                }
            )
            return _stamp_response(response)
        finally:
            reset_correlation_id(correlation_token)


def monitor(app: Any, **kwargs: Any) -> None:
    """Attach Lumonox monitoring to a FastAPI application.

    The SDK always fails silent by default: monitoring failures never block
    user requests.
    """
    if not all(hasattr(app, attr) for attr in ("state", "add_middleware")):
        return
    if getattr(app.state, "_lumonox_configured", False):
        return
    resolved_kwargs = dict(kwargs)
    env_api_key = os.getenv("LUMONOX_API_KEY")
    env_ingest_url = os.getenv("LUMONOX_INGEST_URL") or os.getenv("LUMONOX_ENDPOINT")
    mode = str(kwargs.get("mode", "remote")).strip().lower()
    if mode == "embedded":
        logger.warning(
            "lumonox.monitor: mode='embedded' is no longer supported; "
            "run the backend separately and use remote ingest (LUMONOX_INGEST_URL + "
            "LUMONOX_API_KEY)."
        )
        mode = "remote"
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
        telemetry_observer=(
            _telemetry_observer_arg
            if callable(_telemetry_observer_arg := resolved_kwargs.get("telemetry_observer"))
            else None
        ),
        max_concurrent_sends=max(
            1,
            int(
                resolved_kwargs.get(
                    "max_concurrent_sends",
                    _env_int("LUMONOX_MAX_CONCURRENT_SENDS", 1),
                )
            ),
        ),
    )
    dispatcher = _EventDispatcher(
        config,
        client=resolved_kwargs.get("http_client"),
        owns_client=resolved_kwargs.get("owns_http_client"),
    )
    if not dispatcher._send_enabled:
        logger.warning(
            "lumonox.monitor: remote ingest is disabled because LUMONOX_INGEST_URL and "
            "LUMONOX_API_KEY are not both set; middleware is attached but events will not "
            "be sent."
        )
    if not _add_event_handler(app, "startup", dispatcher.start):
        return
    startup_registered = True
    shutdown_registered = False
    if not _add_event_handler(app, "shutdown", dispatcher.stop):
        if startup_registered:
            _remove_event_handler(app, "startup", dispatcher.start)
        return
    shutdown_registered = True
    try:
        app.add_middleware(_LumonoxMiddleware, dispatcher=dispatcher, config=config)
    except Exception:
        if shutdown_registered:
            _remove_event_handler(app, "shutdown", dispatcher.stop)
        if startup_registered:
            _remove_event_handler(app, "startup", dispatcher.start)
        return
    app.state._lumonox_config = config
    app.state._lumonox_dispatcher = dispatcher
    app.state._lumonox_configured = True
