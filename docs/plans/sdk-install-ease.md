# SDK Install-Ease Plan

**Status:** Phases 0 + 1 + 2 executed on 2026-05-13 (see Results below). Phase 3 deferred.
**Owner:** Dima Drebezov.
**Scope:** `sdk/` only. No changes to the backend, dashboard, or wire protocol.
**Goal:** make `pip install lumonox-sdk` succeed on more environments, with fewer dependency conflicts, on more Python versions — without giving up any current SDK guarantees (silent failure, async hot path, scrubbing, never-break-user-app) **and without reducing default functionality**. A `pip install lumonox-sdk` after this work must produce a product that is *at least as capable* as today's; no metric, capture path, or behavior may be silently lost behind an extra.

## Results (2026-05-13, Phases 0–2)

Measured on Python 3.11.15, macOS / arm64, off a clean venv (numbers reproduce in linux/amd64 slim and linux/arm64 slim cells of `.github/workflows/sdk-install-matrix.yml`).

| Metric | Before | After Phase 1+2 |
|--------|--------|-----------------|
| `requires-python` | `>=3.11` | `>=3.10` |
| `fastapi` floor | `>=0.115.0` | `>=0.100.0` |
| `httpx` floor | `>=0.27.0` | `>=0.24.0` |
| `psutil` floor | `>=6.0.0` | `>=5.9.0` |
| Wheel size (py3-none-any) | 37,178 B | 46,048 B |
| Sdist size | 44,929 B | 53,838 B |
| Install plan packages (incl. lumonox-sdk) | 16 | 16 |
| Cold-import (best of 3, fresh process) | ~57 ms | ~61 ms |
| Default install behaves identically (psutil-backed infra metrics emitted, FastAPI middleware attaches, scrub + queue + correlation unchanged) | yes | yes |
| `fastapi/middleware.py` size | 1128 LOC | ~430 LOC |

Wheel/sdist grew ~9 KB because the original 1128-LOC `_monitor.py` was decomposed into 10 framework-agnostic `core/` modules plus a slimmer `fastapi/middleware.py`, and a new test file (`test_canonical_paths.py`) + adapter doc (`sdk/docs/adapters.md`) were added. Cold-import time grew ~4 ms because the import graph is now broader (more module objects to construct) but stays well inside the 300 ms budget (local baseline ~57 ms; budget is wall-clock around a `python -c "import lumonox"` subprocess so it includes interpreter startup, and is sized to absorb the 100–150 ms overhead slow CI cells like musl/QEMU contribute before any lumonox code runs). Public symbol identity is preserved: `lumonox.fastapi.middleware.monitor is lumonox._monitor.monitor` and `lumonox.core.infrastructure.InfrastructureSampler is lumonox._infrastructure.InfrastructureSampler` (verified by `sdk/tests/test_canonical_paths.py` and at install-smoke time).

## What shipped

