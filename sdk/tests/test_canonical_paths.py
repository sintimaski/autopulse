"""Lock the canonical-vs-legacy import surface.

After the Phase 2 split, ``lumonox.core.*`` and ``lumonox.fastapi.*`` are the
canonical implementation paths; ``lumonox._monitor`` / ``lumonox._infrastructure``
/ ``lumonox._jobs`` / ``lumonox._runtime_context`` remain as re-export shims.
This test enforces four contracts the rest of the SDK depends on:

1. The same symbol is reachable through both paths (object identity, not just
   equality), so callers can mix-and-match without surprises.
2. Patching the canonical psutil reference flips ``InfrastructureSampler.sample``
   off (the shim path no longer carries its own ``psutil`` module-level ref).
3. The top-level ``lumonox.monitor`` / ``lumonox.lumonox`` /
   ``lumonox.capture_background_job`` public-API objects are the same ones
   exported by the canonical modules.
4. Each canonical core/ module exposes the symbols a future framework adapter
   (Django, Flask, …) would import. Removing one of these would silently
   re-introduce a fastapi/ coupling.
"""

from __future__ import annotations

import pytest

import lumonox
from lumonox import _infrastructure as legacy_infra
from lumonox import _jobs as legacy_jobs
from lumonox import _monitor as legacy_monitor
from lumonox import _runtime_context as legacy_runtime
from lumonox.core import (
    config as core_config,
)
from lumonox.core import (
    dispatcher as core_dispatcher,
)
from lumonox.core import (
    events as core_events,
)
from lumonox.core import (
    infrastructure as core_infra,
)
from lumonox.core import (
    jobs as core_jobs,
)
from lumonox.core import (
    runtime_context as core_runtime,
)
from lumonox.core import (
    scrubbing as core_scrubbing,
)
from lumonox.fastapi import middleware as fastapi_middleware


def test_monitor_identity_canonical_and_legacy() -> None:
    assert lumonox.monitor is fastapi_middleware.monitor
    assert lumonox.monitor is legacy_monitor.monitor


def test_infrastructure_sampler_identity() -> None:
    assert core_infra.InfrastructureSampler is legacy_infra.InfrastructureSampler


def test_capture_background_job_identity() -> None:
    assert lumonox.capture_background_job is core_jobs.capture_background_job
    assert lumonox.capture_background_job is legacy_jobs.capture_background_job


def test_runtime_context_identity() -> None:
    assert core_runtime.set_correlation_id is legacy_runtime.set_correlation_id
    assert core_runtime.reset_correlation_id is legacy_runtime.reset_correlation_id
    assert core_runtime.get_correlation_id is legacy_runtime.get_correlation_id


def test_legacy_monitor_shim_resolves_split_symbols() -> None:
    """Names tests historically reached into via ``lumonox._monitor`` still resolve."""
    pairs = (
        ("DEFAULT_SCRUB_KEYS", core_scrubbing.DEFAULT_SCRUB_KEYS),
        ("_scrub_value", core_scrubbing._scrub_value),
        ("_MonitorConfig", core_config._MonitorConfig),
        ("_EventDispatcher", core_dispatcher._EventDispatcher),
        ("_sdk_version", core_dispatcher._sdk_version),
        ("_build_infrastructure_widget_payload", core_events._build_infrastructure_widget_payload),
        ("_split_events_for_ingest_json_budget", core_events._split_events_for_ingest_json_budget),
        ("_stable_error_hash", core_events._stable_error_hash),
        ("_LumonoxMiddleware", fastapi_middleware._LumonoxMiddleware),
        ("_add_event_handler", fastapi_middleware._add_event_handler),
        ("monitor", fastapi_middleware.monitor),
    )
    for name, canonical_obj in pairs:
        assert getattr(legacy_monitor, name) is canonical_obj, name


def test_monkeypatch_on_canonical_psutil_disables_sampler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``InfrastructureSampler.sample()`` reads ``psutil`` from the canonical module."""

    monkeypatch.setattr("lumonox.core.infrastructure.psutil", None)
    sampler = core_infra.InfrastructureSampler(ttl_seconds=0.0)
    assert sampler.sample() == {}


def test_core_modules_expose_framework_adapter_surface() -> None:
    """The pieces a Django / Flask adapter would import from lumonox.core all exist."""
    # Dispatcher + config — the SDK's framework-agnostic send path.
    assert callable(core_dispatcher._EventDispatcher)
    assert callable(core_dispatcher._sdk_version)
    assert callable(core_config._MonitorConfig)
    # Scrubbing — every adapter must scrub before enqueue.
    assert callable(core_scrubbing._scrub_value)
    assert isinstance(core_scrubbing.DEFAULT_SCRUB_KEYS, frozenset)
    # Events — error hashing, batch splitting, infrastructure widget payload.
    assert callable(core_events._stable_error_hash)
    assert callable(core_events._build_infrastructure_widget_payload)
    assert callable(core_events._merge_release_git_into_event)
    # Correlation IDs flow through contextvars on every framework's request path.
    assert callable(core_runtime.set_correlation_id)
    assert callable(core_runtime.reset_correlation_id)
