from __future__ import annotations

import argparse
import math
import random
import signal
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

_KEEP_RUNNING = True
RoleMode = Literal["viewer", "editor", "admin", "mixed"]
Scenario = Literal["steady", "realistic"]
ErrorTag = Literal["auth", "validation", "upstream", "timeout", "not_found", "server"]


@dataclass(frozen=True, slots=True)
class RequestSpec:
    name: str
    method: str
    path_template: str
    weight: int
    error_tags: tuple[ErrorTag, ...] = ()


_REQUEST_SPECS: tuple[RequestSpec, ...] = (
    RequestSpec("health", "GET", "/health", 5),
    RequestSpec("users-read", "GET", "/users/{user_id}", 7, ("auth", "not_found")),
    RequestSpec("users-create", "POST", "/users", 2, ("validation", "auth")),
    RequestSpec("users-patch", "PATCH", "/users/{user_id}", 2, ("validation", "not_found")),
    RequestSpec(
        "users-delete", "DELETE", "/users/{user_id}", 1, ("auth", "validation", "not_found")
    ),
    RequestSpec("orders-read", "GET", "/orders/{order_id}", 6, ("auth", "not_found")),
    RequestSpec("orders-create", "POST", "/orders", 3, ("validation", "upstream")),
    RequestSpec("search", "GET", "/search", 6, ("auth",)),
    RequestSpec("auth-login", "POST", "/auth/login", 2, ("auth",)),
    RequestSpec("reports", "GET", "/reports/daily", 1, ("auth", "timeout")),
    RequestSpec("inventory", "GET", "/inventory/{sku}", 6, ("upstream", "not_found")),
    RequestSpec("payments", "POST", "/payments/intents", 3, ("validation",)),
    RequestSpec(
        "dispatch", "POST", "/integrations/dispatch", 2, ("auth", "validation", "upstream")
    ),
    RequestSpec("analytics", "GET", "/analytics/summary", 5, ("server",)),
    RequestSpec("quote", "GET", "/upstream/quote", 5, ("upstream",)),
    RequestSpec("quota", "GET", "/quota/status", 3, ("validation",)),
    RequestSpec("checkout-preview", "GET", "/checkout/preview", 5, ("timeout",)),
    RequestSpec("feedback", "POST", "/feedback", 3, ("validation",)),
    RequestSpec("errors-key", "GET", "/errors/key-missing", 1, ("server",)),
    RequestSpec("errors-type", "GET", "/errors/type-mismatch", 1, ("server",)),
    RequestSpec("errors-deadline", "GET", "/errors/deadline", 1, ("timeout", "server")),
    RequestSpec("boom", "GET", "/boom", 1, ("server", "auth")),
)


def _handle_stop_signal(_signum: int, _frame: object) -> None:
    global _KEEP_RUNNING
    _KEEP_RUNNING = False


def _weighted_specs() -> list[RequestSpec]:
    weighted: list[RequestSpec] = []
    for spec in _REQUEST_SPECS:
        weighted.extend([spec] * spec.weight)
    return weighted


_ERROR_BURST_NAMES = frozenset(
    {
        "boom",
        "errors-key",
        "errors-type",
        "errors-deadline",
        "payments",
        "inventory",
        "dispatch",
        "checkout-preview",
        "users-delete",
        "orders-create",
        "users-read",
        "orders-read",
        "reports",
        "quota",
        "quote",
    },
)


def _generated_burst_targets(
    weighted_specs: list[RequestSpec],
    *,
    rng: random.Random,
) -> frozenset[str]:
    plans: tuple[tuple[ErrorTag, ...], ...] = (
        ("server", "timeout"),
        ("auth", "validation"),
        ("upstream", "not_found"),
        ("server", "upstream", "auth"),
        ("validation", "timeout"),
    )
    selected_plan = rng.choice(plans)
    names: set[str] = set()
    for spec in weighted_specs:
        if not spec.error_tags:
            continue
        if any(tag in selected_plan for tag in spec.error_tags) and rng.random() < 0.72:
            names.add(spec.name)
    # Keep at least a few generated targets so bursts are visible.
    if len(names) < 4:
        fallback = [spec.name for spec in weighted_specs if spec.name in _ERROR_BURST_NAMES]
        if fallback:
            names.update(rng.sample(fallback, k=min(4, len(fallback))))
    return frozenset(names)


