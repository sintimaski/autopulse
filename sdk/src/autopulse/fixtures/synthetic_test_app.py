from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from autopulse import (
    BarChartWidget,
    CardWidget,
    DonutChartWidget,
    HistogramWidget,
    LineChartWidget,
    ScatterPlotWidget,
    StackedAreaWidget,
    autopulse,
)

logger = logging.getLogger("autopulse.synthetic_test_app")

Role = Literal["viewer", "editor", "admin"]


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str
    role: Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=3, max_length=128)


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    display_name: str = Field(min_length=2, max_length=80)
    role: Role = "viewer"


class PatchUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: Role | None = None
    version: int = Field(default=0, ge=0)


class CreateOrderRequest(BaseModel):
    user_id: int = Field(ge=1)
    amount_cents: int = Field(ge=100, le=5_000_000)
    item: str = Field(min_length=2, max_length=160)


_USERS: dict[int, dict[str, object]] = {
    1: {
        "id": 1,
        "email": "alexa@example.com",
        "display_name": "Alexa",
        "role": "admin",
        "version": 2,
    },
    2: {
        "id": 2,
        "email": "kai@example.com",
        "display_name": "Kai",
        "role": "editor",
        "version": 4,
    },
    3: {
        "id": 3,
        "email": "mira@example.com",
        "display_name": "Mira",
        "role": "viewer",
        "version": 1,
    },
}
_ORDERS: dict[int, dict[str, object]] = {
    1001: {"id": 1001, "user_id": 2, "amount_cents": 1299, "item": "notebook"},
    1002: {"id": 1002, "user_id": 3, "amount_cents": 2499, "item": "wireless-mouse"},
}
_ALLOWED_ROLES: tuple[Role, ...] = ("viewer", "editor", "admin")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _stable_roll(salt: str) -> float:
    digest = hashlib.sha256(salt.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 4_294_967_295


def _should_happen(*, probability: float, salt: str) -> bool:
    bounded_probability = min(max(probability, 0.0), 1.0)
    return _stable_roll(salt) < bounded_probability


def _build_demo_dashboard_widgets() -> list[object]:
    # Simple deterministic processing over fixture data to showcase each widget type.
    total_users = len(_USERS)
    total_orders = len(_ORDERS)
    avg_order_value = (
        sum(int(order["amount_cents"]) for order in _ORDERS.values()) / max(total_orders, 1) / 100.0
    )
    role_counts: dict[str, int] = {"viewer": 0, "editor": 0, "admin": 0}
    for user in _USERS.values():
        role = str(user.get("role", "viewer"))
        if role in role_counts:
            role_counts[role] += 1
    recent_load_points = [
        ("-5m", float(total_orders + 1)),
        ("-4m", float(total_orders + 2)),
        ("-3m", float(total_orders + 3)),
        ("-2m", float(total_orders + 2)),
        ("-1m", float(total_orders + 4)),
    ]
    orders_by_item = [
        (str(order["item"]), float(order["amount_cents"]) / 100.0) for order in _ORDERS.values()
    ]
    latency_histogram = [
        ("<50ms", 12.0),
        ("50-100ms", 24.0),
        ("100-250ms", 18.0),
        ("250ms+", 6.0),
    ]
    route_risk_scatter = [
        (130.0, 0.8, "/health"),
        (88.0, 2.4, "/users/{id}"),
        (62.0, 6.9, "/orders"),
        (20.0, 12.3, "/reports/daily"),
    ]
    stacked_mix = [
        ("-5m", "success", 18.0),
        ("-5m", "client", 2.0),
        ("-5m", "server", 1.0),
        ("-4m", "success", 21.0),
        ("-4m", "client", 3.0),
        ("-4m", "server", 1.0),
        ("-3m", "success", 22.0),
        ("-3m", "client", 2.0),
        ("-3m", "server", 2.0),
        ("-2m", "success", 20.0),
        ("-2m", "client", 4.0),
        ("-2m", "server", 2.0),
        ("-1m", "success", 24.0),
        ("-1m", "client", 3.0),
        ("-1m", "server", 1.0),
    ]
    return [
        CardWidget(
            widget_id="synthetic_avg_order_usd",
            title="Avg order value",
            description="Computed from seeded synthetic orders",
            value=round(avg_order_value, 2),
            unit="USD",
            tone="neutral",
            order=10,
        ),
        LineChartWidget(
            widget_id="synthetic_recent_load",
            title="Recent synthetic load",
            description="Derived minute trend for fixture traffic",
            points=recent_load_points,
            color="#818cf8",
            unit="req",
            order=20,
        ),
        BarChartWidget(
            widget_id="synthetic_orders_by_item",
            title="Order value by item",
            description="Current fixture order mix",
            bars=orders_by_item,
            unit="USD",
            order=30,
        ),
        DonutChartWidget(
            widget_id="synthetic_user_roles",
            title="User role distribution",
            description=f"Roles across {total_users} users",
            slices=[(key, float(value)) for key, value in role_counts.items()],
            order=40,
        ),
        HistogramWidget(
            widget_id="synthetic_latency_histogram",
            title="Latency distribution",
            description="Synthetic request-latency buckets",
            buckets=latency_histogram,
            unit="req",
            order=50,
        ),
        ScatterPlotWidget(
            widget_id="synthetic_route_risk",
            title="Route risk scatter",
            description="x=request volume, y=error rate %",
            points=route_risk_scatter,
            x_label="Request volume",
            y_label="Error rate %",
            order=60,
        ),
        StackedAreaWidget(
            widget_id="synthetic_outcome_stack",
            title="Outcome stack",
            description="Success/client/server composition over time",
            points=stacked_mix,
            order=70,
        ),
    ]


def _parse_test_token(x_auth_token: str | None) -> AuthContext | None:
    if x_auth_token is None:
        return None
    parts = [piece.strip() for piece in x_auth_token.split(":")]
    if len(parts) != 3 or parts[0] != "demo":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid x-auth-token format",
        )
    _, role_raw, user_id = parts
    role: Role | None = role_raw.lower() if role_raw.lower() in _ALLOWED_ROLES else None
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown role in token",
        )
    return AuthContext(user_id=user_id or "token-user", role=role)