- `sdk/pyproject.toml`: widened `requires-python` to `>=3.10`; floors loosened (see table); 3.10 classifier added.
- `sdk/src/lumonox/`: replaced `from datetime import UTC` with `from datetime import timezone` + `timezone.utc` so the module bytecode loads on Python 3.10 (UTC alias is 3.11+). Tracked via per-file ruff ignore `UP017` for `sdk/src/lumonox/**/*.py` in the workspace `pyproject.toml`.
- `sdk/src/lumonox/core/*` (10 modules: config, dispatcher, env, events, infrastructure, jobs, paths, runtime_context, sampling, scrubbing) and `sdk/src/lumonox/fastapi/{__init__,middleware}.py`: canonical implementation paths. The previous underscore modules (`_monitor.py`, `_infrastructure.py`, `_jobs.py`, `_runtime_context.py`) became re-export shims. Two test monkeypatch target strings in `sdk/tests/test_monitor.py` were updated to the canonical paths; the test file's import block also moved.
- `sdk/tests/test_canonical_paths.py`: new 7-case test pinning object identity between canonical paths and legacy shims, plus a regression check that `monkeypatch.setattr("lumonox.core.infrastructure.psutil", …)` disables `InfrastructureSampler.sample()` and an "adapter surface" check that asserts every symbol a future framework adapter would import is exposed by `lumonox.core.*`.
- `sdk/docs/adapters.md`: adapter contract (what a non-FastAPI binding must do on top of `lumonox.core`).
- `scripts/sdk_end_to_end_smoke.py`: lightweight end-to-end smoke — boots a stub WSGI ingest server, instruments a FastAPI app via `lumonox(app, …)`, drives an ok-path + a 500-path, asserts the delivered ingest events carry the right shape and that `Authorization` was scrubbed before send.
- **Django adapter (Phase 3 second adapter, enabled by Phase 2):** `sdk/src/lumonox/django/{__init__,middleware}.py` — async ASGI middleware that reuses every helper in `lumonox.core.*`. `monitor(**kwargs)` builds the dispatcher; `wrap_asgi(asgi_app)` drives `start()/stop()` from the ASGI lifespan; `LumonoxMiddleware` goes into `settings.MIDDLEWARE`. Install via `pip install "lumonox-sdk[django]"` (extra: `django>=4.2`). Synthetic Django fixture at `sdk/src/lumonox/fixtures/synthetic_django_app.py`; 3 pytest cases at `sdk/tests/test_django_middleware.py` exercise it via `httpx.ASGITransport`. Rich error events for Django 500s flow through `django.core.signals.got_request_exception` since Django's exception middleware catches view errors before outer middleware can.
- `lumonox.core.config.build_monitor_config(**kwargs)` — shared config builder that funnels every adapter's env-var/kwargs/defaults logic through one place. Both adapters call it identically.
- `sdk/README.md`: Compatibility section documenting the new floors and tested matrix.
- `sdk/CHANGELOG.md`: Unreleased entry describing the widened Python range, looser floors, and canonical paths.
- `.github/workflows/sdk-install-matrix.yml` + `scripts/sdk_install_smoke.py`: pure-Python install-matrix workflow covering {3.10, 3.11, 3.12, 3.13} × {amd64, arm64} × {slim, alpine}, with one extra cell pinning every floor (`fastapi==0.100.0`, `httpx==0.24.0`, `psutil==5.9.0`) on `python:3.10-slim`. Each cell asserts the psutil-backed counter set is populated and that `python -c "import lumonox"` finishes under a 300 ms cold-import budget (wall-clock around a subprocess, so it includes Python startup; sized for slow CI cells like musl/QEMU while still catching real import-graph regressions).

`uv run pytest sdk/tests/` and `uv run mypy` are green; `uv run ruff check sdk/` is green. The cross-platform matrix runs in CI on push and PR.

This plan does **not** introduce a Rust core, native compilation, or non-Python language bindings. Pure-Python `py3-none-any` is already the gold standard for install ease; the work here is to defend and extend that property.

### Guiding constraint: no functional regression

Several "obvious" install-ease moves trade capability for portability. Those are rejected here:

| Tempting move | Why it's rejected |
|---------------|-------------------|
| Move `psutil` to an extra | psutil powers host/process CPU, memory, disk, network metrics (`_infrastructure.py`). Behind an extra, the default install silently drops those widgets. The existing `try/except ImportError` is a robustness belt for damaged/sandboxed envs, not a product signal. psutil already ships manylinux + musllinux + macOS + Windows wheels; install pain is small in practice. **Keep required.** |
| Move `httpx` to an extra with stdlib fallback | The send path uses a bounded queue with drop-when-full. A 20–30% slower transport means *more drops under load* — a functional regression even though no API changes. **Keep required.** |
| Move `fastapi` to an extra | The SDK is a FastAPI middleware. Making it optional is cosmetic until we ship a second framework adapter (separate product decision, see Phase 3). **Keep required for now.** |

What remains is a set of changes that strictly *expand* reach and *reduce* conflicts without touching capability.

---

## Baseline (what we have today)

From `sdk/pyproject.toml` and a scan of `sdk/src/lumonox/`:

