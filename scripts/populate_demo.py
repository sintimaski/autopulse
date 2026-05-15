#!/usr/bin/env python3
"""One-shot demo data population: POST 72h of realistic synthetic events to a running backend.

Usage (from repo root, with the backend running):

    uv run scripts/populate_demo.py

Environment overrides:
    LUMONOX_DEMO_API_KEY    Ingest key (required — see backend /settings or bootstrap output)
    LUMONOX_DEMO_API_BASE   Base URL (default: http://127.0.0.1:8000)
    LUMONOX_DEMO_HOURS      Lookback window in hours (default: 72)
    LUMONOX_DEMO_SEED       Random seed for reproducible data (default: 20260514)

Needs the monorepo workspace installed:  uv sync
"""

from __future__ import annotations

import contextlib
import os
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

_SERVICES: tuple[str, ...] = ("checkout-api", "payments-worker", "search-api")
_ENVIRONMENTS: tuple[str, ...] = ("production", "staging")
_INGEST_CHUNK = 250

_HOUR_MULTIPLIERS: tuple[float, ...] = (
    0.15,
    0.12,
    0.10,
    0.10,
    0.12,
    0.18,  # 00-05 UTC
    0.32,
    0.55,
    0.90,
    1.30,
    0.95,
    0.72,  # 06-11 UTC
    0.68,
    0.75,
    0.80,
    0.85,
    0.95,
    1.30,  # 12-17 UTC
    0.92,
    0.65,
    0.45,
    0.32,
    0.22,
    0.17,  # 18-23 UTC
)
_WEEKEND_MULTIPLIER = 0.55


