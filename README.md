<div align="center">

# 🪄 Lumonox

#### Observability for FastAPI and Django apps in minutes — know what broke, when, and which requests caused it.

[![PyPI – lumonox](https://img.shields.io/pypi/v/lumonox?label=lumonox&color=3776AB&logo=pypi&logoColor=white)](https://pypi.org/project/lumonox/)
[![PyPI – lumonox-sdk](https://img.shields.io/pypi/v/lumonox-sdk?label=lumonox-sdk&color=3776AB&logo=pypi&logoColor=white)](https://pypi.org/project/lumonox-sdk/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://pypi.org/project/lumonox/)
[![CI](https://img.shields.io/github/actions/workflow/status/sintimaski/lumonox/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/sintimaski/lumonox/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/sintimaski/lumonox?color=brightgreen)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/sintimaski/lumonox?style=social)](https://github.com/sintimaski/lumonox/stargazers)

<br />

[![Live demo](https://img.shields.io/badge/▶%20Live%20demo-Hugging%20Face%20Space-FF9D00?style=for-the-badge)](https://sintimaski-lumonox-demo.hf.space)
[![Quickstart](https://img.shields.io/badge/⚡%20Quickstart-3%20steps-2EA043?style=for-the-badge)](#quickstart)
[![Docs](https://img.shields.io/badge/📖%20Docs-DEVELOPMENT.md-1F6FEB?style=for-the-badge)](./DEVELOPMENT.md)

<br />

![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?logo=duckdb&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)

<br /><br />

<a href="https://sintimaski-lumonox-demo.hf.space"><img alt="Lumonox dashboard overview" src="https://github.com/user-attachments/assets/6d0ca05d-418e-47eb-86ec-3f367cbff8d1" width="900" /></a>

</div>

---

> **Self-hosted, MIT-licensed.** Lumonox is a complete observability stack — Python SDK, FastAPI ingest API, and Next.js dashboard — that you run on your own infrastructure. One wheel ships the API with the dashboard bundled inside. Issues, forks, and contributions are welcome.

Lumonox gives Python teams a fast path to useful production visibility without observability-infra overhead. It instruments both **FastAPI** and **Django** apps — and the Lumonox API itself is a FastAPI service under the hood.

> **▶️ Try it live:** a seeded, self-refreshing demo runs at **[sintimaski-lumonox-demo.hf.space](https://sintimaski-lumonox-demo.hf.space)** — sign in with `demo@lumonox.dev` (the magic link is shown inline, no email needed). Setup notes: [`docs/ops/HUGGINGFACE_SPACE.md`](./docs/ops/HUGGINGFACE_SPACE.md).

---

## Highlights ✨

|   |   |
| :--- | :--- |
| 🚀 **Drop-in middleware** | One call instruments your FastAPI or async Django app. The SDK is bounded and async — a misconfigured Lumonox cannot block your hot path. |
| 🔍 **Five-second triage** | Overview → Diagnosis → Requests with a shared **`correlation`** scope across requests, errors, and background jobs (honors `X-Request-ID` / `X-Correlation-ID`). |
| 📊 **Custom widgets** | Push your own KPIs from your SDK code. Seven built-in chart types, rendered next to Lumonox traffic and errors — no separate dashboard builder to learn. |
| 📣 **Multi-channel alerts** | Error spike + outage detection to email (SMTP, Resend, Postmark, sendmail), Slack, Discord, or generic webhooks. |
| 🔐 **Self-hosted control** | Magic-link or OIDC auth, multi-project organisations, 4-role RBAC (viewer / member / admin / owner), configurable retention and storage. |
| 📦 **One install, one process** | `pip install lumonox` — the Next.js dashboard is bundled inside the Python wheel. Postgres + DuckDB, or all-SQLite for trivial deploys. |

---

## Contents

- ▶️ [Live demo](https://sintimaski-lumonox-demo.hf.space)
- ✨ [Highlights](#highlights)
- 🚀 [Quickstart](#quickstart)
- 🧱 [Under the hood](#under-the-hood)
- 📊 [Custom dashboard widgets](#custom-dashboard-widgets)
- ⚙️ [Runtime modes](#runtime-modes)
- 🔐 [Auth and options](#auth-and-options)
- 🌍 [Environment reference](#environment-reference)
- 🛠️ [Develop Lumonox from this repo](#develop-lumonox-from-this-repo)
- 🤝 [Contributing](#contributing)
- 📦 [PyPI publishing & install links](./docs/ops/PYPI_PUBLISHING.md)
- 📄 [License](#license)

---

## Quickstart ✨

### Instrument your FastAPI app 🚀

Three steps: install the SDK, set ingest URL + project key, add one middleware call. Sending stays async and bounded; failures are quiet by default so a bad observability rollout cannot take down production.

```bash
pip install lumonox-sdk
```

```python
from fastapi import FastAPI
from lumonox import lumonox

app = FastAPI()
lumonox(app)
```

```bash
export LUMONOX_INGEST_URL="http://127.0.0.1:8000/ingest"   # or https://your-host/your-mount/ingest
export LUMONOX_API_KEY="<project ingest key from dashboard>"
```

🔑 Copy the ingest key from the dashboard (project settings / onboarding).

### Instrument your Django app 🐍

Lumonox instruments **Django** apps too, through an async middleware adapter (ASGI). The default install ships the FastAPI adapter; install the `[django]` extra to add Django, then add the middleware and wire `monitor()` + `wrap_asgi()` in `asgi.py`:

```bash
pip install "lumonox-sdk[django]"
```

```python
# settings.py
MIDDLEWARE = [
    "lumonox.django.middleware.LumonoxMiddleware",
    # ... your other middleware ...
]

# asgi.py
from django.core.asgi import get_asgi_application
from lumonox.django import monitor, wrap_asgi

monitor(api_key="...", ingest_url="https://your-host/ingest", service_name="my-django-app")
application = wrap_asgi(get_asgi_application())
```

The same `LUMONOX_*` env vars apply. `wrap_asgi()` drives the SDK dispatcher off the ASGI lifespan. The adapter is **async/ASGI-only** (classic synchronous WSGI Django is out of scope for v1). Details: [sdk/docs/adapters.md](./sdk/docs/adapters.md).

### Run the Lumonox API from another repo 🖥️

Two **PyPI** install lines. The **`lumonox`** wheel exposes **`from lumonox import mount_on_app`** (and `lumonox_backend` for the full package tree).

| What you need | One line |
|-----------------|----------|
| **API + pre-built dashboard** (wheel bundles static UI; published on pushes to `main` via `.github/workflows/publish-lumonox-pypi.yml` after PyPI trusted publishing is set up) | `pip install lumonox` or `uv add lumonox` |
| **Same as above + app SDK** (`from lumonox import lumonox` for FastAPI; add the `[django]` extra for Django) | `pip install "lumonox-sdk[stack]"` or `uv add "lumonox-sdk[stack]"` |

**Git** (always works; pin `main` to a tag or commit SHA in production):

```bash
uv add "lumonox @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=backend"
```

```bash
pip install "lumonox @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=backend"
```

```bash
uv run uvicorn lumonox_backend.main:app --host 0.0.0.0 --port 8000
```

**API + SDK from Git in one line:**

```bash
uv add "lumonox @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=backend" "lumonox-sdk @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=sdk"
```

```bash
pip install "lumonox @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=backend" "lumonox-sdk @ git+https://github.com/sintimaski/lumonox.git@main#subdirectory=sdk"
```

Use `--env-file /path/to/.env` only when that file exists. Otherwise omit it or create one (see `backend/.env.example` in the repo).

### Sanity-check ingest 🧪

```bash
export INGEST_KEY='<project ingest key>'
./scripts/examples/ingest_sample_event.sh
```

✅ Expect **HTTP 200** with `{"accepted": <n>}`.

First-ingest smoke checklist (contract-aligned):

1. Run `./scripts/examples/ingest_sample_event.sh` with a valid project key.
2. Confirm the script reports **HTTP 200** and response body includes `"accepted": 1` (or higher for larger batches).
3. Open the dashboard and verify the new event appears in Overview/Requests (live updates may appear without manual refresh; refresh if your browser tab was idle).

---

**🏭 Running in production?** Start with the **[Production deployment guide](./docs/ops/PRODUCTION_DEPLOYMENT.md)**.

---

## Under the hood 🧱

A monorepo with three real surfaces, each independently buildable:

| Surface | What it is |
| --- | --- |
| **`sdk/`** | Python SDK (PyPI: `lumonox-sdk`) — FastAPI + Django (ASGI) middleware over one shared core/adapter send path. |
| **`backend/`** | FastAPI ingest + dashboard API + background workers (PyPI: `lumonox`). One wheel also bundles the built dashboard. |
| **`frontend/`** | Next.js dashboard; default delivery is a static export mounted by the backend at `/lumonox/ui/`. |

Engineering highlights worth a look:

- **An SDK that can't take your app down.** Bounded async queue, drop-when-full backpressure, background batch sender, bounded retries plus an opt-in circuit breaker, byte-budgeted batches, and silent-failure-by-default. Sensitive headers and secret-like fields are scrubbed before anything leaves the process; the hot path targets sub-millisecond overhead.
- **Ingest kept fast.** `POST /ingest` authenticates per-project API keys (stored hashed), validates and normalizes events, and pushes heavy work off the request path. Relational metadata lives in SQL; high-volume events go to a DuckDB event store with optional Parquet cold storage and S3-compatible sync.
- **Diagnosis-first dashboard.** Opinionated Overview → Diagnosis → Requests flow with shared request-correlation scope, grouped error stack traces, incident notebooks, an operator-health surface, release markers, and multi-channel alerts (email / Slack / Discord / webhook). Auth via magic-link or OIDC.
- **Built like production software.** Fully typed (mypy), linted (Ruff) and security-scanned (Bandit); pytest across SDK + backend on both SQLite and Postgres; frontend Vitest + Playwright smoke with a bundle-size budget. `make ci` mirrors the GitHub Actions pipeline locally.

Scope and boundaries — what Lumonox deliberately does *not* try to be — are documented in **[DEVELOPMENT.md](./DEVELOPMENT.md)**.

---

## Custom dashboard widgets 📊

Pass `dashboard_widgets=(...)` into `lumonox()`. Built-in types include `CardWidget`, `LineChartWidget`, `BarChartWidget`, `DonutChartWidget`, `HistogramWidget`, `ScatterPlotWidget`, and `StackedAreaWidget`. The backend merges them into the dashboard so teams see **your** KPIs next to Lumonox traffic and errors—no separate “dashboard builder” product to learn.

```python
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from lumonox import CardWidget, LineChartWidget, lumonox

app = FastAPI()
lumonox(
    app,
    dashboard_widgets=[
        CardWidget(widget_id="n", title="Count", value=42.0, unit="n", order=10),
        LineChartWidget(
            widget_id="t",
            title="Series",
            points=[
                (datetime.now(tz=UTC) - timedelta(minutes=1), 1.0),
                (datetime.now(tz=UTC), 2.0),
            ],
            order=20,
        ),
    ],
)
```

**📚 Reference**

- Widget definitions: `sdk/src/lumonox/widgets.py`
- Rich demo fixture: `sdk/src/lumonox/fixtures/synthetic_test_app.py` (`_build_demo_dashboard_widgets`)
- UI showcase: `/lumonox/ui/widgets-showcase`

---

## Runtime modes ⚙️


| Use case                          | What to run                                 | When to use                                                                                                                                                          |
| --------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **🏗️ Full local stack**          | `./scripts/run_synthetic_stack.sh`          | End-to-end demo or integration work: API on `:8000`, synthetic FastAPI app on `:8001`, dashboard (static mount or Next sidecar per `LUMONOX_FRONTEND_MODE`).       |
| **🐍 Full local stack (Django)**  | `./scripts/run_synthetic_django_stack.sh`   | Same stack with the synthetic **Django** app on `:8001` instead of FastAPI — exercises the `lumonox.django` adapter. Thin wrapper that delegates to `run_synthetic_stack.sh`.       |
| **🖥️ Backend only**              | `uv run python -m lumonox_backend.main` (requires **`lumonox`**; [install](./backend/README.md#install-outside-the-monorepo) if you are not in this repo) | Run the ingest + dashboard API without the Next dev server—automation, headless testing, or pairing with your own UI.                                                |
| **🔥 API + Next with hot reload** | Backend + `npm --prefix frontend run dev`   | Frontend iteration: HMR on the dashboard while the API serves JSON; point `NEXT_PUBLIC_LUMONOX_API_BASE_URL` (and related `NEXT_PUBLIC_`* vars) at the API origin. |
| **📈 Synthetic load**             | `./scripts/examples/synthetic_load_demo.sh` (FastAPI) · `./scripts/examples/synthetic_django_load_demo.sh` (Django) | Generate mixed traffic against the sample app. The FastAPI driver supports `BASE_URL`, `DURATION_MINUTES`, `TARGET_REQUESTS`, `ROLE_MODE`, `SCENARIO`; the Django driver is a lighter curl loop (`BASE_URL`, `TARGET_REQUESTS`, `SLEEP_SECONDS`).           |


---

## Auth and options 🔐

### Dashboard authentication 🔑

How operators sign into the dashboard (separate from per-project ingest keys):


| Mechanism                         | Configuration                                                                 |
| --------------------------------- | ----------------------------------------------------------------------------- |
| Email allowlist (magic link)      | `DASHBOARD_AUTH_ALLOWED_EMAIL=you@example.com`                                |
| Domain allowlist                  | `DASHBOARD_ALLOWED_EMAIL_DOMAINS=example.com`                                 |
| OIDC                              | `DASHBOARD_OIDC_`* variables                                                  |
| Local dev without mail            | `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN=true` (surfaces a link in the UI) |
| Optional API-key browser fallback | `DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK=true` (default off)                    |


📬 Local email outbox (auth links and alert messages) without SMTP:

```bash
export ALERT_EMAIL_PROVIDER=file
export ALERT_EMAIL_FILE_OUTBOX_DIR=./.lumonox/emails
```

### Multi-channel alerts 📣

**Channels:** `file`, `smtp`, `smtp_localhost`, `sendmail`, `resend`, `postmark`, generic `webhook`, `slack`, `discord`, `composite`, and `stub`.

**Primary knobs:** `ALERT_SENDER_MODE`, `ALERT_EMAIL_PROVIDER` + `ALERT_EMAIL_`*, `ALERT_WEBHOOK_URL`, `ALERT_SLACK_WEBHOOK_URL`, `ALERT_DISCORD_WEBHOOK_URL`.

Details: [backend/ALERT_DELIVERY_RUNBOOK.md](./backend/ALERT_DELIVERY_RUNBOOK.md).

### SDK: `lumonox(app, **kwargs)` 🎛️

Remote mode is the default: set `LUMONOX_INGEST_URL` and `LUMONOX_API_KEY` (or pass `ingest_url` / `api_key`). Tune batching, privacy, and volume from code or environment.


| Parameter                                                                           | Purpose                                                                                   |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `api_key`, `ingest_url`                                                             | Override environment                                                                      |
| `service_name`, `environment`                                                       | Labels on every event                                                                     |
| `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s` | Sender batching and backoff                                                               |
| `debug`                                                                             | Verbose SDK logging (`LUMONOX_DEBUG`)                                                   |
| `capture_headers`, `capture_query_params`, `scrub_keys`                             | Privacy and capture policy                                                                |
| `request_sample_rate`, `ignore_path_prefixes`                                       | Traffic shaping                                                                           |
| `dashboard_widgets`                                                                 | Custom dashboard cards and charts ([Custom dashboard widgets](#custom-dashboard-widgets)) |
| `capture_infrastructure_metrics`, `infrastructure_probe_interval_ms`                | Optional host metrics                                                                     |


---

## Environment reference 🌍


| Area                  | Highlights                                                                                                                                                                                                                                                                                                                       | Full lists                                                                               |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **📘 SDK**            | `LUMONOX_API_KEY`, `LUMONOX_INGEST_URL` / `LUMONOX_ENDPOINT`, batching (`LUMONOX_BATCH_MAX_EVENTS`, `LUMONOX_FLUSH_INTERVAL_SECONDS`, `LUMONOX_MAX_QUEUE_SIZE`), `LUMONOX_DEBUG`, `LUMONOX_REQUEST_SAMPLE_RATE`, `LUMONOX_IGNORE_PATH_PREFIXES`, `LUMONOX_CAPTURE_HEADERS`, `LUMONOX_CAPTURE_QUERY_PARAMS` | [sdk/README.md](./sdk/README.md)                                                         |
| **🗄️ Backend**       | `DATABASE_URL`, `LUMONOX_EVENT_STORE`, `LUMONOX_DUCKDB_PATH`, `LUMONOX_DATA_DIR`, `DASHBOARD_AUTH_`*, `ALERT_`*, `INGEST_*`, `JOBS_*`, dashboard rate limits                                                                                                                                                               | [backend/.env.example](./backend/.env.example), [backend/README.md](./backend/README.md) |
| **📱 Frontend build** | `NEXT_PUBLIC_LUMONOX_API_BASE_URL`, `NEXT_PUBLIC_LUMONOX_FRONTEND_MODE`, related `NEXT_PUBLIC_`* toggles                                                                                                                                                                                                                     | [frontend/.env.example](./frontend/.env.example)                                         |


📖 For architecture, event shapes, and scope boundaries: [DEVELOPMENT.md](./DEVELOPMENT.md).

---

## Develop Lumonox from this repo 🛠️

🔧 Fork or clone Lumonox when you want to **shape it to your org** — extend widgets, ingest rules, retention, alert channels, or dashboard behavior without fighting a black-box SaaS installer.

📦 One install line:

```bash
./scripts/bootstrap_local.sh
```

Or use the root task runner commands:

```bash
make setup
```

▶️ One run line (backend + dashboard + synthetic FastAPI app):

```bash
./scripts/run_synthetic_stack.sh
```

Same as `make synthetic-stack` (or `make stack`). The script always runs `npm --prefix frontend run build` first, then starts the backend and sample app.

💡 Then open the dashboard (`http://127.0.0.1:8000/lumonox/ui/dashboard/` when serving the static export from the backend, or the Next dev URL printed if you run in sidecar mode), sign in, and copy an ingest key for experiments.

🚦 Optional traffic against the sample app (`:8001`):

```bash
./scripts/examples/synthetic_load_demo.sh
```

Same as `make synthetic-load` (or `make load`) once the stack is listening.

From a cold clone: `make setup`, then the two script lines above, then `curl -s http://127.0.0.1:8000/health` and `curl -s http://127.0.0.1:8000/ready` (expect `{"status":"ok"}` and a ready JSON body). Ops and drill details: [docs/README.md](./docs/README.md).

Core validation commands from repository root:

```bash
make check
make ci                 # mirrors GitHub Actions CI (SQLite + frontend jobs); see scripts/ci_local.sh
make check-python-ci  # backend CI-equivalent (requires Postgres BACKEND_TEST_DATABASE_URL)
make release-gates
```

**Backend pytest default:** `uv run pytest` at the repo root runs SDK + backend tests. Backend integration tests use an **ephemeral session SQLite file** when `BACKEND_TEST_DATABASE_URL` is unset (no local Postgres required for the default suite). Set `BACKEND_TEST_DATABASE_URL` to pin a SQLite path or use Postgres—for example the ingest idempotency test that skips on SQLite—see **`backend/README.md`** and **`backend/tests/conftest.py`**.

Same full gate as a copy-paste script (equivalent to `make release-gates`; see `scripts/release_gates.sh` for steps):

```bash
bash ./scripts/release_gates.sh
```

On success the final line is `[release-gates] all checks passed`. Optional: set `LUMONOX_RELEASE_GATES_POSTGRES=1` to include Postgres-backed pytest, or `LUMONOX_RELEASE_GATES_E2E=1` to run Playwright smoke (both are separate jobs in [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)).

#### Supported matrix and CI parity

| Surface | Supported in CI / docs | Notes |
| --- | --- | --- |
| OS | **macOS**, **Linux** (`ubuntu-latest` in CI) | Primary maintainer paths. |
| Windows | **Best effort** | Not covered in CI; WSL2 is the closest parity story. |
| Python | **3.11+** per [`backend/pyproject.toml`](./backend/pyproject.toml) `requires-python` | Use `uv sync --group dev` from repo root. |
| Node.js | **22.x** per [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) (`setup-node`) | Run `npm ci` in `frontend/` before `npm run dev` / `npm run build`. |

| Check | Local default | CI |
| --- | --- | --- |
| Full CI mirror (default: `python-sqlite` + `frontend` jobs; optional Postgres + Playwright via env) | `make ci` (`scripts/ci_local.sh`) | `.github/workflows/ci.yml` |
| Ruff, mypy, bandit, pytest | `make check` / release gates | `python-sqlite` job |
| Backend CI-equivalent gate (ruff/format/mypy/bandit/pip-audit/pytest+coverage/packaging/jobs + Postgres backend tests) | `make check-python-ci` (requires `BACKEND_TEST_DATABASE_URL=postgresql+asyncpg://...`) | `python-sqlite` + `python-postgres` jobs |
| Backend tests on Postgres | Optional (`LUMONOX_RELEASE_GATES_POSTGRES=1`) | `python-postgres` job |
| Frontend audit, lint, typecheck, test, build, bundle budget | `make check` / release gates | `frontend` job |
| Browser smoke (Playwright) | Optional (`LUMONOX_RELEASE_GATES_E2E=1`) | `browser-smoke` job |

**Production rollout** stays documented in **[Production deployment →](./docs/ops/PRODUCTION_DEPLOYMENT.md)** and the focused docs index **[docs/README.md](./docs/README.md)**. Frontend layout and contributor conventions: **[frontend/README.md](./frontend/README.md)**.

---

## Contributing 🤝

Issues, fixes, docs improvements, and platform-compat patches are welcome.

- 🐛 **Bugs / questions:** [GitHub Issues](https://github.com/sintimaski/lumonox/issues).
- 🧭 **Workflow:** [`AGENTS.md`](./AGENTS.md) is the development playbook for humans and agents alike. Product scope and architecture live in [`DEVELOPMENT.md`](./DEVELOPMENT.md).
- ✅ **Before opening a PR:** run `make ci` (or `make release-gates` for the full bar). Frontend changes also need `npm run build` in `frontend/`.
- 🍴 **Forking it for your own stack?** Start with [Develop Lumonox from this repo](#develop-lumonox-from-this-repo-).

---

## License 📄

Lumonox is released under the [MIT License](./LICENSE) — use it, fork it, learn from it.

---

<div align="center">

[Demo](https://sintimaski-lumonox-demo.hf.space) · [PyPI](https://pypi.org/project/lumonox/) · [Issues](https://github.com/sintimaski/lumonox/issues) · [DEVELOPMENT.md](./DEVELOPMENT.md) · [AGENTS.md](./AGENTS.md)

<sub>Open source. MIT licensed. ⭐ Star it if you find it useful.</sub>

</div>
