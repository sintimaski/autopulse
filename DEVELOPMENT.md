# AutoPulse Development Brief

AutoPulse is a plug-and-play observability product for FastAPI applications. The core promise is:

> Useful visibility into a FastAPI app in two minutes, without learning observability infrastructure.

This document is the cleaned development source of truth.

## Product Positioning

AutoPulse is not a general-purpose Grafana, Datadog, or Sentry replacement. It is an opinionated, Python-native tool for solo developers, indie hackers, and small backend teams that want instant insight into API traffic, errors, and latency.

Primary wedge:

- Zero-config setup.
- FastAPI-first integration.
- Useful defaults instead of dashboards and query languages.
- Logs, request metrics, and errors in one simple view.
- Designed for small teams that do not want DevOps overhead.

Ideal user:

- Solo developer or indie hacker shipping a FastAPI app.
- Small backend team of 1-5 people.
- Developer who does not want to configure Prometheus, Grafana, agents, log pipelines, or complex Sentry/Datadog settings.

Product rule:

> If a feature makes the user think like an observability engineer, it does not belong in the MVP.

## MVP Goal

The MVP should answer one question:

> What broke, when did it break, and what requests led to it?

The first version should make it easy to see:

- Recent HTTP requests.
- Request rate.
- Error rate.
- Average latency.
- Exceptions with stack traces.
- Simple email alerts for major failures.

## MVP Feature Scope

### Must Have

SDK:

- FastAPI middleware.
- One-line integration.
- Automatic request capture:
  - Method.
  - Path.
  - Status code.
  - Latency.
  - Timestamp.
  - Exception details when available.
- Async, non-blocking buffering.
- Background batch sender.
- Retry with bounded attempts.
- Silent failure when AutoPulse is unavailable.
- Default sensitive data scrubbing.

Backend:

- Authenticated ingestion endpoint.
- Event validation.
- Project API key lookup.
- Raw event storage.
- Basic per-minute metric aggregation.
- Basic error grouping by hash.

Dashboard:

- Overview page with requests/minute, error rate, and average latency.
- Recent requests table.
- Errors page with grouped stack traces, counts, and last-seen timestamps.

Alerts:

- Email alert on error spikes.
- Email alert on possible service outage using a simple heuristic.

**Layered capabilities:** The shipped codebase may expose organization governance, OIDC sign-in, extended retention presets, SQL-scoped filters, or multi-channel alerts. Treat these as **progressive disclosure** on the default diagnosis path; they extend the MVP goal above rather than replacing it, unless maintainers explicitly widen scope.

### Build Soon After MVP

- Background job tracking.
- Cron monitoring.
- Smarter error grouping.
- Route/status/error filtering.
- Ignore-list defaults for health checks.
- Slack or Discord alerts.
- Request sampling.

### Explicit Non-Goals For MVP

- Distributed tracing.
- Custom dashboard builder.
- Query language.
- Complex alert rules.
- Kubernetes integrations.
- Multi-cloud integrations.
- Log transformation pipelines.
- Full APM agent behavior.
- Enterprise permissions and audit logs.

## Recommended Architecture

Start as hosted SaaS. Add self-hosting later only if there is clear demand.

```
FastAPI App
  |
  | AutoPulse SDK middleware
  v
In-memory async buffer
  |
  | background batch sender
  v
HTTPS ingestion API
  |
  v
Validation and processing
  |
  v
Postgres storage
  |
  v
Dashboard API
  |
  v
Next.js dashboard
```

## Recommended Tech Stack

### Storage note (local dev defaults)

