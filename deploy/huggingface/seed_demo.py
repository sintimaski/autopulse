#!/usr/bin/env python3
"""Seed and drive the Lumonox Hugging Face Spaces demo.

Modes (exactly one required):

  --bootstrap  Run DB migrations and idempotently create the demo tenant:
               an organization, a project, a dashboard user + owner membership,
               and an ingest API key. SQLite-only; runs *before* the API starts.

  --backfill   Wait for the API to become healthy, then POST synthetic request /
               error history (last few hours) to /ingest so the dashboard is
               already populated when the first visitor lands.

  --live       Wait for health, then loop forever POSTing a small fresh batch on
               an interval so the demo keeps moving.

The ingest key is generated once and cached at
``$LUMONOX_DATA_DIR/.lumonox/demo_api_key`` so all three modes (separate
processes) agree on the same key. Set ``LUMONOX_DEMO_API_KEY`` to override.

This script depends only on the installed ``lumonox`` package — no monorepo
checkout is needed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

# Synthetic traffic shape: a handful of services across two environments. Kept small
# so the overview stays readable ("five-second understanding" — see the product rules).
_SERVICES: tuple[str, ...] = ("checkout-api", "payments-worker", "search-api")
_ENVIRONMENTS: tuple[str, ...] = ("production", "staging")

# Stay well under the backend's per-batch event cap and request-size limit.
_INGEST_CHUNK = 250


def _port() -> str:
    return os.getenv("LUMONOX_DEMO_PORT", "8000").strip() or "8000"


def _api_base() -> str:
    """Loopback base URL for the in-container API process."""
    return os.getenv("LUMONOX_DEMO_API_BASE", f"http://127.0.0.1:{_port()}").rstrip("/")


def _data_lumonox_dir() -> Path:
    """`.lumonox/` under the configured data root (same anchoring the backend uses)."""
    from lumonox_backend.core.config import resolve_lumonox_data_root

    return resolve_lumonox_data_root() / ".lumonox"


def _key_cache_path() -> Path:
    return _data_lumonox_dir() / "demo_api_key"


def _load_or_create_raw_key() -> str:
    """Resolve the demo ingest key: env override → cached file → freshly generated."""
    from lumonox_backend.auth.api_keys import generate_api_key

    override = (os.getenv("LUMONOX_DEMO_API_KEY") or "").strip()
    if override:
        return override

    cache_path = _key_cache_path()
    if cache_path.is_file():
        cached = cache_path.read_text(encoding="utf-8").strip()
        if cached:
            return cached

    raw_key, _key_id, _salt, _hash = generate_api_key()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(raw_key, encoding="utf-8")
    os.chmod(cache_path, 0o600)
    return raw_key


def _ensure_data_dirs() -> None:
    lumonox_dir = _data_lumonox_dir()
    (lumonox_dir / "emails").mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------------------
# --bootstrap: migrations + demo tenant
# --------------------------------------------------------------------------------------
async def _bootstrap_tenant() -> None:
    """Idempotently create the org / project / user / membership / ingest key."""
    from sqlalchemy import select

    from lumonox_backend.auth.api_keys import build_api_key_record
    from lumonox_backend.database import write_session
    from lumonox_backend.models import (
        ApiKey,
        DashboardUser,
        Organization,
        OrganizationMembership,
        Project,
    )

    email = (
        os.getenv("LUMONOX_DEMO_EMAIL", "demo@lumonox.dev").strip() or "demo@lumonox.dev"
    ).lower()
    org_name = "Lumonox Demo"
    project_name = "Demo Project"

    raw_key = _load_or_create_raw_key()
    key_record = build_api_key_record(raw_key)
    if key_record is None:
        raise SystemExit(
            "[seed] LUMONOX_DEMO_API_KEY is not a valid ingest key (expected ap_live_<id>_<secret>)"
        )
    key_id, key_salt, key_hash = key_record

    async with write_session() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.name == org_name)
        )
        if organization is None:
            organization = Organization(name=org_name)
            session.add(organization)
            await session.flush()

        project = await session.scalar(
            select(Project)
            .where(Project.organization_id == organization.id)
            .order_by(Project.created_at.asc())
        )
        if project is None:
            project = Project(
                name=project_name,
                organization_id=organization.id,
                onboarding_completed=True,
            )
            session.add(project)
            await session.flush()

        user = await session.scalar(select(DashboardUser).where(DashboardUser.email == email))
        if user is None:
            user = DashboardUser(email=email)
            session.add(user)
            await session.flush()

        membership = await session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.user_id == user.id,
            )
        )
        if membership is None:
            session.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role="owner",
                    invited_email=email,
                )
            )

        existing_key = await session.scalar(select(ApiKey).where(ApiKey.key_id == key_id))
        if existing_key is None:
            session.add(
                ApiKey(
                    project_id=project.id,
                    key_id=key_id,
                    key_salt=key_salt,
                    key_hash=key_hash,
                )
            )

        await session.commit()

    print(
        f"[seed] tenant ready — organization={org_name!r} project={project_name!r} "
        f"sign-in email={email!r}"
    )


def _run_bootstrap() -> None:
    from lumonox_backend.database import upgrade_to_head

    _ensure_data_dirs()
    print("[seed] running database migrations…")
    upgrade_to_head()
    asyncio.run(_bootstrap_tenant())


# --------------------------------------------------------------------------------------
# Traffic helpers (shared by --backfill and --live)
# --------------------------------------------------------------------------------------
def _wait_for_health(timeout_seconds: float = 150.0) -> None:
    base = _api_base()
    deadline = time.monotonic() + timeout_seconds
    last_error: str = "no response"
    with httpx.Client(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"{base}/health")
                if response.status_code == 200:
                    return
                last_error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.0)
    raise SystemExit(f"[seed] API never became healthy at {base}/health ({last_error})")


def _post_events(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    events: list[dict[str, object]],
) -> int:
    headers = {"Authorization": f"Bearer {api_key}"}
    accepted = 0
    for start in range(0, len(events), _INGEST_CHUNK):
        chunk = events[start : start + _INGEST_CHUNK]
        response = client.post(
            f"{base_url}/ingest",
            headers=headers,
            json={"sdk_version": "lumonox-demo", "events": chunk},
        )
        response.raise_for_status()
        with contextlib.suppress(Exception):
            accepted += int(response.json().get("accepted", 0))
    return accepted


def _generate_window(
    *,
    window_end: datetime,
    duration_seconds: int,
    base_rate_per_second: float,
    rng: random.Random,
    max_events: int,
) -> list[dict[str, object]]:
    from lumonox_backend.ingestion.scenario_events import generate_scenario_events

    events, _stats = generate_scenario_events(
        now=window_end,
        duration_seconds=duration_seconds,
        base_rate_per_second=base_rate_per_second,
        rng=rng,
        service_names=_SERVICES,
        environments=_ENVIRONMENTS,
        spike_chance=0.18,
        spike_multiplier=2.6,
        error_burst_chance=0.11,
        max_events=max_events,
    )
    return events


# --------------------------------------------------------------------------------------
# --backfill: populate recent history
# --------------------------------------------------------------------------------------
def _run_backfill() -> None:
    _wait_for_health()
    api_key = _load_or_create_raw_key()
    base_url = _api_base()

    hours = max(1, int(os.getenv("LUMONOX_DEMO_BACKFILL_HOURS", "4")))
    window_seconds = 600  # contiguous 10-minute windows, no gaps
    rng = random.Random(20260514)
    now = datetime.now(tz=UTC)
    window_end = now - timedelta(hours=hours) + timedelta(seconds=window_seconds)

    total = 0
    with httpx.Client(timeout=30.0) as client:
        while window_end <= now:
            events = _generate_window(
                window_end=window_end,
                duration_seconds=window_seconds,
                base_rate_per_second=2.2,
                rng=rng,
                max_events=1600,
            )
            total += _post_events(client, base_url, api_key, events)
            window_end += timedelta(seconds=window_seconds)

    print(f"[seed] backfilled ~{total} events across the last {hours}h")


# --------------------------------------------------------------------------------------
# --live: keep the demo moving
# --------------------------------------------------------------------------------------
def _run_live() -> None:
    _wait_for_health()
    api_key = _load_or_create_raw_key()
    base_url = _api_base()
    interval = max(5.0, float(os.getenv("LUMONOX_DEMO_LIVE_INTERVAL_SECONDS", "25")))
    rng = random.Random()

    print(f"[seed] live traffic trickle started (every {interval:.0f}s)")
    with httpx.Client(timeout=20.0) as client:
        while True:
            events = _generate_window(
                window_end=datetime.now(tz=UTC),
                duration_seconds=int(interval),
                base_rate_per_second=3.0,
                rng=rng,
                max_events=400,
            )
            try:
                _post_events(client, base_url, api_key, events)
            except httpx.HTTPError as exc:
                print(f"[seed] live batch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--bootstrap", action="store_true", help="migrations + demo tenant")
    mode.add_argument("--backfill", action="store_true", help="POST recent synthetic history")
    mode.add_argument("--live", action="store_true", help="loop POSTing fresh batches")
    args = parser.parse_args()

    if args.bootstrap:
        _run_bootstrap()
    elif args.backfill:
        _run_backfill()
    elif args.live:
        _run_live()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
