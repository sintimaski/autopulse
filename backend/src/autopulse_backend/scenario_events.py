from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class ScenarioGenerationStats:
    generated_events: int
    spike_windows: int
    error_burst_windows: int


_ROUTE_FAMILIES: tuple[dict[str, object], ...] = (
    {"name": "health", "weight": 4, "method": "GET", "path_fn": lambda rng: "/health"},
    {
        "name": "search",
        "weight": 6,
        "method": "GET",
        "path_fn": lambda rng: f"/search?q=item-{rng.randint(1, 20)}",
    },
    {
        "name": "orders-read",
        "weight": 8,
        "method": "GET",
        "path_fn": lambda rng: f"/orders/{rng.randint(1, 800)}",
    },
    {
        "name": "orders-create",
        "weight": 4,
        "method": "POST",
        "path_fn": lambda rng: "/orders",
    },
    {
        "name": "orders-update",
        "weight": 3,
        "method": "PATCH",
        "path_fn": lambda rng: f"/orders/{rng.randint(1, 800)}",
    },
    {
        "name": "auth-login",
        "weight": 2,
        "method": "POST",
        "path_fn": lambda rng: "/auth/login",
    },
    {
        "name": "reports",
        "weight": 2,
        "method": "GET",
        "path_fn": lambda rng: "/reports/daily",
    },
    {
        "name": "missing",
        "weight": 2,
        "method": "GET",
        "path_fn": lambda rng: "/missing-route",
    },
    {"name": "boom", "weight": 1, "method": "GET", "path_fn": lambda rng: "/boom"},
)


def split_csv_values(raw: str) -> tuple[str, ...]:
    return tuple(piece.strip() for piece in raw.split(",") if piece.strip())


def _weighted_routes() -> list[dict[str, object]]:
    weighted: list[dict[str, object]] = []
    for family in _ROUTE_FAMILIES:
        weighted.extend([family] * int(family["weight"]))
    return weighted


_WEIGHTED_ROUTES = _weighted_routes()


def _status_code_for_family(name: str, *, rng: random.Random, error_boost: float) -> int:
    roll = rng.random()
    if name == "missing":
        return 404
    if name == "boom":
        return 500 if roll < 0.7 + error_boost * 0.25 else 502
    if name == "orders-create":
        if roll < 0.75:
            return 201
        if roll < 0.92:
            return 400
        return 503 if rng.random() < 0.4 + error_boost * 0.4 else 500
    if name == "auth-login":
        if roll < 0.58:
            return 200
        if roll < 0.9:
            return 401
        return 500 if rng.random() < 0.45 + error_boost * 0.4 else 502
    if name == "orders-update":
        if roll < 0.78:
            return 200
        if roll < 0.93:
            return 409
        return 500 if rng.random() < 0.4 + error_boost * 0.35 else 502
    if name == "reports":
        if roll < 0.84:
            return 200
        if roll < 0.94:
            return 504
        return 500
    if name == "search":
        if roll < 0.9:
            return 200
        if roll < 0.97:
            return 429
        return 500
    if name == "orders-read":
        if roll < 0.86:
            return 200
        if roll < 0.95:
            return 404
        return 500
    if roll < 0.96:
        return 200
    return 503


def _latency_for_status(status_code: int, *, rng: random.Random) -> float:
    if status_code >= 500:
        base = rng.uniform(120.0, 480.0)
        jitter = rng.uniform(0.85, 1.6)
    elif status_code >= 400:
        base = rng.uniform(35.0, 120.0)
        jitter = rng.uniform(0.7, 1.3)
    else:
        base = rng.uniform(8.0, 95.0)
        jitter = rng.uniform(0.65, 1.4)
    return round(base * jitter, 2)


def _error_payload(*, path: str, status_code: int, request_id: str) -> dict[str, str]:
    exc_type = "ScenarioTrafficError"
    exc_msg = f"Synthetic {status_code} while serving {path} ({request_id})"
    stack = (
        "Traceback (scenario):\n"
        f'  File "/app/handlers.py", line 88, in handle\n'
        f"  RuntimeError: {exc_msg}\n"
    )
    digest = hashlib.sha256()
    digest.update(exc_type.encode("utf-8"))
    digest.update(b"|")
    digest.update(exc_msg.encode("utf-8"))
    digest.update(b"|")
    digest.update(stack.encode("utf-8"))
    return {
        "exception_type": exc_type,
        "exception_message": exc_msg,
        "stack_trace": stack,
        "error_hash": digest.hexdigest(),
    }


