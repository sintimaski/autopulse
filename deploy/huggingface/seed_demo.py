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
import uuid
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
    *,
    pause_between_chunks: float = 0.0,
) -> int:
    headers = {"Authorization": f"Bearer {api_key}"}
    accepted = 0
    chunk_starts = list(range(0, len(events), _INGEST_CHUNK))
    for index, start in enumerate(chunk_starts):
        chunk = events[start : start + _INGEST_CHUNK]
        response = client.post(
            f"{base_url}/ingest",
            headers=headers,
            json={"sdk_version": "lumonox-demo", "events": chunk},
        )
        response.raise_for_status()
        with contextlib.suppress(Exception):
            accepted += int(response.json().get("accepted", 0))
        # Throttle the backfill burst so it never starves API reads on a small
        # free-tier instance. Without this, a slow first-load /dashboard/auth/session
        # check (racing the write burst) trips the dashboard's "could not reach the
        # server" timeout. The live trickle posts <=2 chunks so it leaves this at 0.
        if pause_between_chunks > 0 and index < len(chunk_starts) - 1:
            time.sleep(pause_between_chunks)
    return accepted


# Hour-of-day rate multipliers (UTC, 24-element lookup, anchored ~UTC business day so
# the curve maps to "9am" / "5pm" peaks for a European service). Models a deep-night
# trough, two clearly visible commute peaks at 09:00 and 17:00 UTC, a small lunch dip,
# and an evening decline. Peaks are intentionally ~1.4× the daytime plateau so they
# survive the existing spike / error-burst noise (~25% jitter) and the morning- and
# evening-rush shape is actually visible on the dashboard's hourly chart.
_HOUR_OF_DAY_MULTIPLIERS: tuple[float, ...] = (
    0.15,
    0.12,
    0.10,
    0.10,
    0.12,
    0.18,  # 00..05 UTC — deep-night trough
    0.32,
    0.55,
    0.90,
    1.30,
    0.95,
    0.72,  # 06..11 UTC — ramp + sharp 09:00 commute peak
    0.68,
    0.75,
    0.80,
    0.85,
    0.95,
    1.30,  # 12..17 UTC — lunch dip, ramp, sharp 17:00 peak
    0.92,
    0.65,
    0.45,
    0.32,
    0.22,
    0.17,  # 18..23 UTC — evening decline back to night
)

# Weekends are noticeably lighter for B2B-shaped traffic; SaaS apps still see weekend
# usage, just less of it. Applied as a flat multiplier on top of the hourly curve.
_WEEKEND_MULTIPLIER: float = 0.55


