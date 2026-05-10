"""Async helpers for DuckDB work on thread pools.

The official DuckDB Python package exposes a **synchronous** API (queries run in
the embedded engine). There is no first-party ``async``/await driver; helpers
such as ``aioduck`` still delegate to worker threads under the hood.

We offload DuckDB onto dedicated `ThreadPoolExecutor` pools so the asyncio event
loop stays responsive. Throughput and latency on the hot path are improved by
tuning the embedded store (see ``event_store`` connection config, CTE-based
pagination SQL, and ``LUMONOX_DUCKDB_*`` env vars) rather than pretending the
Python client is non-blocking IO.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from functools import partial
from threading import Lock
from time import monotonic
from typing import Any, TypeVar, cast

from lumonox_backend.metrics import service_metrics

_T = TypeVar("_T")

_read_executor: ThreadPoolExecutor | None = None
_write_executor: ThreadPoolExecutor | None = None
_init_lock = Lock()

_LOG = logging.getLogger(__name__)

_DUCKDB_READ_SLOW_MS_LIGHT = 1_000
_DUCKDB_READ_SLOW_MS_HEAVY = 3_000


def _default_read_executor_workers() -> int:
    cpu = os.cpu_count() or 8
    return max(4, min(64, cpu * 2))


def _slug_read_operation(name: str | None) -> str:
    if not name or not str(name).strip():
        return "unknown"
    slug = re.sub(r"[^a-z0-9_]+", "_", str(name).strip().lower())
    slug = slug.strip("_")[:48] or "unknown"
    return slug


def _parse_worker_count(env_name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    try:
        parsed = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


def get_duckdb_read_executor() -> ThreadPoolExecutor:
    global _read_executor
    with _init_lock:
        if _read_executor is None:
            workers = _parse_worker_count(
                "LUMONOX_DUCKDB_READ_EXECUTOR_WORKERS",
                default=_default_read_executor_workers(),
                minimum=4,
                maximum=64,
            )
            _read_executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="ap-duckdb-r",
            )
        return _read_executor


def get_duckdb_write_executor() -> ThreadPoolExecutor:
    global _write_executor
    with _init_lock:
        if _write_executor is None:
            workers = _parse_worker_count(
                "LUMONOX_DUCKDB_WRITE_EXECUTOR_WORKERS",
                default=4,
                minimum=1,
                maximum=16,
            )
            _write_executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="ap-duckdb-w",
            )
        return _write_executor


async def run_duckdb_read_sync(
    fn: Callable[..., _T],
    /,
    *args: Any,
    duckdb_read_operation: str | None = None,
    **kwargs: Any,
) -> _T:
    loop = asyncio.get_running_loop()
    executor = get_duckdb_read_executor()
    call: Callable[..., Any] = partial(fn, *args, **kwargs)
    slug = _slug_read_operation(duckdb_read_operation)
    wait_start = monotonic()
    fut = loop.run_in_executor(executor, call)
    try:
        result = await fut
    except asyncio.CancelledError:
        if slug:
            service_metrics.increment("duckdb.read.cancelled_wait_total")
            service_metrics.increment(f"duckdb.read.{slug}.cancelled_wait_total")
        raise
    else:
        wait_ms = int((monotonic() - wait_start) * 1000)
        with suppress(Exception):
            service_metrics.increment(f"duckdb.read.{slug}.duration_ms", amount=max(0, wait_ms))
            service_metrics.increment(f"duckdb.read.{slug}.total")
            service_metrics.increment("duckdb.read.duration_ms", amount=max(0, wait_ms))
            service_metrics.increment("duckdb.read.total")
            if wait_ms >= _DUCKDB_READ_SLOW_MS_HEAVY:
                service_metrics.increment(f"duckdb.read.{slug}.slow_heavy_total")
            elif wait_ms >= _DUCKDB_READ_SLOW_MS_LIGHT:
                service_metrics.increment(f"duckdb.read.{slug}.slow_light_total")
            if wait_ms >= _DUCKDB_READ_SLOW_MS_LIGHT:
                _LOG.info("slow duckdb read op=%s duration_ms=%s", slug, wait_ms)
        return cast(_T, result)


async def run_duckdb_write_sync(fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    loop = asyncio.get_running_loop()
    executor = get_duckdb_write_executor()
    if kwargs:
        return await loop.run_in_executor(executor, partial(fn, *args, **kwargs))
    if args:
        return await loop.run_in_executor(executor, partial(fn, *args))
    return await loop.run_in_executor(executor, fn)


def shutdown_duckdb_executors(*, wait: bool = True) -> None:
    """Release DuckDB thread pools (typically from app lifespan shutdown)."""
    global _read_executor, _write_executor
    with _init_lock:
        if _read_executor is not None:
            _read_executor.shutdown(wait=wait, cancel_futures=False)
            _read_executor = None
        if _write_executor is not None:
            _write_executor.shutdown(wait=wait, cancel_futures=False)
            _write_executor = None