- Keep relational metadata (projects, keys, UI settings, alerts) in SQL (`DATABASE_URL`).
- Store high-volume raw events in DuckDB by default (`AUTOPULSE_EVENT_STORE=duckdb`).
- **DuckDB file path:** relative `AUTOPULSE_DUCKDB_PATH` values are anchored to the **AutoPulse data root** (monorepo checkout root, or `AUTOPULSE_DATA_DIR` / `AUTOPULSE_PROJECT_ROOT`), not the process cwd—so ingest, dashboard queries, retention, and CLI jobs always open the same file. See `normalize_event_store_duckdb_path` / `resolve_autopulse_data_root` in `backend/src/autopulse_backend/core/config.py` and `docs/ops/BACKUP_RESTORE.md` (migration note if you previously relied on cwd-relative files).
- Preserve dashboard API contracts while event reads migrate behind an event-store abstraction.
- Keep a `sqlite` event-store fallback mode for rollout safety.
- **Production rollout:** topology, health probes, SLO budgets, backups, and drills are summarized in **[docs/ops/PRODUCTION_DEPLOYMENT.md](./docs/ops/PRODUCTION_DEPLOYMENT.md)** (canonical; use it instead of piecing ops docs ad hoc).

SDK:

- Python.
- FastAPI / Starlette middleware.
- `asyncio.Queue` for bounded buffering.
- `httpx.AsyncClient` for background delivery.

Backend:

- FastAPI.
- Pydantic for payload validation.
- SQL database (Postgres in hosted stacks, SQLite for local defaults) for **metadata** (projects, hashed API keys, sessions), **aggregates** (metric buckets, error groups), and alert state.
- High-volume **raw events** via the configured event store (DuckDB by default; see storage note above), abstracted behind the event-store layer—not “all raw rows in Postgres” unless you operate a custom deployment.
- SQLAlchemy ORM models today; SQLModel is optional future polish.
- Background tasks or a simple worker loop for aggregation.

Frontend:

- Next.js.
- Lightweight chart library.
- Simple server-rendered or API-backed dashboard pages.

Infrastructure:

- Start with a single-region VPS or simple managed app platform.
- Managed Postgres if possible.
- HTTPS-only public ingestion.
- Add Redis/queue infrastructure only after Postgres and in-process workers become insufficient.

## Developer Experience

Ideal integration:

```python
from fastapi import FastAPI
from autopulse import monitor

app = FastAPI()
monitor(app)
```

Optional explicit configuration:

```python
monitor(
    app,
    api_key="ap_live_...",
    service_name="billing-api",
    environment="production",
)
```

DX principles:

- One-line setup should work.
- No config file required.
- Environment variables are supported but not required for local use.
- Local development should degrade gracefully, such as console output or no-op mode.
- Missing or invalid AutoPulse configuration must never break the user's app.
- Documentation should fit on one page for the MVP.

## SDK Behavior

The SDK must be safe to install in production apps. It should never make the observed application depend on AutoPulse availability.

Request lifecycle:

1. Middleware starts a timer.
2. Request is passed to the FastAPI app.
3. Middleware captures response status and latency.
4. If an exception occurs, middleware captures exception type, message, and stack trace, then re-raises the original exception.
5. Event is pushed to a bounded async queue.
6. Background sender flushes batches to the ingestion API.

Buffering:

- Use an in-memory bounded queue, for example `asyncio.Queue(maxsize=1000)`.
- If the queue is full, drop the event.
- Dropping observability data is acceptable; blocking the user app is not.

Batching:

- Flush when either condition is met:
  - Batch reaches a configured size, for example 50-100 events.
  - Flush interval elapses, for example 2 seconds.
- Use gzip later if payload size becomes an issue.

Failure handling:

- Retry transient failures with exponential backoff.
- Keep max retries low, for example 3.
- Drop the batch after retries are exhausted.
- Do not log noisy errors by default in user applications.
- Provide optional debug mode for SDK troubleshooting.

Performance targets:

- SDK overhead: under 1 ms per request in the common path.
- Memory usage: bounded by queue size and batch size.
- Network usage: batched only, never one request per event.

## Event Model

Start with a small number of event types.

### Request Event

