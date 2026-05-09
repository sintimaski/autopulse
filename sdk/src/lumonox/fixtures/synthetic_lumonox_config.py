"""Typed Lumonox wiring for the synthetic FastAPI fixture.

Use this instead of ad-hoc ``os.getenv`` blocks in ``synthetic_test_app``.

**Deployment**

Events go to a standalone Lumonox backend (typical local ``uvicorn`` on :8000).
See ``scripts/run_synthetic_stack.sh`` and ``scripts/run_remote_stack.sh``.

Environment loading mirrors the variables documented in ``fixtures/README.md``.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from lumonox.widgets import BaseDashboardWidget


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


@dataclass(frozen=True, slots=True)
class SyntheticLumonoxCommon:
    """Fields shared by monitoring presets."""

    service_name: str = "synthetic-test-api"
    environment: str = "dev"
    batch_size: int = 20
    flush_interval_s: float = 1.0
    debug: bool = False


@dataclass(frozen=True, slots=True)
class SyntheticRemoteDeployment:
    """Events go to another Lumonox stack (typical local ``uvicorn`` on :8000)."""

    ingest_url: str = "http://127.0.0.1:8000/ingest"
    api_key: str | None = None


@dataclass(frozen=True, slots=True)
class SyntheticLumonoxFixture:
    """Complete monitor options for ``synthetic_test_app`` (factories or ``from_env``)."""

    common: SyntheticLumonoxCommon
    deployment: SyntheticRemoteDeployment

    @classmethod
    def separate_backend(
        cls,
        *,
        ingest_url: str = "http://127.0.0.1:8000/ingest",
        api_key: str | None = None,
        common: SyntheticLumonoxCommon | None = None,
    ) -> SyntheticLumonoxFixture:
        """Point the SDK at a standalone Lumonox backend (``LUMONOX_API_KEY`` in prod)."""
        return cls(
            common=common or SyntheticLumonoxCommon(),
            deployment=SyntheticRemoteDeployment(ingest_url=ingest_url, api_key=api_key),
        )

    @classmethod
    def from_env(cls) -> SyntheticLumonoxFixture:
        """Parse ``LUMONOX_*`` variables (remote ingest defaults)."""
        common = SyntheticLumonoxCommon(
            service_name=os.getenv("LUMONOX_SERVICE_NAME", "synthetic-test-api"),
            environment=os.getenv("LUMONOX_ENVIRONMENT", "dev"),
            batch_size=_env_int("LUMONOX_BATCH_SIZE", 20),
            flush_interval_s=_env_float("LUMONOX_FLUSH_INTERVAL_S", 1.0),
            debug=_env_bool("LUMONOX_DEBUG"),
        )
        deployment = SyntheticRemoteDeployment(
            ingest_url=os.getenv("LUMONOX_INGEST_URL", "http://127.0.0.1:8000/ingest"),
            api_key=os.getenv("LUMONOX_API_KEY"),
        )
        return cls(common=common, deployment=deployment)

    def monitor_kwargs(self, *, dashboard_widgets: Sequence[BaseDashboardWidget]) -> dict[str, Any]:
        """Keyword arguments for :func:`lumonox.monitor` (or ``lumonox`` helper)."""
        dep = self.deployment
        return {
            "service_name": self.common.service_name,
            "environment": self.common.environment,
            "batch_size": self.common.batch_size,
            "flush_interval_s": self.common.flush_interval_s,
            "debug": self.common.debug,
            "dashboard_widgets": list(dashboard_widgets),
            "mode": "remote",
            "ingest_url": dep.ingest_url,
            "api_key": dep.api_key,
        }