def _auth_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
    x_test_role: str | None = Header(default=None),
    x_test_user: str | None = Header(default=None),
) -> AuthContext:
    if isinstance(authorization, str) and authorization.strip().lower() == "bearer expired":
        logger.warning("auth_rejected route=%s reason=expired-bearer", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired bearer token",
        )
    token_context = _parse_test_token(x_auth_token)
    if token_context is not None:
        return token_context
    if x_test_role is not None:
        maybe_role = x_test_role.strip().lower()
        if maybe_role not in _ALLOWED_ROLES:
            logger.warning(
                "auth_rejected route=%s reason=invalid-role role=%s",
                request.url.path,
                maybe_role,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role")
        return AuthContext(user_id=(x_test_user or "header-user"), role=maybe_role)
    logger.warning("auth_rejected route=%s reason=missing-auth", request.url.path)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing synthetic credentials",
    )


AUTH_CONTEXT = Depends(_auth_context)
FLAG_QUERY = Query(default=False)
SEARCH_QUERY = Query(default="all", min_length=1, max_length=100)
REPORT_DATE_QUERY = Query(default=None)


def _enforce_role(
    request: Request,
    auth: AuthContext,
    allowed_roles: frozenset[Role],
) -> AuthContext:
    if auth.role in allowed_roles:
        return auth
    logger.warning(
        "auth_forbidden route=%s user=%s role=%s allowed=%s",
        request.url.path,
        auth.user_id,
        auth.role,
        ",".join(sorted(allowed_roles)),
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def _require_viewer(request: Request, auth: AuthContext = AUTH_CONTEXT) -> AuthContext:
    return _enforce_role(request, auth, frozenset({"viewer", "editor", "admin"}))


def _require_editor(request: Request, auth: AuthContext = AUTH_CONTEXT) -> AuthContext:
    return _enforce_role(request, auth, frozenset({"editor", "admin"}))


def _require_admin(request: Request, auth: AuthContext = AUTH_CONTEXT) -> AuthContext:
    return _enforce_role(request, auth, frozenset({"admin"}))


VIEWER_AUTH = Depends(_require_viewer)
EDITOR_AUTH = Depends(_require_editor)
ADMIN_AUTH = Depends(_require_admin)


def create_app(*, enable_monitor: bool = True) -> FastAPI:
    app = FastAPI(title="AutoPulse Synthetic Test App", version="0.1.0")

    if enable_monitor:
        mode = os.getenv("AUTOPULSE_MODE", "embedded").strip().lower()
        monitor_kwargs: dict[str, object] = {
            "mode": mode,
            "service_name": os.getenv("AUTOPULSE_SERVICE_NAME", "synthetic-test-api"),
            "environment": os.getenv("AUTOPULSE_ENVIRONMENT", "dev"),
            "batch_size": int(os.getenv("AUTOPULSE_BATCH_SIZE", "20")),
            "flush_interval_s": float(os.getenv("AUTOPULSE_FLUSH_INTERVAL_S", "1.0")),
            "debug": os.getenv("AUTOPULSE_DEBUG", "").strip().lower() in {"1", "true", "yes"},
            "mount_prefix": os.getenv("AUTOPULSE_MOUNT_PREFIX", "/autopulse"),
            "database_url": os.getenv(
                "AUTOPULSE_DATABASE_URL",
                "sqlite+aiosqlite:///./autopulse_embedded.db",
            ),
            "frontend_mode": os.getenv("AUTOPULSE_FRONTEND_MODE", "static"),
            "dashboard_widgets": _build_demo_dashboard_widgets(),
        }
        if mode == "remote":
            monitor_kwargs["api_key"] = os.getenv("AUTOPULSE_API_KEY")
            monitor_kwargs["ingest_url"] = os.getenv(
                "AUTOPULSE_INGEST_URL", "http://localhost:8000/ingest"
            )
        autopulse(app, **monitor_kwargs)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or f"syn-{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"ok": True, "service": "synthetic-test-api", "timestamp": _utc_now()}

    @app.get("/users/{user_id}")
    async def get_user(
        user_id: int,
        request: Request,
        auth: AuthContext = VIEWER_AUTH,
    ) -> dict[str, object]:
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        if user_id not in _USERS or _should_happen(
            probability=0.2,
            salt=f"user-miss:{user_id}:{request_id}",
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"actor": auth.user_id, "user": _USERS[user_id]}

    @app.post("/users", status_code=status.HTTP_201_CREATED)
    async def create_user(
        payload: CreateUserRequest,
        auth: AuthContext = EDITOR_AUTH,
    ) -> dict[str, object]:
        if payload.email.endswith("@blocked.example"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email domain blocked",
            )
        next_id = max(_USERS) + 1
        model = {
            "id": next_id,
            "email": payload.email,
            "display_name": payload.display_name,
            "role": payload.role,
            "version": 0,
        }
        _USERS[next_id] = model
        logger.info("user_created actor=%s user_id=%s", auth.user_id, next_id)
        return {"user": model}

    @app.patch("/users/{user_id}")
    async def patch_user(
        user_id: int,
        payload: PatchUserRequest,
        request: Request,
        force_conflict: bool = FLAG_QUERY,
        auth: AuthContext = EDITOR_AUTH,
    ) -> dict[str, object]:
        user = _USERS.get(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        should_conflict = force_conflict or _should_happen(
            probability=0.25,
            salt=f"patch-conflict:{user_id}:{payload.version}:{request_id}",
        )
        if should_conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Version mismatch")
        if payload.display_name is not None:
            user["display_name"] = payload.display_name
        if payload.role is not None:
            user["role"] = payload.role
        user["version"] = int(user["version"]) + 1
        logger.info("user_updated actor=%s user_id=%s", auth.user_id, user_id)
        return {"user": user}

    @app.get("/orders/{order_id}")
    async def get_order(
        order_id: int,
        request: Request,
        auth: AuthContext = VIEWER_AUTH,
    ) -> dict[str, object]:
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        if order_id not in _ORDERS or _should_happen(
            probability=0.16,
            salt=f"order-miss:{order_id}:{request_id}",
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return {"actor": auth.user_id, "order": _ORDERS[order_id]}

    @app.post("/orders", status_code=status.HTTP_201_CREATED)
    async def create_order(
        payload: CreateOrderRequest,
        request: Request,
        force_unavailable: bool = FLAG_QUERY,
        auth: AuthContext = EDITOR_AUTH,
    ) -> dict[str, object]:
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        should_fail = force_unavailable or _should_happen(
            probability=0.18,
            salt=f"orders-unavailable:{payload.user_id}:{request_id}",
        )
        if should_fail:
            logger.error("order_upstream_failure actor=%s request_id=%s", auth.user_id, request_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory backend unavailable",
            )
        order_id = max(_ORDERS) + 1
        order = {
            "id": order_id,
            "user_id": payload.user_id,
            "amount_cents": payload.amount_cents,
            "item": payload.item,
        }
        _ORDERS[order_id] = order
        return {"order": order}

    @app.get("/search")
    async def search(
        request: Request,
        q: str = SEARCH_QUERY,
        auth: AuthContext = VIEWER_AUTH,
    ) -> dict[str, object]:
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        if _should_happen(probability=0.2, salt=f"search-latency:{q}:{request_id}"):
            await asyncio.sleep(0.35)
        else:
            await asyncio.sleep(0.04)
        return {
            "actor": auth.user_id,
            "query": q,
            "count": 3,
            "items": ["alpha", "beta", "gamma"],
        }

    @app.post("/auth/login")
    async def login(payload: LoginRequest) -> dict[str, object]:
        users: dict[str, tuple[str, Role]] = {
            "viewer@example.com": ("demo-pass", "viewer"),
            "editor@example.com": ("demo-pass", "editor"),
            "admin@example.com": ("demo-pass", "admin"),
        }
        expected = users.get(payload.username.lower())
        if expected is None or expected[0] != payload.password:
            logger.warning("login_failed username=%s", payload.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        role = expected[1]
        return {"token": f"demo:{role}:{payload.username.lower()}", "role": role}

    @app.get("/reports/daily")
    async def daily_report(
        report_date: date | None = REPORT_DATE_QUERY,
        force_timeout: bool = FLAG_QUERY,
        auth: AuthContext = ADMIN_AUTH,
    ) -> dict[str, object]:
        effective_date = report_date or date.today()
        await asyncio.sleep(0.9)
        if force_timeout or _should_happen(
            probability=0.14,
            salt=f"daily-report:{effective_date.isoformat()}",
        ):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Report query timed out",
            )
        return {
            "actor": auth.user_id,
            "date": effective_date.isoformat(),
            "totals": {"requests": 1842, "errors": 63, "p95_latency_ms": 241.7},
        }

    @app.get("/boom")
    async def boom(
        request: Request,
        auth: AuthContext = ADMIN_AUTH,
    ) -> dict[str, object]:
        request_id = str(getattr(request.state, "request_id", "no-request-id"))
        logger.error("boom_triggered actor=%s request_id=%s", auth.user_id, request_id)
        raise ValueError(f"Synthetic crash in /boom request_id={request_id}")

    return app


app = create_app()