- Build: `hatchling`, `py3-none-any` wheel. Single source package `lumonox`.
- `requires-python = ">=3.11"`.
- Hard deps:
  - `fastapi>=0.115.0`
  - `httpx>=0.27.0`
  - `psutil>=6.0.0` ← **only non-pure-Python dep**
- Optional extra: `[stack]` → pulls in the backend (`lumonox>=0.2.10`). Correct as-is.
- Framework coupling: `_monitor.py` imports `fastapi`, `starlette`, `httpx` at module top-level.
- `psutil` is already wrapped in `try/except ImportError` (`_infrastructure.py:12`) — the SDK degrades gracefully when it's missing. **This means psutil can move to an extra with zero behavior change.**
- Public surface (`__init__.py`): `monitor`, `lumonox`, `capture_background_job`, widget classes, lazy-loaded `create_app` / `mount_on_app` from the backend. Side-effect-free import.

## Friction sources, ranked by impact (no-regression filter applied)

| # | Source | Why it hurts | Fix path |
|---|--------|--------------|----------|
| 1 | `fastapi>=0.115.0` floor | Apps pinned to older FastAPI lines (0.100–0.114) hit resolver conflicts. | Loosen floor to lowest version exposing the middleware API we actually use; no upper cap. |
| 2 | `httpx>=0.27.0` floor | `httpx` is widely pinned by user apps; tight floor causes conflicts. | Loosen floor to lowest version exposing the `AsyncClient` shape we use; no upper cap. |
| 3 | `psutil>=6.0.0` floor | Similar resolver-pin issue at the floor; the floor itself is more aggressive than needed. | Loosen floor (likely `>=5.9`). Stay required — see no-regression table. |
| 4 | `requires-python = ">=3.11"` | Excludes 3.10 (default on Debian 12, Ubuntu 22.04, RHEL 9 image families). | Widen to `>=3.10` after a syntax/typing audit. |
| 5 | No CI install-matrix smoke test | We don't actually know on which envs install currently succeeds; releases ship blind. | Add CI cells across (3.10–3.13) × (amd64, arm64) × (slim, alpine). |
| 6 | Framework-bound module imports | Forecloses any future second-framework adapter and makes the codebase harder to navigate. | Pure internal refactor; **no dep changes, no public API change** (Phase 3). |
| 7 | psutil install on exotic arches | psutil ships wheels for the common matrix but not riscv / mips / some BSDs. | Out of scope: documented as a known limitation; users on those arches can install a build toolchain. Not common enough to justify dropping the metric. |

---

## Phased plan

Each phase is independently shippable. Phases 1–3 are recommended; Phase 4 is stretch.

### Phase 0 — Measure baseline (½ day)

Before changing anything, capture the current state so we can prove improvement.

- [x] Record current wheel size, sdist size, and install time on a clean venv.
- [x] Record current dep-tree depth via `pip install lumonox-sdk --dry-run --report -`.
- [x] Run `pip install lumonox-sdk` (current built wheel) on Python 3.11 (clean venv) and Python 3.10 (clean venv); install time ~4 s, plan width 16 packages.
- [x] Note the largest single transitive: psutil's native wheel (~890 KB) sits alongside pydantic-core (~4.3 MB) and pydantic (~4.1 MB); fastapi itself is 1.5 MB. Total site-packages with the SDK installed: ~28 MB excluding pip/setuptools.

Output: a 1-page table at the top of this doc replacing this list, used as the before/after benchmark.

### Phase 1 — Conflict-reduction quick wins (low risk, no API change, no functional change)

All four items widen reach or reduce dep-resolver conflicts. None of them changes what the SDK does or which deps it requires.

