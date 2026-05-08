# AutoPulse 🚀

> ⚡ FastAPI observability you can wire up in minutes, with enough depth for serious backends when you grow into it.

**AutoPulse** is an opinionated stack for Python teams: SDK middleware captures requests and errors without blocking your app; a backend ingests and stores high-volume telemetry; the dashboard favors quick answers—what broke, when it broke, and what traffic surrounded it—over building your own Grafana.


<img width="1440" height="813" alt="image" src="https://github.com/user-attachments/assets/6d0ca05d-418e-47eb-86ec-3f367cbff8d1" />


📊 You can also **ship custom dashboard panels from your app**: define cards, line charts, bar charts, donuts, histograms, scatter plots, and stacked areas in code (`dashboard_widgets=...` on `autopulse()`), and they appear beside the built-in views—useful for SLIs, business counters, or anything you want operators to see next to requests and errors.

🛡️ Ship a working setup fast; keep **sampling**, **privacy controls**, **dashboard auth** (magic link, domains, OIDC), **multi-channel alerting**, **DuckDB-backed event storage**, and **optional host metrics** in your back pocket for larger installs.

---

**🏭 Running in production?** Use the **[Production deployment guide](./docs/ops/PRODUCTION_DEPLOYMENT.md)** — TLS, databases, scaling, static UI export, scheduler/jobs, and operational defaults.

---

## Contents

