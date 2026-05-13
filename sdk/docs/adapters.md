# Framework adapter contract

`lumonox-sdk` ships with **two** framework adapters today:

- `lumonox.fastapi` — FastAPI / Starlette (the original).
- `lumonox.django` — Django async middleware (ASGI; opt-in via the `[django]`
  extra so the FastAPI install line stays unchanged for current users).

The send path, scrubbing, event shape, bounded queue, and psutil-backed
infrastructure sampling are framework-agnostic and live under `lumonox.core`.
This document describes what a framework adapter must provide and what the
existing adapters do. A new adapter (Flask, Litestar, …) is one new file
under `lumonox.<framework>.middleware`.

## Layout

```
src/lumonox/
  __init__.py            # public API + lazy re-exports (unchanged surface)
  core/                  # framework-agnostic implementation
    config.py            # _MonitorConfig dataclass
    dispatcher.py        # _EventDispatcher (queue + transport + retries + circuit breaker)
    env.py               # LUMONOX_* env-var parsers
    events.py            # event-shape helpers (timestamp, error hash, batch split, widgets)
    infrastructure.py    # InfrastructureSampler (psutil counters)
    jobs.py              # capture_background_job (no framework dep)
    paths.py             # path-prefix normalization + ignore-list logic
    runtime_context.py   # correlation-id contextvars
    sampling.py          # request sampling
    scrubbing.py         # DEFAULT_SCRUB_KEYS + _scrub_value
  fastapi/               # FastAPI / Starlette adapter
    __init__.py          # exposes ``monitor``
    middleware.py        # _LumonoxMiddleware + _resolve_route_path + monitor()
  django/                # Django async-middleware adapter (ASGI)
    __init__.py          # exposes ``monitor``, ``LumonoxMiddleware``, ``wrap_asgi``
    middleware.py        # LumonoxMiddleware + got_request_exception hook + wrap_asgi
  _monitor.py            # re-export shim → core.* + fastapi.middleware
  _infrastructure.py     # re-export shim → core.infrastructure
  _jobs.py               # re-export shim → core.jobs
  _runtime_context.py    # re-export shim → core.runtime_context
  widgets.py             # dashboard widget primitives
```

`lumonox.core.*` is intentionally Starlette-free. `lumonox.fastapi.*` is
the only place where Starlette / FastAPI types appear at import time. New
adapters live as siblings: `lumonox.django.middleware`,
`lumonox.flask.middleware`, etc.

The underscore modules (`_monitor.py`, `_infrastructure.py`, `_jobs.py`,
`_runtime_context.py`) are re-export shims kept for the pre-split import
surface — callers that imported from them keep working without
modification. There is no deprecation warning; the shims are part of the
stability contract.

If your tests need to monkeypatch module-level attributes (e.g. the
``psutil`` reference inside ``InfrastructureSampler.sample()`` or the
``_add_event_handler`` lookup inside ``monitor()``), patch the
**canonical** path — that is the module the lookup actually happens in:

```python
monkeypatch.setattr("lumonox.core.infrastructure.psutil", _stub)
monkeypatch.setattr("lumonox.fastapi.middleware._add_event_handler", _stub)
```

## What a new adapter must do

A framework adapter is a single Python file (≈ 250 LOC, judging by
`lumonox.fastapi.middleware`). Its responsibilities are:

1. **Extract a request snapshot.** Produce a small dict with at minimum
   `method`, the resolved route template (preferred) or raw path, request
   `headers` and `query_params` if `capture_headers` /
   `capture_query_params` are enabled, and a correlation id (preferring
   an incoming `X-Request-ID` or `X-Correlation-ID` header). Use
   `lumonox.core.runtime_context.set_correlation_id` /
   `reset_correlation_id` so background jobs scheduled within the
   request can inherit the id.

2. **Wrap the response (and any exception) into an ingest event.**
   Capture wall-clock latency, status code, and on exceptions a stable
   error hash (`lumonox.core.events._stable_error_hash`) plus a redacted
   stack trace. Re-raise the original exception so the host framework's
   error pipeline still runs — the SDK must never swallow user-facing
   errors.

3. **Hand events to the dispatcher.** Construct
   `lumonox.core.dispatcher._EventDispatcher(config)` from a
   `_MonitorConfig`, register its `start()` / `stop()` with the host
   framework's lifecycle (FastAPI: `add_event_handler('startup', …)`;
   Django: `AppConfig.ready()` + signal handlers; Flask:
   `app.before_serving` / `app.teardown_appcontext`), and call
   `dispatcher.enqueue(event)` on the request path. Never block on
   transport.