def _api_base() -> str:
    return os.getenv("LUMONOX_DEMO_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _diurnal_multiplier(when: datetime) -> float:
    utc = when.astimezone(UTC)
    h = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    lo, hi = int(h) % 24, (int(h) + 1) % 24
    frac = h - int(h)
    hourly = _HOUR_MULTIPLIERS[lo] * (1.0 - frac) + _HOUR_MULTIPLIERS[hi] * frac
    if utc.weekday() >= 5:
        hourly *= _WEEKEND_MULTIPLIER
    return hourly


def _hex32() -> str:
    return uuid.uuid4().hex


def _hex16() -> str:
    return uuid.uuid4().hex[:16]


def _augment_traces(
    events: list[dict], *, rng: random.Random, child_chance: float = 0.4
) -> list[dict]:
    out: list[dict] = []
    services = list(_SERVICES)
    for ev in events:
        trace_id = _hex32()
        span_id = _hex16()
        method = str(ev.get("method", "GET"))
        path = str(ev.get("path", "/")).split("?", 1)[0]
        parent = {**ev, "trace_id": trace_id, "span_id": span_id, "span_name": f"{method} {path}"}
        out.append(parent)

        if rng.random() >= child_chance:
            continue
        parent_svc = str(ev.get("service_name", services[0]))
        downstream = [s for s in services if s != parent_svc]
        if not downstream:
            continue
        child = {
            **ev,
            "trace_id": trace_id,
            "span_id": _hex16(),
            "parent_span_id": span_id,
            "service_name": rng.choice(downstream),
            "span_name": f"call {rng.choice(downstream)}",
        }
        ts_raw = str(ev.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts += timedelta(milliseconds=rng.randint(20, 200))
            child["timestamp"] = ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
        child["latency_ms"] = round(
            max(1.0, float(ev.get("latency_ms", 100)) * rng.uniform(0.35, 0.85)), 2
        )
        out.append(child)
    return out


def _infra_event(when: datetime, rng: random.Random) -> dict:
    traffic = _diurnal_multiplier(when)
    ts = when.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {
        "type": "request",
        "timestamp": ts,
        "service_name": rng.choice(_SERVICES),
        "environment": rng.choice(_ENVIRONMENTS),
        "method": "GET",
        "path": "/health",
        "status_code": 200,
        "latency_ms": round(rng.uniform(1.0, 8.0), 2),
        "request_id": f"infra-{uuid.uuid4().hex[:12]}",
        "infrastructure_metrics": {
            "host_cpu_percent": round(
                min(95.0, max(5.0, 14.0 + 56.0 * traffic + rng.gauss(0, 4.5))), 2
            ),
            "host_memory_used_percent": round(min(88.0, max(32.0, 56.0 + rng.gauss(0, 4.0))), 2),
            "process_cpu_percent": round(
                min(80.0, max(1.0, 6.0 + 28.0 * traffic + rng.gauss(0, 3.0))), 2
            ),
            "process_memory_percent": round(min(22.0, max(3.0, 11.0 + rng.gauss(0, 2.0))), 2),
            "disk_used_percent": round(min(72.0, max(22.0, 45.0 + rng.gauss(0, 2.5))), 2),
        },
    }


def _generate_window(window_end: datetime, duration_seconds: int, rng: random.Random) -> list[dict]:
    from lumonox_backend.ingestion.scenario_events import generate_scenario_events

    midpoint = window_end - timedelta(seconds=duration_seconds / 2)
    effective_rate = max(0.1, 2.2 * _diurnal_multiplier(midpoint))
    events, _ = generate_scenario_events(
        now=window_end,
        duration_seconds=duration_seconds,
        base_rate_per_second=effective_rate,
        rng=rng,
        service_names=_SERVICES,
        environments=_ENVIRONMENTS,
        spike_chance=0.18,
        spike_multiplier=2.6,
        error_burst_chance=0.11,
        max_events=3200,
    )
    events = _augment_traces(events, rng=rng)
    events.append(_infra_event(midpoint, rng))
    return events


def _wait_for_health(base: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_err = "no response"
    with httpx.Client(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                r = client.get(f"{base}/health")
                if r.status_code == 200:
                    return
                last_err = f"HTTP {r.status_code}"
            except httpx.HTTPError as exc:
                last_err = str(exc)
            time.sleep(1.0)
    raise SystemExit(f"[populate] backend not healthy at {base}/health ({last_err})")


def _post_chunk(client: httpx.Client, base: str, key: str, events: list[dict]) -> int:
    headers = {"Authorization": f"Bearer {key}"}
    accepted = 0
    for start in range(0, len(events), _INGEST_CHUNK):
        chunk = events[start : start + _INGEST_CHUNK]
        r = client.post(
            f"{base}/ingest",
            headers=headers,
            json={"sdk_version": "populate-demo", "events": chunk},
        )
        r.raise_for_status()
        with contextlib.suppress(Exception):
            accepted += int(r.json().get("accepted", 0))
        time.sleep(0.3)
    return accepted


def main() -> int:
    api_key = os.getenv("LUMONOX_DEMO_API_KEY", "").strip()
    if not api_key:
        print(
            "[populate] set LUMONOX_DEMO_API_KEY to your ingest key.\n"
            "  Find it in the backend settings or bootstrap output, e.g.:\n"
            "    export LUMONOX_DEMO_API_KEY=ap_live_...",
            file=sys.stderr,
        )
        return 1

    base = _api_base()
    hours = max(1, int(os.getenv("LUMONOX_DEMO_HOURS", "72")))
    seed = int(os.getenv("LUMONOX_DEMO_SEED", "20260514"))

    print(f"[populate] backend: {base}  window: {hours}h  seed: {seed}")
    _wait_for_health(base)

    rng = random.Random(seed)
    now = datetime.now(tz=UTC)
    window_seconds = 600

    windows: list[datetime] = []
    w = now
    cutoff = now - timedelta(hours=hours)
    while w > cutoff:
        windows.append(w)
        w -= timedelta(seconds=window_seconds)

    total = 0
    errors = 0
    with httpx.Client(timeout=30.0) as client:
        for i, window_end in enumerate(windows):
            events = _generate_window(window_end, window_seconds, rng)
            try:
                accepted = _post_chunk(client, base, api_key, events)
                total += accepted
                errors = 0
                if (i + 1) % 10 == 0 or i == 0:
                    pct = round((i + 1) / len(windows) * 100)
                    print(f"[populate] {pct}%  windows={i + 1}/{len(windows)}  accepted={total}")
            except httpx.HTTPError as exc:
                errors += 1
                print(f"[populate] chunk error: {exc}", file=sys.stderr)
                if errors >= 5:
                    print("[populate] too many errors — aborting", file=sys.stderr)
                    return 1

    print(f"[populate] done — ingested ~{total} events across {hours}h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