def _build_event(
    *,
    rng: random.Random,
    timestamp: datetime,
    service_name: str,
    environment: str,
    request_id: str,
    error_boost: float,
) -> dict[str, object]:
    route = rng.choice(_WEIGHTED_ROUTES)
    route_name = str(route["name"])
    method = str(route["method"])
    path_fn = route["path_fn"]
    path = str(path_fn(rng)) if callable(path_fn) else "/unknown"
    status_code = _status_code_for_family(route_name, rng=rng, error_boost=error_boost)
    event_type = "error" if status_code >= 500 else "request"
    event: dict[str, object] = {
        "type": event_type,
        "timestamp": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "service_name": service_name,
        "environment": environment,
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": _latency_for_status(status_code, rng=rng),
        "request_id": request_id,
    }
    if event_type == "error":
        event.update(_error_payload(path=path, status_code=status_code, request_id=request_id))
    return event


def generate_manual_batch_events(
    *,
    now: datetime,
    batch_index: int,
    batch_size: int,
    rng: random.Random,
    service_names: tuple[str, ...],
    environments: tuple[str, ...],
    lookback_seconds: int = 25,
    spike_chance: float = 0.2,
    spike_multiplier: float = 2.4,
) -> tuple[list[dict[str, object]], ScenarioGenerationStats]:
    effective_batch_size = max(1, batch_size)
    spike_windows = 0
    if rng.random() < spike_chance:
        effective_batch_size = max(
            batch_size + 1,
            int(round(batch_size * max(1.0, spike_multiplier))),
        )
        spike_windows = 1

    events: list[dict[str, object]] = []
    run_prefix = f"manual-{batch_index:06d}"
    for event_index in range(effective_batch_size):
        service_name = rng.choice(service_names)
        environment = rng.choice(environments)
        timestamp = now - timedelta(seconds=rng.uniform(0.0, max(2, lookback_seconds)))
        request_id = f"{run_prefix}-{event_index + 1:04d}"
        events.append(
            _build_event(
                rng=rng,
                timestamp=timestamp,
                service_name=service_name,
                environment=environment,
                request_id=request_id,
                error_boost=0.0,
            )
        )

    stats = ScenarioGenerationStats(
        generated_events=len(events),
        spike_windows=spike_windows,
        error_burst_windows=0,
    )
    return (events, stats)


def generate_scenario_events(
    *,
    now: datetime,
    duration_seconds: int,
    base_rate_per_second: float,
    rng: random.Random,
    service_names: tuple[str, ...],
    environments: tuple[str, ...],
    spike_chance: float,
    spike_multiplier: float,
    error_burst_chance: float,
    max_events: int,
) -> tuple[list[dict[str, object]], ScenarioGenerationStats]:
    events: list[dict[str, object]] = []
    spike_windows = 0
    error_burst_windows = 0
    spike_seconds_remaining = 0
    error_burst_seconds_remaining = 0
    request_seq = 0
    run_prefix = now.strftime("scenario-%Y%m%d%H%M%S")

    for elapsed_second in range(duration_seconds, 0, -1):
        if len(events) >= max_events:
            break

        if spike_seconds_remaining <= 0 and rng.random() < spike_chance:
            spike_seconds_remaining = rng.randint(2, 6)
            spike_windows += 1
        if error_burst_seconds_remaining <= 0 and rng.random() < error_burst_chance:
            error_burst_seconds_remaining = rng.randint(2, 5)
            error_burst_windows += 1

        rate = max(0.1, base_rate_per_second)
        if spike_seconds_remaining > 0:
            rate *= max(1.0, spike_multiplier)
            spike_seconds_remaining -= 1
        if error_burst_seconds_remaining > 0:
            error_burst_seconds_remaining -= 1
        error_boost = 0.45 if error_burst_seconds_remaining > 0 else 0.0

        jittered_rate = max(0.1, rate * rng.uniform(0.65, 1.45))
        events_this_second = max(0, int(round(jittered_rate + rng.random() * 0.8)))
        for _ in range(events_this_second):
            if len(events) >= max_events:
                break
            request_seq += 1
            timestamp = now - timedelta(seconds=elapsed_second - rng.random())
            service_name = rng.choice(service_names)
            environment = rng.choice(environments)
            request_id = f"{run_prefix}-{request_seq:07d}"
            events.append(
                _build_event(
                    rng=rng,
                    timestamp=timestamp,
                    service_name=service_name,
                    environment=environment,
                    request_id=request_id,
                    error_boost=error_boost,
                )
            )

    events.sort(key=lambda item: str(item.get("timestamp", "")))
    stats = ScenarioGenerationStats(
        generated_events=len(events),
        spike_windows=spike_windows,
        error_burst_windows=error_burst_windows,
    )
    return events, stats