- ✨ [Quickstart](#quickstart)
- 📊 [Custom dashboard widgets](#custom-dashboard-widgets)
- ⚙️ [Runtime modes](#runtime-modes)
- 🔐 [Auth and options](#auth-and-options)
- 🌍 [Environment reference](#environment-reference)
- 🛠️ [Develop AutoPulse from this repo](#develop-autopulse-from-this-repo)

---

## Quickstart ✨

### Instrument your FastAPI app 🚀

Three steps: install the SDK, set ingest URL + project key, add one middleware call. Sending stays async and bounded; failures are quiet by default so a bad observability rollout cannot take down production.

```bash
pip install autopulse
```

```python
from fastapi import FastAPI
from autopulse import autopulse

app = FastAPI()
autopulse(app)
```

```bash
export AUTOPULSE_INGEST_URL="http://127.0.0.1:8000/ingest"   # or https://your-host/your-mount/ingest
export AUTOPULSE_API_KEY="<project ingest key from dashboard>"
```

🔑 Copy the ingest key from the dashboard (project settings / onboarding).

### Sanity-check ingest 🧪

```bash
export INGEST_KEY='<project ingest key>'
./scripts/examples/ingest_sample_event.sh
```

✅ Expect **HTTP 202**. Refresh the dashboard to see the event.

---

## Custom dashboard widgets 📊

Pass `dashboard_widgets=(...)` into `autopulse()`. Built-in types include `CardWidget`, `LineChartWidget`, `BarChartWidget`, `DonutChartWidget`, `HistogramWidget`, `ScatterPlotWidget`, and `StackedAreaWidget`. The backend merges them into the dashboard so teams see **your** KPIs next to AutoPulse traffic and errors—no separate “dashboard builder” product to learn.

```python
from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from autopulse import CardWidget, LineChartWidget, autopulse

app = FastAPI()
autopulse(
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

- Widget definitions: `sdk/src/autopulse/widgets.py`
- Rich demo fixture: `sdk/src/autopulse/fixtures/synthetic_test_app.py` (`_build_demo_dashboard_widgets`)
- UI showcase: `/autopulse/ui/widgets-showcase`

---

## Runtime modes ⚙️


| Use case                          | What to run                                 | When to use                                                                                                                                                          |
| --------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **🏗️ Full local stack**          | `./scripts/run_synthetic_stack.sh`          | End-to-end demo or integration work: API on `:8000`, synthetic FastAPI app on `:8001`, dashboard (static mount or Next sidecar per `AUTOPULSE_FRONTEND_MODE`).       |
| **🖥️ Backend only**              | `uv run python -m autopulse_backend.main`   | Run the ingest + dashboard API without the Next dev server—automation, headless testing, or pairing with your own UI.                                                |
| **🔥 API + Next with hot reload** | Backend + `npm --prefix frontend run dev`   | Frontend iteration: HMR on the dashboard while the API serves JSON; point `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL` (and related `NEXT_PUBLIC_`* vars) at the API origin. |
| **📈 Synthetic load**             | `./scripts/examples/synthetic_load_demo.sh` | Generate realistic mixed traffic against the sample app; override `BASE_URL`, `DURATION_MINUTES`, `TARGET_REQUESTS`, `ROLE_MODE`, or `SCENARIO` as needed.           |


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
export ALERT_EMAIL_FILE_OUTBOX_DIR=./.autopulse/emails
```

### Multi-channel alerts 📣

**Channels:** `file`, `smtp`, `smtp_localhost`, `sendmail`, `resend`, `postmark`, generic `webhook`, `slack`, `discord`, `composite`, and `stub`.

**Primary knobs:** `ALERT_SENDER_MODE`, `ALERT_EMAIL_PROVIDER` + `ALERT_EMAIL_`*, `ALERT_WEBHOOK_URL`, `ALERT_SLACK_WEBHOOK_URL`, `ALERT_DISCORD_WEBHOOK_URL`.

Details: [backend/ALERT_DELIVERY_RUNBOOK.md](./backend/ALERT_DELIVERY_RUNBOOK.md).

### SDK: `autopulse(app, **kwargs)` 🎛️

Remote mode is the default: set `AUTOPULSE_INGEST_URL` and `AUTOPULSE_API_KEY` (or pass `ingest_url` / `api_key`). Tune batching, privacy, and volume from code or environment.


| Parameter                                                                           | Purpose                                                                                   |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `api_key`, `ingest_url`                                                             | Override environment                                                                      |
| `service_name`, `environment`                                                       | Labels on every event                                                                     |
| `queue_maxsize`, `batch_size`, `flush_interval_s`, `max_retries`, `retry_backoff_s` | Sender batching and backoff                                                               |
| `debug`                                                                             | Verbose SDK logging (`AUTOPULSE_DEBUG`)                                                   |
| `capture_headers`, `capture_query_params`, `scrub_keys`                             | Privacy and capture policy                                                                |
| `request_sample_rate`, `ignore_path_prefixes`                                       | Traffic shaping                                                                           |
| `dashboard_widgets`                                                                 | Custom dashboard cards and charts ([Custom dashboard widgets](#custom-dashboard-widgets)) |
| `capture_infrastructure_metrics`, `infrastructure_probe_interval_ms`                | Optional host metrics                                                                     |


---

## Environment reference 🌍


| Area                  | Highlights                                                                                                                                                                                                                                                                                                                       | Full lists                                                                               |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **📘 SDK**            | `AUTOPULSE_API_KEY`, `AUTOPULSE_INGEST_URL` / `AUTOPULSE_ENDPOINT`, batching (`AUTOPULSE_BATCH_MAX_EVENTS`, `AUTOPULSE_FLUSH_INTERVAL_SECONDS`, `AUTOPULSE_MAX_QUEUE_SIZE`), `AUTOPULSE_DEBUG`, `AUTOPULSE_REQUEST_SAMPLE_RATE`, `AUTOPULSE_IGNORE_PATH_PREFIXES`, `AUTOPULSE_CAPTURE_HEADERS`, `AUTOPULSE_CAPTURE_QUERY_PARAMS` | [sdk/README.md](./sdk/README.md)                                                         |
| **🗄️ Backend**       | `DATABASE_URL`, `AUTOPULSE_EVENT_STORE`, `AUTOPULSE_DUCKDB_PATH`, `AUTOPULSE_DATA_DIR`, `DASHBOARD_AUTH_`*, `ALERT_`*, `INGEST_*`, `JOBS_*`, dashboard rate limits                                                                                                                                                               | [backend/.env.example](./backend/.env.example), [backend/README.md](./backend/README.md) |
| **📱 Frontend build** | `NEXT_PUBLIC_AUTOPULSE_API_BASE_URL`, `NEXT_PUBLIC_AUTOPULSE_FRONTEND_MODE`, related `NEXT_PUBLIC_`* toggles                                                                                                                                                                                                                     | [frontend/.env.example](./frontend/.env.example)                                         |


📖 For architecture, event shapes, and scope boundaries: [DEVELOPMENT.md](./DEVELOPMENT.md).

---

## Develop AutoPulse from this repo 🛠️

🔧 Fork or clone AutoPulse when you want to **shape it to your org** — extend widgets, ingest rules, retention, alert channels, or dashboard behavior without fighting a black-box SaaS installer.

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

💡 Then open the dashboard (`http://127.0.0.1:8000/autopulse/ui/dashboard/` when serving the static export from the backend, or the Next dev URL printed if you run in sidecar mode), sign in, and copy an ingest key for experiments.

🚦 Optional traffic against the sample app (`:8001`):

```bash
./scripts/examples/synthetic_load_demo.sh
```

Core validation commands from repository root:

```bash
make check
make release-gates
```

**Production rollout** stays documented in **[Production deployment →](./docs/ops/PRODUCTION_DEPLOYMENT.md)** and the focused docs index **[docs/README.md](./docs/README.md)**.