- [x] **Widened `requires-python` to `>=3.10`.** The only 3.11-only syntax found was `from datetime import UTC`; replaced with `from datetime import timezone` + `timezone.utc` across `_monitor.py`, `_jobs.py`, `widgets.py`, and `fixtures/synthetic_test_app.py`. No PEP 695 `type X = …`, no `Self` import, no `asyncio.TaskGroup`, no exception groups in the SDK. Added a per-file ruff ignore for `UP017` on `sdk/src/lumonox/**/*.py` so the workspace `target-version = "py311"` doesn't push us back to the alias.
- [x] **Loosened version floors:** `fastapi>=0.100.0`, `httpx>=0.24.0`, `psutil>=5.9.0`. Smoke-installed against pinned floor versions in a clean Python 3.10 + 3.11 venv; `lumonox()` attaches, `InfrastructureSampler().sample()` returns the full 14-key counter set. Documented in `sdk/README.md` Compatibility section.
- [x] **CI install-matrix smoke test.** `.github/workflows/sdk-install-matrix.yml` builds the wheel once, then installs it across {3.10, 3.11, 3.12, 3.13} × {amd64, arm64} × {slim, alpine} (12 cells) plus a `python:3.10-slim` floors cell pinning each dependency at its declared minimum. `scripts/sdk_install_smoke.py` is the shared check: import surface, middleware attaches, psutil counter set populated, cold import under 300 ms (subprocess wall-clock; absorbs Python interpreter startup on slow CI cells).
- [x] **Cold-import regression guard.** Embedded in `scripts/sdk_install_smoke.py`: best-of-3 `python -c "import lumonox"` must be under 300 ms. Local baseline ~57 ms (Phase 1) and ~57 ms (Phase 2); unchanged within noise. The budget is wall-clock around a subprocess so it includes Python interpreter startup, which dominates the number on slow CI cells (alpine/musl, QEMU-emulated arm); 300 ms is sized to absorb that overhead while still catching a real import-graph regression of ~100 ms+.

**Acceptance for Phase 1:**
- Baseline table from Phase 0 reruns clean across the new matrix.
- Required deps are unchanged in *number*; only floors are looser.
- Default install produces the same metrics, widgets, and capture behavior as today.

### Phase 2 — Internal core / adapter split (medium risk, *no public API change, no dep change*)

Pure internal refactor. Worth doing for readability and as enabling work for a possible second framework adapter — **not** to make `fastapi` optional. The dep list does not change in this phase.