```json
{
  "type": "request",
  "timestamp": "2026-04-26T11:00:00Z",
  "service_name": "api",
  "environment": "production",
  "method": "GET",
  "path": "/users/{id}",
  "status_code": 200,
  "latency_ms": 42.3,
  "request_id": "optional-request-id"
}
```

### Error Event

```json
{
  "type": "error",
  "timestamp": "2026-04-26T11:00:00Z",
  "service_name": "api",
  "environment": "production",
  "method": "GET",
  "path": "/users/{id}",
  "status_code": 500,
  "latency_ms": 12.8,
  "exception_type": "ValueError",
  "exception_message": "invalid user id",
  "stack_trace": "...",
  "error_hash": "stable-hash"
}
```

Prefer route templates over raw paths when possible, for example `/users/{id}` instead of `/users/123`, to reduce cardinality.

## Ingestion API

### `POST /ingest`

Receives event batches from the SDK.

Headers:

```http
Authorization: Bearer <api_key>
Content-Type: application/json
```

Body:

```json
{
  "events": []
}
```

Responsibilities:

- Authenticate the API key.
- Resolve the project.
- Validate event schema.
- Normalize timestamps.
- Attach server-side metadata:
  - Project ID.
  - Received timestamp.
  - SDK version.
- Store raw events.
- Trigger or perform basic aggregation.

Response:

```json
{
  "accepted": 42
}
```

The ingestion endpoint should be fast. Expensive grouping, alerting, and aggregation can be moved to workers as the product grows.

## Storage Model

Use Postgres plus JSONB for the MVP. Avoid a time-series database until there is real scale pressure.

### Suggested Tables

`projects`:

- `id`
- `name`
- `created_at`

`api_keys`:

- `id`
- `project_id`
- `key_hash`
- `created_at`
- `revoked_at`

`events`:

- `id`
- `project_id`
- `timestamp`
- `received_at`
- `type`
- `service_name`
- `environment`
- `method`
- `path`
- `status_code`
- `latency_ms`
- `payload` JSONB

`metric_buckets`:

- `id`
- `project_id`
- `service_name`
- `environment`
- `minute_bucket`
- `request_count`
- `error_count`
- `latency_sum_ms`
- `latency_count`
- `avg_latency_ms`

`error_groups`:

- `id`
- `project_id`
- `service_name`
- `environment`
- `error_hash`
- `exception_type`
- `message_fingerprint`
- `count`
- `first_seen`
- `last_seen`
- `sample_event_id`
- `sample_payload` JSONB

Indexes to add early:

- `events(project_id, timestamp DESC)`
- `events(project_id, type, timestamp DESC)`
- `events(project_id, path, timestamp DESC)`
- `metric_buckets(project_id, minute_bucket DESC)`
- `error_groups(project_id, last_seen DESC)`
- Unique index on `error_groups(project_id, service_name, environment, error_hash)`.

Retention:

- Keep raw events for 7-14 days on early paid plans.
- Keep aggregated metrics longer.
- Make retention a pricing lever later.

## Dashboard Requirements

The dashboard is the product experience. Optimize for fast diagnosis, not configurability.

### Overview

Must show:

- Requests per minute graph.
- Error rate graph or stat.
- Average latency graph or stat.
- Top failing routes.
- Recent errors.

Core question:

> Can a developer understand what is broken in five seconds?

### Requests

Table columns:

- Time.
- Method.
- Path.
- Status.
- Latency.
- Service.
- Environment.

Filters:

- Time range.
- Status code.
- Route.
- Environment.

### Errors

Grouped errors should show:

- Exception type.
- Short message.
- Affected route.
- Count.
- First seen.
- Last seen.
- Sample stack trace.

## Alerts

Start with email.

Initial alert types:

- Error spike: error rate crosses a simple threshold over a short window.
- Service outage: no successful requests or repeated 5xx responses over a window.

Keep alert configuration minimal:

- Enabled or disabled.
- Destination email.
- Default thresholds.