def _burst_biased_pool(
    base: list[RequestSpec],
    *,
    in_error_burst: bool,
    rng: random.Random,
    burst_targets: frozenset[str],
) -> list[RequestSpec]:
    if not in_error_burst:
        return base
    extra: list[RequestSpec] = []
    for spec in base:
        if spec.name in burst_targets and rng.random() < 0.5:
            extra.extend([spec] * rng.randint(1, 2))
    return base + extra


def _resolve_role(mode: RoleMode, *, rng: random.Random) -> str:
    if mode != "mixed":
        return mode
    return rng.choice(["viewer", "editor", "admin"])


def _auth_headers(role: str, *, request_id: str) -> dict[str, str]:
    return {
        "x-request-id": request_id,
        "x-auth-token": f"demo:{role}:{role}-bot",
    }


def _pick_sku(rng: random.Random) -> str:
    if rng.random() < 0.72:
        return rng.choice(["SKU-100", "SKU-200", "SKU-RETIRED"])
    return f"SKU-{rng.randint(400, 999)}"


def _realistic_rps_curve(elapsed_seconds: int) -> float:
    """Deterministic diurnal-ish shape: quiet valleys and busy plateaus (no wall-clock)."""
    t = elapsed_seconds % 120
    # two peaks per 120s window
    peak1 = math.exp(-((t - 22) ** 2) / 180.0)
    peak2 = math.exp(-((t - 78) ** 2) / 200.0)
    return 0.52 + 0.95 * max(peak1, peak2)