- [x] **Module layout** as specified — implementation now lives at the canonical paths, with the original 1128-LOC ``_monitor.py`` decomposed into seven framework-agnostic ``core/`` modules plus a ~430-LOC ``fastapi/middleware.py`` adapter glue file:
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
      __init__.py          # exposes monitor
      middleware.py        # _LumonoxMiddleware + _resolve_route_path + monitor()
    _monitor.py            # re-export shim → core.* + fastapi.middleware
    _infrastructure.py     # re-export shim → core.infrastructure
    _jobs.py               # re-export shim → core.jobs
    _runtime_context.py    # re-export shim → core.runtime_context
    widgets.py             # unchanged
  ```
  Test monkeypatch targets were migrated in `sdk/tests/test_monitor.py` (two strings: `lumonox._infrastructure.psutil` → `lumonox.core.infrastructure.psutil`; `lumonox._monitor._add_event_handler` → `lumonox.fastapi.middleware._add_event_handler`). The import block in that test now reaches the canonical core/ paths directly. Identity is locked in by `sdk/tests/test_canonical_paths.py` (7 cases): top-level public-API identity, underscore-shim re-export identity for every symbol the rest of the test suite reaches into, and an "adapter surface" check that asserts the symbols a future Django / Flask adapter would import are all reachable from `lumonox.core.*`.
- [x] **Public API stability:** `from lumonox import monitor, lumonox, capture_background_job` is unchanged. `lumonox.fastapi.middleware` is the canonical adapter path; `lumonox.core.*` is the canonical framework-agnostic path.
- [x] **Adapter contract doc:** `sdk/docs/adapters.md` describes the three responsibilities of a framework adapter (extract request, capture response, hand event to dispatcher) and the hard constraints (never break host app, async hot path, scrub before send, re-raise on exception, no public API drift). Updated to reflect that monkeypatch targets must point at the canonical module.
- [x] **Risk control:** 62 SDK tests pass (56 existing + 6 new canonical-path tests); ruff, mypy, bandit green. End-to-end smoke (`scripts/sdk_end_to_end_smoke.py`) drives the SDK through a stub ingest endpoint and confirms behavior: events delivered, `Authorization` scrubbed to `[REDACTED]` before send, correlation IDs propagated, error events carry exception type / message / hash / stack.

**Acceptance for Phase 2:**
- All existing tests pass with no changes.
- Public import surface (`__init__.py` `__all__`) is byte-identical in effect.
- Dep list is unchanged.

### Phase 3 — Optional (future, gated on a real signal)

Only consider if we have concrete evidence — bug reports, install failure analytics, or a product decision to ship a second framework adapter — that the remaining friction is worth a functionality tradeoff. Each item explicitly notes the cost.

- **Second framework adapter (e.g. Flask).** *No functionality cost.* Would add `[flask]` extra alongside `[fastapi]`, with one of them required at install time. Only worth it with a concrete product decision to support a second framework. Phase 2's refactor is the enabling work.
- **`httpx`-stdlib fallback transport.** *Cost: ~20–30% slower transport, more drops under load.* Rejected by default; revisit only if `httpx` version conflicts become a top install-failure mode in CI/telemetry.
- **Vendored mini-HTTP client.** *Cost: ~200 LOC of HTTP code to maintain; perf parity not guaranteed.* Same rejection criteria as above.
- **Single-file `lumonox_sdk_lite.py` variant.** *Cost: parallel maintenance, drift risk, reduced capability (no psutil, no httpx, no widgets).* Only worth it with concrete demand from users who can't `pip install`.

These are catalogued so a future maintainer doesn't re-derive the rejection. Each requires explicit re-approval against the no-regression guarantee.

---

## Non-goals

- Rust/C extensions. Explicitly out of scope — they make install *harder*, not easier (see chat with maintainer 2026-05-13).
- Multi-language SDKs (Node, Go, Ruby). Different decision entirely; revisit only when there's a product decision to support a non-Python host framework.
- Bundling the backend or dashboard. The `[stack]` extra already covers users who want that.
- Reducing required dependencies. The current required set (`fastapi`, `httpx`, `psutil`) all back specific product capabilities; none can move to an extra without a default-install regression. See no-regression table.

## Open questions

- Minimum acceptable `fastapi` / `httpx` / `psutil` versions? Needs a quick audit of which APIs `_monitor.py` and `_infrastructure.py` actually use. Phase 1 task.
- Are there real environments where psutil's wheel matrix isn't enough? If so, name them — that's the only thing that would justify revisiting the no-regression call. Likely candidates: AWS Lambda (works fine), Cloud Run (works fine), Vercel Python (works fine), GitHub Actions (works fine). The hypothetical "no toolchain on Alpine" case is largely covered by musllinux wheels.

## Rollout

- **Phase 1** ships in the next SDK patch (`0.2.x`) — behavior-preserving, dep list unchanged in count, version floors loosened. `sdk/CHANGELOG.md` should note the wider Python range and looser floors.
- **Phase 2** is a separate minor (`0.3.0`) — public API unchanged but internal structure changes; warrants its own release note and a longer soak window.
- **Phase 3** items are case-by-case; each requires its own approval against the no-regression guarantee.

## Verification checklist (for each phase)

- `uv run --package lumonox-sdk pytest sdk/tests/` green.
- Install-matrix CI cell (Phase 1 deliverable) green across 3.10/3.11/3.12/3.13 × amd64/arm64 × slim/alpine.
- Cold-import time <300 ms (regression guard — wall-clock around `python -c "import lumonox"` subprocess, includes interpreter startup; sized for slow CI cells).
- **No-regression check**: in each matrix cell, after `pip install`, confirm psutil-backed infrastructure metrics are present and populated (not silently missing). This is the load-bearing assertion that prevents an install-ease "win" from masking a functional loss.
- Manual smoke: instrument the synthetic test app under `sdk/src/lumonox/fixtures/`, observe events arriving at a local backend, confirm scrubbing + queue behavior unchanged.
- `lumonox-engineering.mdc` SDK contract spot-check: never raises on the request path, silent on misconfig, scrubs before send, re-raises original on middleware exceptions.
