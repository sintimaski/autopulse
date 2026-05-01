"""Async helpers for DuckDB work on thread pools.

DuckDB calls are synchronous. ``asyncio.to_thread`` uses the process default
`ThreadPoolExecutor`, which is shared with ingest, retention, and dashboard
code. Under high ingest load, dashboard reads can queue behind many writers and
appear to "block".

Dedicated pools isolate dashboard-style reads from write-heavy paths so reads
still get threads while writes compete only within the write pool.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Lock
from typing import Any, TypeVar

_T = TypeVar("_T")

_read_executor: ThreadPoolExecutor | None = None
_write_executor: ThreadPoolExecutor | None = None
_init_lock = Lock()


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
                "AUTOPULSE_DUCKDB_READ_EXECUTOR_WORKERS",
                default=24,
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
                "AUTOPULSE_DUCKDB_WRITE_EXECUTOR_WORKERS",
                default=4,
                minimum=1,
                maximum=16,
            )
            _write_executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="ap-duckdb-w",
            )
        return _write_executor


async def run_duckdb_read_sync(fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    loop = asyncio.get_running_loop()
    executor = get_duckdb_read_executor()
    if kwargs:
        return await loop.run_in_executor(executor, partial(fn, *args, **kwargs))
    if args:
        return await loop.run_in_executor(executor, partial(fn, *args))
    return await loop.run_in_executor(executor, fn)


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