def _request_payload(
    *,
    spec: RequestSpec,
    rng: random.Random,
    request_id: str,
    request_index: int,
    error_burst: bool,
    role_mode: RoleMode,
) -> tuple[str, str, dict[str, Any], dict[str, str]]:
    role = _resolve_role(role_mode, rng=rng)
    headers = _auth_headers(role, request_id=request_id)
    params: dict[str, Any] = {}
    body: dict[str, Any] = {}
    user_id = rng.randint(1, 30)
    order_id = rng.randint(1000, 1100)
    sku = _pick_sku(rng)

    if error_burst:
        if spec.name == "users-read":
            roll = rng.random()
            if roll < 0.18:
                headers = {"x-request-id": request_id}
            elif roll < 0.32:
                headers = {"x-request-id": request_id, "Authorization": "Bearer expired"}
            elif roll < 0.55:
                user_id = rng.choice([404, 9_999, 50_001])
        elif spec.name == "orders-read":
            order_roll = rng.random()
            if order_roll < 0.22:
                headers = {"x-request-id": request_id, "Authorization": "Bearer expired"}
            elif order_roll < 0.52:
                order_id = rng.choice([7_001, 8_888, 12_345])
        elif spec.name == "search" and rng.random() < 0.18:
            headers = {"x-request-id": request_id}
        elif (
            spec.name in {"users-patch", "orders-create", "reports", "dispatch"}
            and rng.random() < 0.32
        ):
            headers["x-auth-token"] = "demo:viewer:viewer-forbidden"
        elif spec.name == "users-patch" and rng.random() < 0.48:
            user_id = rng.choice([404, 99_999])
        elif spec.name == "inventory" and rng.random() < 0.55:
            sku = f"UNKNOWN-{rng.randint(1, 9999)}"
        elif spec.name == "dispatch" and rng.random() < 0.5:
            headers["x-integration-secret"] = "wrong-secret"
        elif spec.name.startswith("errors-") and rng.random() < 0.2:
            headers = {"x-request-id": request_id}

    path = spec.path_template.format(user_id=user_id, order_id=order_id, sku=sku)

    if spec.name == "users-create":
        suffix = request_index % 100_000
        body = {
            "email": f"user-{suffix}@example.com",
            "display_name": f"User {suffix}",
            "role": rng.choice(["viewer", "editor"]),
        }
        if error_burst:
            choice = rng.random()
            if choice < 0.26:
                body["email"] = "bad-email"
            elif choice < 0.5:
                body["email"] = f"blocked-{suffix}@blocked.example"
    elif spec.name == "users-patch":
        body = {
            "display_name": f"Patch {request_index}",
            "version": rng.randint(0, 4),
        }
        if error_burst and rng.random() < 0.42:
            params["force_conflict"] = "true"
    elif spec.name == "orders-create":
        body = {
            "user_id": user_id,
            "amount_cents": rng.randint(120, 9_999),
            "item": f"item-{rng.randint(1, 300)}",
        }
        if error_burst and rng.random() < 0.42:
            params["force_unavailable"] = "true"
    elif spec.name == "search":
        params["q"] = f"q-{rng.randint(1, 50)}"
    elif spec.name == "auth-login":
        chosen_role = rng.choice(["viewer", "editor", "admin"])
        body = {"username": f"{chosen_role}@example.com", "password": "demo-pass"}
        headers = {"x-request-id": request_id}
        if error_burst and rng.random() < 0.42:
            body["password"] = "wrong-pass"  # nosec B105
    elif spec.name == "reports":
        if error_burst and rng.random() < 0.42:
            params["force_timeout"] = "true"
    elif spec.name == "boom":
        if error_burst and role_mode == "mixed" and rng.random() < 0.28:
            headers["x-auth-token"] = "demo:viewer:viewer-boom"
        else:
            headers["x-auth-token"] = "demo:admin:admin-bot"
    elif spec.name == "payments":
        amt = rng.randint(199, 24_999)
        if error_burst and rng.random() < 0.38:
            amt = rng.choice([5, 12, 25])
        body = {"amount_cents": amt, "currency": "usd"}
    elif spec.name == "dispatch":
        body = {
            "event_type": f"order.{rng.choice(['placed', 'shipped', 'cancelled'])}",
            "payload": {"id": str(rng.randint(1, 50_000))},
        }
        headers.setdefault("x-integration-secret", "synthetic-secret")
        if error_burst and rng.random() < 0.25:
            body["event_type"] = ""
    elif spec.name == "quote":
        path = "/upstream/quote"
        params["symbol"] = rng.choice(["SYNTH", "ACME", "EDGE", "VOID"])
    elif spec.name == "checkout-preview":
        path = "/checkout/preview"
        params["items"] = rng.randint(1, 24)
        if error_burst and rng.random() < 0.35:
            params["force_timeout"] = "true"
    elif spec.name == "feedback":
        body = {"rating": rng.randint(1, 5), "comment": None}
        if error_burst and rng.random() < 0.4:
            body["rating"] = rng.choice([0, 6, 10, -1])
    elif spec.name == "users-delete":
        if error_burst and rng.random() < 0.42:
            headers["x-auth-token"] = "demo:viewer:viewer-del"
            user_id = rng.choice([1, 2, 3, 404])
        elif error_burst and rng.random() < 0.55:
            headers["x-auth-token"] = "demo:admin:admin-bot"
            user_id = rng.choice([2, 3])
        else:
            headers["x-auth-token"] = "demo:admin:admin-bot"
            user_id = rng.choice([1, 4, 5, 6, 7, 8, 404, 902])
        path = spec.path_template.format(user_id=user_id, order_id=order_id, sku=sku)

    return path, spec.method, {"params": params, "json": body}, headers


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic traffic for the SDK test app.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=None,
        help="Preferred run interval in minutes (takes precedence over --duration-seconds).",
    )
    parser.add_argument("--rps", type=int, default=6)
    parser.add_argument(
        "--target-requests",
        type=int,
        default=200,
        help="Total requests to generate during the selected run interval.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--role-mode",
        choices=["viewer", "editor", "admin", "mixed"],
        default="mixed",
    )
    parser.add_argument(
        "--scenario",
        choices=["steady", "realistic"],
        default="steady",
        help="steady: fixed tick; realistic: diurnal-ish RPS curve + tick jitter",
    )
    parser.add_argument(
        "--tick-jitter",
        type=float,
        default=0.18,
        help="plus/minus fraction of 1s sleep (realistic scenario)",
    )
    parser.add_argument("--spike-interval-seconds", type=int, default=20)
    parser.add_argument("--spike-multiplier", type=float, default=2.8)
    parser.add_argument("--error-burst-interval-seconds", type=int, default=25)
    parser.add_argument("--error-burst-duration-seconds", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    args = parser.parse_args()

    duration_seconds = args.duration_seconds
    if args.duration_minutes is not None:
        duration_seconds = max(1, int(round(args.duration_minutes * 60)))

    # Keep the generator in "target mode" by default: ~200 requests over chosen interval.
    if args.target_requests > 0:
        computed_rps = max(1, math.ceil(args.target_requests / max(1, duration_seconds)))
    else:
        computed_rps = args.rps

    if args.duration_minutes is None and args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be > 0")
    if duration_seconds <= 0:
        raise SystemExit("duration must be > 0")
    if args.rps <= 0:
        raise SystemExit("--rps must be > 0")
    if args.target_requests < 0:
        raise SystemExit("--target-requests must be >= 0")
    if args.spike_interval_seconds <= 0:
        raise SystemExit("--spike-interval-seconds must be > 0")
    if args.spike_multiplier < 1.0:
        raise SystemExit("--spike-multiplier must be >= 1.0")
    if args.error_burst_interval_seconds <= 0:
        raise SystemExit("--error-burst-interval-seconds must be > 0")
    if args.error_burst_duration_seconds <= 0:
        raise SystemExit("--error-burst-duration-seconds must be > 0")
    if not 0.0 <= args.tick_jitter <= 0.45:
        raise SystemExit("--tick-jitter must be between 0 and 0.45")

    signal.signal(signal.SIGINT, _handle_stop_signal)
    signal.signal(signal.SIGTERM, _handle_stop_signal)

    base_url = args.base_url.rstrip("/")
    weighted = _weighted_specs()
    rng = random.Random(args.seed)  # nosec B311 - deterministic fixture traffic
    status_counts: dict[int, int] = {}
    route_counts: dict[str, int] = {}
    failures = 0
    transport_errors = 0
    total_requests = 0
    start_time = time.monotonic()
    tick = 0
    burst_targets = _generated_burst_targets(weighted, rng=rng)

    print("synthetic_load: starting")
    print(f"- base_url: {base_url}")
    print(f"- duration_seconds: {duration_seconds}")
    print(f"- target_requests: {args.target_requests}")
    print(f"- computed_rps: {computed_rps}")
    print(f"- role_mode: {args.role_mode}")
    print(f"- scenario: {args.scenario}")
    print(f"- seed: {args.seed}")
    print(f"- burst_targets: {sorted(burst_targets)}")

    with httpx.Client(timeout=args.timeout_seconds) as client:
        end_time = start_time + duration_seconds
        while _KEEP_RUNNING and time.monotonic() < end_time:
            if args.target_requests > 0 and total_requests >= args.target_requests:
                break
            tick += 1
            elapsed_seconds = int(time.monotonic() - start_time)
            in_spike = elapsed_seconds > 0 and elapsed_seconds % args.spike_interval_seconds == 0
            in_error_burst = (
                elapsed_seconds > 0
                and elapsed_seconds % args.error_burst_interval_seconds
                < args.error_burst_duration_seconds
            )
            pool = _burst_biased_pool(
                weighted,
                in_error_burst=in_error_burst,
                rng=rng,
                burst_targets=burst_targets,
            )

            curve = 1.0 if args.scenario == "steady" else _realistic_rps_curve(elapsed_seconds)
            current_rps = max(1, int(round(computed_rps * curve)))
            if in_spike:
                current_rps = max(1, int(round(current_rps * args.spike_multiplier)))
            if args.target_requests > 0:
                remaining = max(0, args.target_requests - total_requests)
                current_rps = min(current_rps, remaining)
                if current_rps == 0:
                    break

            for req_index in range(current_rps):
                spec = rng.choice(pool)
                total_requests += 1
                request_id = f"load-{tick:05d}-{req_index:03d}"
                path, method, payload, headers = _request_payload(
                    spec=spec,
                    rng=rng,
                    request_id=request_id,
                    request_index=total_requests,
                    error_burst=in_error_burst,
                    role_mode=args.role_mode,
                )
                route_counts[spec.name] = route_counts.get(spec.name, 0) + 1
                try:
                    response = client.request(
                        method=method,
                        url=f"{base_url}{path}",
                        params=payload["params"],
                        json=payload["json"] or None,
                        headers=headers,
                    )
                except httpx.TransportError as exc:
                    transport_errors += 1
                    failures += 1
                    if transport_errors <= 5 or transport_errors % 25 == 0:
                        print(
                            "transport_error:"
                            f" req={request_id}"
                            f" route={spec.name}"
                            f" error={type(exc).__name__}: {exc}"
                        )
                    continue
                status_counts[response.status_code] = status_counts.get(response.status_code, 0) + 1
                if not response.is_success:
                    failures += 1

            if args.scenario == "realistic":
                jitter = 1.0 + rng.uniform(-args.tick_jitter, args.tick_jitter)
            else:
                jitter = 1.0
            time.sleep(max(0.05, jitter))

    elapsed = round(time.monotonic() - start_time, 2)
    print("synthetic_load: complete")
    print(f"- total_requests: {total_requests}")
    print(f"- non_2xx: {failures}")
    print(f"- transport_errors: {transport_errors}")
    print(f"- elapsed_seconds: {elapsed}")
    print(f"- status_counts: {dict(sorted(status_counts.items()))}")
    print(f"- route_counts: {dict(sorted(route_counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