## The Django adapter as a worked example

`lumonox.django.middleware` is one file. It imports nothing from
`lumonox.fastapi.*` — only:

```python
from lumonox.core.config import _MonitorConfig, build_monitor_config
from lumonox.core.dispatcher import _EventDispatcher
from lumonox.core.events import (
    _build_infrastructure_widget_payload,
    _merge_release_git_into_event,
    _merge_widget_payloads,
    _stable_error_hash,
    _utc_now_iso,
)
from lumonox.core.paths import _path_is_ignored
from lumonox.core.runtime_context import reset_correlation_id, set_correlation_id
from lumonox.core.sampling import _should_sample_request
from lumonox.widgets import serialize_dashboard_widgets
```

`build_monitor_config(**kwargs)` is the shared config builder that resolves
`LUMONOX_*` env vars + kwargs + defaults into a `_MonitorConfig` so both
adapters honor the same set of knobs.

Django specifics worth knowing if you write a third adapter:

- **Django catches view exceptions before outer middleware sees them.**
  Django's exception middleware (added implicitly inside `BaseHandler`)
  wraps the view and converts unhandled exceptions to 500 responses.
  Our middleware never sees the raw `Exception`. To recover exception
  detail (type / message / stack trace / error hash) we connect to
  `django.core.signals.got_request_exception` once in `monitor()`. The
  handler attaches the exception to `request._lumonox_exception` (a plain
  attribute on the request object) because the request object travels
  through Django's `sync_to_async` boundary intact, whereas contextvars
  do not. When the middleware sees a 5xx response, it reads
  `request._lumonox_exception` and emits the `type=error` event.
- **The signal handler must be module-level.** Django's signal registry
  holds receivers via weak refs by default; a nested-function receiver
  would be GC'd shortly after `connect()` returns and the handler would
  silently disappear. `_exception_signal_handler` is at module scope so
  Python keeps it alive for the life of the process.
- **No `app.state` analogue.** Django middleware classes are instantiated
  lazily on first request, not handed an `app` object. We keep the
  dispatcher + config in a module-level `_Runtime` slot that `monitor()`
  writes and the middleware reads. One dispatcher per process, which is
  what users expect.
- **Lifespan ergonomics: `wrap_asgi(asgi_app)`.** Wrapping the Django
  ASGI app with `wrap_asgi` drives `await dispatcher.start()` and
  `await dispatcher.stop()` from the standard ASGI lifespan protocol so
  users do not have to manage SDK lifecycle by hand.

## Hard constraints

These mirror `.cursor/rules/lumonox-engineering.mdc` and apply to every
adapter:

- **Never break the host app.** If the dispatcher or transport is
  broken, the host request must still succeed. Silent failure is the
  default; `LUMONOX_DEBUG=1` is the only opt-in path to error logging.
- **Hot path is async / non-blocking.** No blocking I/O in middleware;
  the send path runs in a background asyncio task with `asyncio.Queue`
  + drop-when-full semantics. (For sync-only frameworks like classic
  Django WSGI, the adapter must run the dispatcher in its own asyncio
  loop on a background thread — not on the request thread.)
- **Scrub before send.** ``_EventDispatcher.enqueue`` already calls
  ``_scrub_value`` using ``_MonitorConfig.scrub_keys``; adapters should
  not duplicate scrubbing, but they must not bypass `enqueue` either.
- **Re-raise on exception.** Capture the event then re-raise; the
  response always carries an `X-Request-ID` header on the non-error
  path.
- **No public-API drift.** `from lumonox import monitor, lumonox,
  capture_background_job` is part of the SDK's stability contract.
  A Django adapter should expose its own `monitor(app, …)` factory; the
  top-level `lumonox(app, …)` convenience should remain FastAPI-focused
  until product strategy explicitly broadens it.

## Why this layout

Today `lumonox-sdk` ships exactly one framework adapter, and `fastapi`
is a required dependency because that is the framework it instruments
(see `.cursor/rules/lumonox-product.mdc`: Lumonox is FastAPI-native).
The core/adapter split exists for two reasons:

- **Readability.** Framework-independent primitives (queue, transport,
  scrubbing, infrastructure metrics, correlation) are reachable from
  one place and can be tested without instantiating a FastAPI app.
- **Optionality.** If a second adapter is ever shipped, the only new
  module is `lumonox.<framework>.middleware`. Required dependencies
  stay required (`fastapi` cannot move to an extra without a default-
  install regression — see `docs/plans/sdk-install-ease.md`
  no-regression table); a future adapter would add its own framework
  dep alongside.
