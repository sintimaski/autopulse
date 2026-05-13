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
"""

from __future__ import annotations

from typing import Any

# Importing ``django`` here is intentional: this fixture only makes sense if
# Django is installed. Tests that want to skip when Django is missing should
# use ``pytest.importorskip("django")`` before importing this module.
import django
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path

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