Avoid complex alert builders in the MVP.

## Security And Privacy

AutoPulse may receive sensitive application metadata. Default behavior must be conservative.

Never capture by default:

- Authorization headers.
- Cookies.
- Passwords.
- Tokens.
- Full request bodies.
- Full response bodies.

Default scrub keys:

- `authorization`
- `cookie`
- `set-cookie`
- `password`
- `passwd`
- `secret`
- `token`
- `api_key`
- `apikey`
- `access_token`
- `refresh_token`

Security requirements:

- HTTPS only.
- API key authentication for ingestion.
- Store API keys hashed, not plaintext.
- Scrub sensitive values in the SDK before sending.
- Allow custom scrub rules.
- Allow disabling body/query capture.
- Do not capture request bodies in the MVP unless explicitly enabled.

## Competitive Notes

Sentry:

- Strong error tracking and grouping.
- Weakness for this niche: setup and UI can feel heavy; request-level visibility is not the core experience.

Datadog:

- Powerful full observability platform.
- Weakness for this niche: overkill, expensive, and requires infra knowledge.

Better Stack / Logtail:

- Cleaner logging experience.
- Weakness for this niche: not FastAPI-native and still requires users to think about log shipping or pipelines.

AutoPulse assumption:

> The user refuses to configure observability.

This assumption should guide product, documentation, dashboard design, SDK behavior, and pricing.

## Pricing Direction

Keep pricing simple while validating demand.

Possible starting tiers:

- Free: one project, limited event retention.
- Starter: around $10/month, more logs and email alerts.
- Pro: around $25/month, multiple services/projects and longer retention.

Avoid complex usage-based pricing in the beginning.

## Build Order

1. Create Python SDK package skeleton.
2. Implement FastAPI middleware.
3. Capture request and error events.
4. Add bounded async queue.
5. Add background batch sender.
6. Build `POST /ingest`.
7. Add API key authentication.
8. Store raw events in Postgres.
9. Build a minimal dashboard API.
10. Build overview dashboard.
11. Add request list.
12. Add grouped error view.
13. Add basic per-minute aggregation.
14. Add email alerts.
15. Add retention cleanup.
16. Add SDK benchmarks.

The first shippable milestone is:

> Install SDK, make requests, see recent requests and errors in the dashboard.

Aggregation and alerts can improve after that core loop works.

## Engineering Risks

SDK slows user app:

- Use async middleware, bounded queues, batching, and benchmarks.

AutoPulse outage affects user app:

- Fail silently and drop events after bounded retries.

Data volume grows too quickly:

- Add sampling, retention limits, route normalization, and health-check filtering.

Sensitive data leakage:

- Scrub in SDK, keep body capture off by default, and hash API keys.

Dashboard becomes too complex:

- Keep fixed views and opinionated defaults.

Storage model becomes expensive:

- Use retention windows, aggregate metrics, and postpone long raw-event retention.

## Where to invest engineering (technical leverage)

This is where depth pays off. The product does not win because the stack is exotic; it wins when the boring path is fast, safe, and predictable.

### 1. SDK buffering strategy

The most critical component. A bad SDK (blocks the event loop, grows memory unbounded, or crashes on send failures) kills trust immediately.

Invest here first:

- **Bounded queue** — cap memory and backpressure explicitly.
- **Drop strategy** — when full, drop observability data, never stall the app (document this behavior).
- **Background flush** — batch sends off the hot request path; fixed batch size and time-based flush.

Measure overhead early (microbenchmarks, real FastAPI load tests). Treat SDK quality as a release gate.

### 2. Smart sampling

Control cardinality and volume before Postgres or costs become the story:

- **Ignore noise by default** — e.g. `/health`, `/ready`, static assets (configurable later).
- **Sample high-frequency endpoints** — fixed-rate or adaptive sampling for routes that dominate volume while still surfacing errors at full fidelity where possible.

