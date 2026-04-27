from __future__ import annotations

import asyncio
import hashlib
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
        "access_token",
        "refresh_token",
    }
)


@dataclass(slots=True)
class _MonitorConfig:
    api_key: str | None
    ingest_url: str | None
    service_name: str
    environment: str
    queue_maxsize: int
    batch_size: int
    flush_interval_s: float
    max_retries: int
    retry_backoff_s: float
    debug: bool


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


def _stable_error_hash(exception_type: str, exception_message: str, stack_trace: str) -> str:
    # Keep grouping stable across equivalent traces where only line numbers differ.
    normalized_stack_trace = re.sub(r"line \d+", "line ?", stack_trace)
    digest = hashlib.sha256()
    digest.update(exception_type.encode("utf-8"))
    digest.update(b"|")
    digest.update(exception_message.encode("utf-8"))
    digest.update(b"|")
    digest.update(normalized_stack_trace.encode("utf-8"))
    return digest.hexdigest()


def _resolve_route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


def _scrub_value(value: Any, scrub_keys: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            key: ("[REDACTED]" if key.lower() in scrub_keys else _scrub_value(item, scrub_keys))
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
        _debug_log(
            self._config.debug,
            "sender started "
            f"ingest_url={self._config.ingest_url} "
            f"batch_size={self._config.batch_size} "
            f"flush_interval_s={self._config.flush_interval_s}",
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopping.set()
        await self._task
        self._task = None
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def enqueue(self, event: dict[str, Any]) -> None:
        if not self._send_enabled:
            return
        try:
            self._queue.put_nowait(_scrub_value(event, DEFAULT_SCRUB_KEYS))
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
        for attempt in range(self._config.max_retries + 1):
            try:
                _debug_log(
                    self._config.debug,
                    f"sending batch events={len(batch)} attempt={attempt + 1}/"
                    f"{self._config.max_retries + 1} url={self._config.ingest_url}",
                )
                response = await self._client.post(
                    self._config.ingest_url,
                    json=payload,
                    headers=headers,
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
            "headers": dict(request.headers.items()),
            "query_params": dict(request.query_params.multi_items()),
        }
        try:
            response = await call_next(request)
        except Exception as exc:
            latency_ms = (perf_counter() - started_at) * 1000
            stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": _resolve_route_path(request),
                    "type": "request",
                    "status_code": 500,
                    "latency_ms": round(latency_ms, 3),
                }
            )
            self._dispatcher.enqueue(
                {
                    **common,
                    "path": _resolve_route_path(request),
                    "type": "error",
                    "status_code": 500,
                    "latency_ms": round(latency_ms, 3),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "stack_trace": stack_trace,
                    "error_hash": _stable_error_hash(type(exc).__name__, str(exc), stack_trace),
                }
            )
            raise
        latency_ms = (perf_counter() - started_at) * 1000
        self._dispatcher.enqueue(
            {
                **common,
                "path": _resolve_route_path(request),
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
    mode = str(kwargs.get("mode", "remote")).strip().lower()
    if mode == "embedded":
        try:
            from autopulse._embedded import configure_embedded

            resolved_kwargs.update(configure_embedded(app, kwargs=kwargs))
        except Exception as exc:
            _debug_log(bool(kwargs.get("debug", False)), f"embedded setup failed: {exc}")
    config = _MonitorConfig(
        api_key=resolved_kwargs.get("api_key"),
        ingest_url=resolved_kwargs.get("ingest_url"),
        service_name=resolved_kwargs.get("service_name", "api"),
        environment=resolved_kwargs.get("environment", "production"),
        queue_maxsize=int(resolved_kwargs.get("queue_maxsize", 1000)),
        batch_size=int(resolved_kwargs.get("batch_size", 50)),
        flush_interval_s=float(resolved_kwargs.get("flush_interval_s", 2.0)),
        max_retries=int(resolved_kwargs.get("max_retries", 3)),
        retry_backoff_s=float(resolved_kwargs.get("retry_backoff_s", 0.1)),
        debug=bool(resolved_kwargs.get("debug", False)),
    )
    dispatcher = _EventDispatcher(
        config,
        client=resolved_kwargs.get("http_client"),
        owns_client=resolved_kwargs.get("owns_http_client"),
    )
    app.add_middleware(_AutoPulseMiddleware, dispatcher=dispatcher, config=config)
    if not _add_event_handler(app, "startup", dispatcher.start):
        return
    if not _add_event_handler(app, "shutdown", dispatcher.stop):
        return
    app.state._autopulse_configured = True
