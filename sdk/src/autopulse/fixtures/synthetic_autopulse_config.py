"""Typed AutoPulse wiring for the synthetic FastAPI fixture.

Use this instead of ad-hoc ``os.getenv`` blocks in ``synthetic_test_app``.

**Deployment shapes**

- **Embedded (one process):** backend + ingest + dashboard mounted on the same
  app — the default ``one_line_embedded()`` preset.
- **Remote (separate server):** SDK sends to an external AutoPulse ingest URL —
  ``separate_backend()`` preset.
- **Embedded + sidecar UI:** still embedded; set ``frontend_mode="sidecar"`` on
  ``SyntheticEmbeddedDeployment`` when you want the Next dashboard as a child
  process instead of static assets.

Environment loading mirrors the variables documented in ``fixtures/README.md``.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, assert_never

from autopulse.widgets import BaseDashboardWidget

SyntheticFrontendMode = Literal["static", "sidecar"]


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


def _env_frontend_mode() -> SyntheticFrontendMode:
    raw = os.getenv("AUTOPULSE_FRONTEND_MODE", "static").strip().lower()
    return "sidecar" if raw == "sidecar" else "static"


@dataclass(frozen=True, slots=True)
class SyntheticAutopulseCommon:
    """Fields shared by embedded and remote monitoring."""

    service_name: str = "synthetic-test-api"
    environment: str = "dev"
    batch_size: int = 20
    flush_interval_s: float = 1.0
    debug: bool = False


@dataclass(frozen=True, slots=True)
class SyntheticEmbeddedDeployment:
    """AutoPulse runs in-process (mount, DB, optional sidecar frontend)."""

    mount_prefix: str = "/autopulse"
    database_url: str = "sqlite+aiosqlite:///./autopulse.db"
    frontend_mode: SyntheticFrontendMode = "static"


@dataclass(frozen=True, slots=True)
class SyntheticRemoteDeployment:
    """Events go to another AutoPulse stack (typical local ``uvicorn`` on :8000)."""

    ingest_url: str = "http://127.0.0.1:8000/ingest"
    api_key: str | None = None


SyntheticAutopulseDeployment = SyntheticEmbeddedDeployment | SyntheticRemoteDeployment


@dataclass(frozen=True, slots=True)
class SyntheticAutopulseFixture:
    """Complete monitor options for ``synthetic_test_app`` (factories or ``from_env``)."""

    common: SyntheticAutopulseCommon
    deployment: SyntheticAutopulseDeployment

    @classmethod
    def one_line_embedded(
        cls,
        *,
        common: SyntheticAutopulseCommon | None = None,
        embedded: SyntheticEmbeddedDeployment | None = None,
    ) -> SyntheticAutopulseFixture:
        """Default local demo: embedded AutoPulse on this app (minimal moving parts)."""
        return cls(
            common=common or SyntheticAutopulseCommon(),
            deployment=embedded or SyntheticEmbeddedDeployment(),
        )

    @classmethod
    def separate_backend(
        cls,
        *,
        ingest_url: str = "http://127.0.0.1:8000/ingest",
        api_key: str | None = None,
        common: SyntheticAutopulseCommon | None = None,
    ) -> SyntheticAutopulseFixture:
        """Point the SDK at a standalone AutoPulse backend (``AUTOPULSE_API_KEY`` in prod)."""
        return cls(
            common=common or SyntheticAutopulseCommon(),
            deployment=SyntheticRemoteDeployment(ingest_url=ingest_url, api_key=api_key),
        )

    @classmethod
    def from_env(cls) -> SyntheticAutopulseFixture:
        """Parse ``AUTOPULSE_*`` variables (same defaults as the former inline block)."""
        mode = os.getenv("AUTOPULSE_MODE", "embedded").strip().lower()
        common = SyntheticAutopulseCommon(
            service_name=os.getenv("AUTOPULSE_SERVICE_NAME", "synthetic-test-api"),
            environment=os.getenv("AUTOPULSE_ENVIRONMENT", "dev"),
            batch_size=_env_int("AUTOPULSE_BATCH_SIZE", 20),
            flush_interval_s=_env_float("AUTOPULSE_FLUSH_INTERVAL_S", 1.0),
            debug=_env_bool("AUTOPULSE_DEBUG"),
        )
        if mode == "remote":
            deployment: SyntheticAutopulseDeployment = SyntheticRemoteDeployment(
                ingest_url=os.getenv("AUTOPULSE_INGEST_URL", "http://127.0.0.1:8000/ingest"),
                api_key=os.getenv("AUTOPULSE_API_KEY"),
            )
        else:
            # Any non-remote ``AUTOPULSE_MODE`` value is treated as embedded (same as before).
            deployment = SyntheticEmbeddedDeployment(
                mount_prefix=os.getenv("AUTOPULSE_MOUNT_PREFIX", "/autopulse"),
                database_url=os.getenv(
                    "AUTOPULSE_DATABASE_URL",
                    "sqlite+aiosqlite:///./autopulse.db",
                ),
                frontend_mode=_env_frontend_mode(),
            )
        return cls(common=common, deployment=deployment)

    def monitor_kwargs(self, *, dashboard_widgets: Sequence[BaseDashboardWidget]) -> dict[str, Any]:
        """Keyword arguments for :func:`autopulse.monitor` (or ``autopulse`` helper)."""
        base: dict[str, Any] = {
            "service_name": self.common.service_name,
            "environment": self.common.environment,
            "batch_size": self.common.batch_size,
            "flush_interval_s": self.common.flush_interval_s,
            "debug": self.common.debug,
            "dashboard_widgets": list(dashboard_widgets),
        }
        dep = self.deployment
        if isinstance(dep, SyntheticEmbeddedDeployment):
            base.update(
                mode="embedded",
                mount_prefix=dep.mount_prefix,
                database_url=dep.database_url,
                frontend_mode=dep.frontend_mode,
            )
        elif isinstance(dep, SyntheticRemoteDeployment):
            base.update(
                mode="remote",
                ingest_url=dep.ingest_url,
                api_key=dep.api_key,
            )
        else:
            assert_never(dep)
        return base