Sampling is a product feature disguised as infrastructure: fewer events, same “what broke?” answer.

### 3. Error grouping

Basic grouping delivers outsized perceived value:

- **Hash stack traces** (normalized frames, strip volatile lines where safe) into a stable `error_hash`.
- **Group similar errors** — one row per group with count, first/last seen, sample trace.

This feels intelligent without building a full issue-tracking or ML pipeline.

### 4. Data model simplicity

Resist premature platform complexity:

- **Postgres + JSONB** is enough for MVP and early scale; iterate on indexes and retention.
- **Defer** Kafka, dedicated time-series DBs, and distributed tracing backends until ingestion volume or query patterns force the issue.

The clever move is a schema you can evolve and queries you can explain — not a diagram with ten boxes.

## Where the product wins (not Rust, not sockets)

Long-term, a Rust sidecar or WebSockets can matter. The wedge that gets users and keeps them is product and UX, not transport alone.

### 1. Instant gratification

Target: install → first real data in the dashboard in **seconds** (order of tens of seconds, not a workshop).

- One-line integration.
- Clear “you are receiving events” signal in the UI.
- No mandatory multi-step setup before value.

### 2. Opinionated defaults

“No config” means the product chooses good defaults:

- Auto-ignore noisy routes where safe.
- Auto-group errors and surface top issues.
- Auto-surface request rate, error rate, and latency without building a dashboard.

Users should feel guided, not asked to design observability.

### 3. Clarity over power

Avoid positioning around “query anything.” Lead with:

- **“Here’s what’s broken”** — grouped errors, recent failing requests, simple time context.

Power users can graduate to filters and search later; the MVP wins on diagnosis speed, not SQL-for-logs.

## Future development

Post-MVP directions worth tracking; not required to validate the core loop.

### 1. Local agent (sidecar)

**Idea:** instead of the SDK sending directly to AutoPulse over the internet on every batch:

```
FastAPI app  →  local agent  →  AutoPulse backend
```

The app talks to a process on `localhost` (or a Unix socket); the agent owns outbound HTTPS.

**Why it is a strong long-term play:**

- **Batching and compression** — agent can coalesce traffic from multiple workers, gzip payloads, and reuse connections without coupling that logic to Python’s event loop.
- **Retries and backoff** — network policy lives in one place; the app stays dumb and fast.
- **Operational fit** — one agent per host or per container can serve several processes; easier firewall rules (egress from agent only).
- **Language-agnostic path** — same agent could eventually accept OTLP-like or JSON from other runtimes.

A **Rust** (or otherwise native) agent is a reasonable implementation choice for CPU-efficient serialization, compression, and long-lived connection handling. It is an optimization and deployment story, not the initial reason someone adopts AutoPulse.

**Tradeoffs:** extra install step, versioning the agent with the SDK, and debugging “app vs agent” when misconfigured. Keep direct SDK → `POST /ingest` as the default until agent demand is clear.

### 2. WebSockets

**Dashboard:** push live updates (metrics, new errors, request tail) instead of polling. Improves “something just broke” UX.

**Ingestion (optional, much later):** persistent channel from agent or long-lived services — usually still pair with HTTP ingest for simplicity and firewalls.

**Caveats:** connection lifecycle, auth, reconnect, and horizontal scaling (sticky sessions or shared pub/sub) add backend complexity. Treat as a **post–product-market-fit** enhancement unless a specific customer segment demands live views early.

## Definition Of Done For MVP

The MVP is ready to launch when:

- A FastAPI developer can integrate AutoPulse with one line.
- Requests appear in the dashboard within a few seconds.
- Exceptions are grouped and visible with stack traces.
- Basic request rate, error rate, and latency are visible.
- SDK failure does not affect the user app.
- Sensitive headers and common secret fields are scrubbed by default.
- Email alerts work for simple error spikes.
- Email alerts work for simple outage heuristics.
- Setup documentation is short enough to read in a few minutes.