def _diurnal_multiplier(when: datetime) -> float:
    """Return a 0..1 traffic multiplier for ``when`` (day/night + rush + weekend).

    Linearly interpolates between adjacent hour buckets so the curve is continuous —
    a 600s window straddling 08:55 reads like a real ramp into the 09:00 peak instead
    of jumping at the hour boundary.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    when_utc = when.astimezone(UTC)
    hour_float = when_utc.hour + when_utc.minute / 60.0 + when_utc.second / 3600.0
    lo = int(hour_float) % 24
    hi = (lo + 1) % 24
    frac = hour_float - int(hour_float)
    hourly = _HOUR_OF_DAY_MULTIPLIERS[lo] * (1.0 - frac) + _HOUR_OF_DAY_MULTIPLIERS[hi] * frac
    if when_utc.weekday() >= 5:  # Saturday=5, Sunday=6
        hourly *= _WEEKEND_MULTIPLIER
    return hourly


def _hex32() -> str:
    """32-char lowercase hex — matches the W3C trace_id format the dashboard expects."""
    return uuid.uuid4().hex


def _hex16() -> str:
    """16-char lowercase hex — matches the W3C span_id format."""
    return uuid.uuid4().hex[:16]


def _augment_with_trace_context(
    events: list[dict[str, object]],
    *,
    rng: random.Random,
    child_span_chance: float,
) -> list[dict[str, object]]:
    """Stamp each event with trace_id/span_id and emit correlated downstream spans.

    Most events become single-span traces (one trace, one event). A configurable
    fraction get a downstream "call" span on a *different* service with the same
    ``trace_id`` and ``parent_span_id`` pointing back at the original — so the
    dashboard's Traces page surfaces both trivial and multi-service traces.

    The dashboard's ``/dashboard/traces/*`` SQL reads ``trace_id`` and ``span_name``
    out of the event payload (see ``backend/.../dashboard/routes/traces.py``); the
    backend's ``IngestEvent`` schema accepts them as top-level fields and moves them
    into the payload at persist time.
    """
    out: list[dict[str, object]] = []
    services = list(_SERVICES)
    for ev in events:
        trace_id = _hex32()
        span_id = _hex16()
        method = str(ev.get("method", "GET"))
        path = str(ev.get("path", "/")).split("?", 1)[0]
        parent = dict(ev)
        parent["trace_id"] = trace_id
        parent["span_id"] = span_id
        parent["span_name"] = f"{method} {path}"
        out.append(parent)

        if rng.random() >= child_span_chance:
            continue
        parent_service = str(ev.get("service_name", services[0]))
        downstream = [s for s in services if s != parent_service]
        if not downstream:
            continue
        child = dict(ev)
        child["trace_id"] = trace_id
        child["span_id"] = _hex16()
        child["parent_span_id"] = span_id
        child["service_name"] = rng.choice(downstream)
        child_offset_ms = rng.randint(20, 200)
        ts_raw = str(ev.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts = ts + timedelta(milliseconds=child_offset_ms)
            child["timestamp"] = ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass  # fall back to the parent's timestamp
        # Downstream call is usually faster than the parent (it's only one hop).
        parent_latency = float(ev.get("latency_ms", 100.0))
        child["latency_ms"] = round(max(1.0, parent_latency * rng.uniform(0.35, 0.85)), 2)
        child["span_name"] = f"call {child['service_name']}"
        out.append(child)
    return out


def _generate_window(
    *,
    window_end: datetime,
    duration_seconds: int,
    base_rate_per_second: float,
    rng: random.Random,
    max_events: int,
) -> list[dict[str, object]]:
    from lumonox_backend.ingestion.scenario_events import generate_scenario_events

    # Apply the diurnal curve so traffic looks like a real service: quiet overnight,
    # busy in business hours, with morning and evening commute peaks. Sample the curve
    # at the window's *midpoint* — events fill ``window_end - duration .. window_end``
    # and we want the multiplier to reflect the hour those events actually land in,
    # otherwise a window with ``window_end = 09:00`` (peak) would lift the 08:00 bucket.
    window_midpoint = window_end - timedelta(seconds=duration_seconds / 2)
    effective_rate = max(0.1, base_rate_per_second * _diurnal_multiplier(window_midpoint))
    events, _stats = generate_scenario_events(
        now=window_end,
        duration_seconds=duration_seconds,
        base_rate_per_second=effective_rate,
        rng=rng,
        service_names=_SERVICES,
        environments=_ENVIRONMENTS,
        spike_chance=0.18,
        spike_multiplier=2.6,
        error_burst_chance=0.11,
        max_events=max_events,
    )
    child_chance = max(
        0.0,
        min(1.0, float(os.getenv("LUMONOX_DEMO_TRACE_CHILD_SPAN_CHANCE", "0.4"))),
    )
    return _augment_with_trace_context(events, rng=rng, child_span_chance=child_chance)


# --------------------------------------------------------------------------------------
# --backfill: populate recent history
# --------------------------------------------------------------------------------------
def _run_backfill() -> None:
    _wait_for_health()
    api_key = _load_or_create_raw_key()
    base_url = _api_base()

    hours = max(1, int(os.getenv("LUMONOX_DEMO_BACKFILL_HOURS", "24")))
    chunk_pause = max(0.0, float(os.getenv("LUMONOX_DEMO_BACKFILL_CHUNK_PAUSE_SECONDS", "0.3")))
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
                # Headroom for the rush-hour peaks (multiplier ~1.30 × spike inflation)
                # so the morning + evening surges aren't clipped down to the plateau.
                max_events=3200,
            )
            total += _post_events(
                client, base_url, api_key, events, pause_between_chunks=chunk_pause
            )
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
