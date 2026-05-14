"""Synthetic Django ASGI app used by the install-matrix smoke and unit tests.

Mirrors ``synthetic_test_app.py`` for the FastAPI adapter: a minimum-viable
Django app with a healthy route, a parameterized route, and a route that
raises so the SDK's error path is exercised. The lumonox Django middleware
is wired in via ``settings.MIDDLEWARE``.

``create_asgi_app()`` is the entry point: it configures Django settings on
first call, wires the middleware, and returns the ASGI callable. The
dispatcher is built by ``lumonox.django.monitor(...)``; callers can wrap
the ASGI app with ``lumonox.django.wrap_asgi`` to drive start/stop via
ASGI lifespan, or manage the dispatcher lifecycle themselves.

``create_monitored_asgi_app()`` is the runnable entry point for the
synthetic stack: it calls ``monitor()`` from ``LUMONOX_*`` env vars and
wraps the app with ``wrap_asgi`` so uvicorn's lifespan drives the
dispatcher. It is a factory (no import-time side effects) — serve it with
``uvicorn lumonox.fixtures.synthetic_django_app:create_monitored_asgi_app --factory``
(see ``scripts/run_synthetic_django_stack.sh``).
"""

from __future__ import annotations

import logging
from typing import Any

# Importing ``django`` here is intentional: this fixture only makes sense if
# Django is installed. Tests that want to skip when Django is missing should
# use ``pytest.importorskip("django")`` before importing this module.
import django
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path

from lumonox.fixtures.synthetic_lumonox_config import SyntheticLumonoxFixture

logger = logging.getLogger("lumonox.synthetic_django_app")

_SECRET_KEY = "lumonox-synthetic-django-secret-not-for-prod"  # noqa: S105  # nosec B105 — test-only constant


def _configure_settings_once() -> None:
    """Configure Django settings the first time the fixture is used.

    Django allows ``settings.configure()`` to be called at most once per
    process; subsequent fixture invocations reuse the existing config.
    """
    if settings.configured:
        return
    settings.configure(
        DEBUG=False,
        SECRET_KEY=_SECRET_KEY,
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        MIDDLEWARE=[
            "lumonox.django.middleware.LumonoxMiddleware",
        ],
        DATABASES={},
        INSTALLED_APPS=[],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        # Async middleware is the supported path. Disable the auto-async-mode
        # warnings that Django emits when running without an event loop yet.
        LOGGING_CONFIG=None,
    )
    django.setup()


async def healthz(request: Any) -> JsonResponse:
    return JsonResponse({"ok": True, "service": "synthetic-django-api"})


async def get_user(request: Any, user_id: str) -> JsonResponse:
    return JsonResponse({"id": user_id, "name": "demo"})


async def boom(request: Any) -> HttpResponse:
    raise RuntimeError("synthetic django explosion")


urlpatterns = [
    path("health/", healthz, name="health"),
    path("users/<str:user_id>/", get_user, name="user_detail"),
    path("boom/", boom, name="boom"),
]


def create_asgi_app() -> Any:
    """Return the synthetic Django ASGI application with the lumonox middleware enabled."""
    from django.core.asgi import get_asgi_application

    _configure_settings_once()
    return get_asgi_application()


def create_monitored_asgi_app(
    *,
    enable_monitor: bool = True,
    lumonox_fixture: SyntheticLumonoxFixture | None = None,
) -> Any:
    """Runnable ASGI app for the synthetic stack: wires ``monitor()`` + lifespan.

    Mirrors ``synthetic_test_app.create_app`` for the Django adapter. Use as a
    uvicorn factory so importing this module stays side-effect-free for the
    unit tests::

        uvicorn lumonox.fixtures.synthetic_django_app:create_monitored_asgi_app --factory

    With ``enable_monitor`` (the default) the lumonox dispatcher is built from
    ``LUMONOX_*`` env vars and the app is wrapped with ``wrap_asgi`` so
    uvicorn's lifespan startup/shutdown drives ``dispatcher.start()`` /
    ``.stop()``. With ``enable_monitor=False`` the plain ASGI app is returned
    (the middleware then passes through — never breaks the host app).
    """
    from lumonox.django import monitor, wrap_asgi

    asgi_app = create_asgi_app()
    if not enable_monitor:
        return asgi_app

    fixture = lumonox_fixture or SyntheticLumonoxFixture.from_env()
    monitor(**fixture.monitor_kwargs(dashboard_widgets=[]))

    dep = fixture.deployment
    if dep.api_key and (dep.ingest_url or "").strip():
        logger.info(
            "synthetic_django_app: Lumonox active (remote), service=%s environment=%s",
            fixture.common.service_name,
            fixture.common.environment,
        )
    else:
        logger.warning(
            "synthetic_django_app: Lumonox is not sending events "
            "(missing api_key or ingest_url). Set LUMONOX_INGEST_URL and LUMONOX_API_KEY "
            "(see scripts/run_synthetic_django_stack.sh)."
        )

    return wrap_asgi(asgi_app)
