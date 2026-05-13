"""Asynchronous ingest dispatcher: queue, transport, retries, circuit breaker.

This is the SDK's send path and is intentionally framework-agnostic. A
framework adapter constructs ``_EventDispatcher`` from a ``_MonitorConfig``,
registers its ``start`` / ``stop`` with the host framework's lifecycle, and
calls ``enqueue(event)`` from the request hot path. The dispatcher takes it
from there: bounded queue, drop-when-full on backpressure, batched POSTs
with gzip + idempotency-key, retries with exponential backoff,
``Retry-After`` honoring on 429, optional circuit breaker after N consecutive
terminal failures, and an optional sync telemetry observer for the host app
to observe SDK health.

Key invariants — same as the original ``lumonox._monitor`` implementation:

- ``enqueue`` never blocks and never raises. On a full queue it drops the
  event (logged when ``debug=True``) and returns; the host request stays
  fast even when ingest is broken.
- All events are scrubbed (``_scrub_value``) at enqueue time, before they
  could ever leave the process.
- Each HTTP POST carries a fresh ``Idempotency-Key`` so a retried batch is
  deduplicated server-side.
- When the circuit is open, batches are skipped without consuming an
  idempotency key (no work for the backend to dedup).
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from importlib import metadata
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx

from lumonox.core.config import _MonitorConfig
from lumonox.core.events import (
    _build_infrastructure_widget_payload,
    _merge_release_git_into_event,
    _split_events_for_ingest_json_budget,
    _utc_now_iso,
)
from lumonox.core.scrubbing import _scrub_value

logger = logging.getLogger("lumonox.dispatcher")

# Gzip ingest bodies at or above this UTF-8 JSON size to cut bandwidth (server decompresses).
_INGEST_JSON_GZIP_MIN_BYTES = 2048


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
    now = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
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
        self._circuit_lock: asyncio.Lock | None = None
        self._circuit_consecutive_failures: int = 0
        self._circuit_open_until: float = 0.0

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
            ping: dict[str, Any] = {
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
            _merge_release_git_into_event(self._config, ping)
            self.enqueue(ping)

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

    def _ensure_circuit_lock_sync(self) -> asyncio.Lock | None:
        if self._config.circuit_failure_threshold <= 0:
            return None
        if self._circuit_lock is None:
            self._circuit_lock = asyncio.Lock()
        return self._circuit_lock

    async def _circuit_on_send_success(self, lock: asyncio.Lock | None) -> None:
        if lock is None:
            return
        async with lock:
            self._circuit_consecutive_failures = 0
            self._circuit_open_until = 0.0

    async def _circuit_on_terminal_failure(self, lock: asyncio.Lock | None) -> dict[str, Any]:
        """Record a dropped batch; returns extra telemetry keys when the circuit opens."""
        if lock is None:
            return {}
        extra: dict[str, Any] = {}
        async with lock:
            self._circuit_consecutive_failures += 1
            thr = self._config.circuit_failure_threshold
            if self._circuit_consecutive_failures >= thr:
                self._circuit_open_until = monotonic() + self._config.circuit_open_seconds
                self._circuit_consecutive_failures = 0
                extra["circuit_opened"] = True
                _debug_log(
                    self._config.debug,
                    "ingest circuit opened: "
                    f"fast-fail for {self._config.circuit_open_seconds}s "
                    f"after {thr} consecutive terminal failures",
                )
        return extra

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
        circuit_lock = self._ensure_circuit_lock_sync()
        if circuit_lock is not None:
            async with circuit_lock:
                if monotonic() < self._circuit_open_until:
                    self._emit_telemetry(
                        {
                            "kind": "ingest_batch",
                            "ok": False,
                            "circuit_open": True,
                            "skipped": True,
                            "events": len(batch),
                            "queue_depth": self._queue.qsize(),
                        }
                    )
                    _debug_log(
                        self._config.debug,
                        "ingest circuit open; skipping POST until cooldown elapses",
                    )
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
                await self._circuit_on_send_success(circuit_lock)
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
                    tel = {
                        "kind": "ingest_batch",
                        "ok": False,
                        "events": len(batch),
                        "attempt": attempt + 1,
                        "http_status": code,
                        "queue_depth": self._queue.qsize(),
                    }
                    tel.update(await self._circuit_on_terminal_failure(circuit_lock))
                    self._emit_telemetry(tel)
                    return
                _debug_log(
                    self._config.debug,
                    f"batch send failed attempt={attempt + 1} error={type(exc).__name__}: {exc}",
                )
                if attempt >= self._config.max_retries:
                    _debug_log(self._config.debug, "dropping batch after retries exhausted")
                    tel = {
                        "kind": "ingest_batch",
                        "ok": False,
                        "events": len(batch),
                        "attempt": attempt + 1,
                        "http_status": code,
                        "queue_depth": self._queue.qsize(),
                        "terminal": True,
                    }
                    tel.update(await self._circuit_on_terminal_failure(circuit_lock))
                    self._emit_telemetry(tel)
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
                    tel = {
                        "kind": "ingest_batch",
                        "ok": False,
                        "events": len(batch),
                        "attempt": attempt + 1,
                        "queue_depth": self._queue.qsize(),
                        "terminal": True,
                        "error": type(exc).__name__,
                    }
                    tel.update(await self._circuit_on_terminal_failure(circuit_lock))
                    self._emit_telemetry(tel)
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
                infra_evt: dict[str, Any] = {
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
                _merge_release_git_into_event(self._config, infra_evt)
                self.enqueue(infra_evt)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=self._config.infrastructure_probe_interval_s,
                )
            except TimeoutError:
                continue
