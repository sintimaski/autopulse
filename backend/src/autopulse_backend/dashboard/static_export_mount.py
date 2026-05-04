"""Optional dashboard static export mount (no-op unless extended for local builds)."""

from __future__ import annotations

from typing import Any

from autopulse_backend.core.config import Settings


def maybe_mount_dashboard_static_export(
    app: Any,
    settings: Settings,
    *,
    for_submount: bool = False,
) -> None:
    """Hook for serving a pre-built Next export from the API process.

    The embedded SDK mounts UI via ``autopulse._embedded``; standalone backend
    deployments typically serve the dashboard from a separate Next host. This
    stub keeps imports stable until a static-export path is wired here.
    """
    del app, settings, for_submount
