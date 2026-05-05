# AutoPulse — Production Readiness Master Audit

**Audience:** CEO, CTO, Principal Product Designer, Engineering leads, SRE
**Date:** 2026-05-05
**Status:** Engineering audit artifact (does not supersede [DEVELOPMENT.md](../DEVELOPMENT.md) without maintainer governance per [DOCUMENTATION_GOVERNANCE.md](./DOCUMENTATION_GOVERNANCE.md))
**Related:** [AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md) (prior UX/product roadmap), [PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md)

### Maintainer direction (2026-05-05)

These priorities **narrow** this audit’s backlog; they do not change code behavior until implemented or reflected in `DEVELOPMENT.md` under governance.

| Topic | Direction |
|-------|-----------|
| **Plans / billing** | **Out of scope for now** — no production gate on billing UI, plan tiers, or quota productization. |
| **Metadata database** | **SQLite first** — optimize time-to-value and embedded / single-process flows. Users must retain a **supported path to other SQL backends** (e.g. Postgres) when they outgrow SQLite or need external HA. |
| **Events / “logs and metrics” plane** | **DuckDB remains the dedicated store** for high-volume request/error telemetry and analytical access (see [PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md) storage split). |
| **Dashboard auth** | **Two acceptable modes:** (1) **Basic out of the box** — first-party session / magic link (and related defaults). (2) **Auth with the host app** — integrate with the operator’s identity layer (e.g. OIDC) when the AutoPulse stack sits behind their SSO or they proxy the dashboard. Document and test both; do not force one global enterprise IAM story for the solo path. |

---

## How to read this document

| Section | Use when |
|---------|----------|
| [Executive synthesis](#1-executive-synthesis) | Go/no-go, investor or board narrative |
| [Risk scoring model](#2-risk-scoring-model) | Prioritization and severity alignment |
| [Product & UX](#3-product--ux-audit) | IA, onboarding, positioning |
| [Backend & platform](#4-backend--platform-audit) | Reliability, scale, data correctness |
| [SDK & ingestion](#5-sdk--ingestion-audit) | Customer app safety and ingest fidelity |
| [Frontend](#6-frontend-quality-audit) | Dashboard performance and accessibility |
| [Ops & release](#7-operations--release-audit) | CI/CD, runbooks, shipping |
| [Missing features catalog](#8-missing-features-catalog) | Backlog and gap list |
| [Top 15 missing features](#9-top-15-missing-features-for-production) | Quick punch list |
| [Hardening roadmap](#10-production-hardening-roadmap-p0p1p2) | Sequenced work |
| [Decision log](#11-decision-log-scope-vs-shipped-reality) | Resolve doc/code drift |
| [Go/no-go checklist](#12-go--no-go-production-checklist) | Launch gate |

---

## 1. Executive synthesis

### 1.1 One-line verdict

**AutoPulse has a credible ingest + diagnosis core and strong engineering hygiene in places (validation, hashed keys, metrics, documented topology caveats).** The **default production posture** should optimize the **SQLite + DuckDB** path (fast time-to-value, embedded metadata, DuckDB for the event plane). **“Production ready”** still depends on explicit choices for **any** non-default topology: optional Postgres (or other) metadata DB, **DuckDB single-writer** discipline, WebSocket stickiness when horizontally scaled, scheduler explicitness where SQLite auto-magic does not apply, migration strategy, plus SDK retry/idempotency and release automation (no in-repo container, no CI browser E2E).

### 1.2 Principal product designer

- **Strength:** The product can deliver on “what broke, when, what requests” when data flows; diagnosis-oriented IA is aligned with [DEVELOPMENT.md](../DEVELOPMENT.md).
- **Risk:** **Scope narrative drift** — shipped surface (SQL-scoped queries, traces-adjacent UI, orgs/RBAC, widgets) exceeds literal MVP non-goals in `DEVELOPMENT.md`, which confuses positioning, onboarding copy, and “five second overview” discipline (see [AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md) §1, §3).
- **Risk:** **Progressive disclosure** is not yet a first-class product layer: power features are discoverable without a clear “solo default path,” increasing time-to-value for the stated ICP (solo / 1–5).

### 1.3 CTO / platform

- **Strength:** FastAPI layering, ingest guards (size, rate, optional idempotency), **SQL metadata DB (SQLite by default) + DuckDB event store** split, internal metrics and `/ready` semantics ([PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md)).
- **SQLite-first path:** Known workspace-default SQLite filenames get **scheduler auto-enabled** when `JOBS_ENABLE_SCHEDULER` is unset — good for embedded / solo time-to-value ([backend/src/autopulse_backend/core/config.py](../backend/src/autopulse_backend/core/config.py) `_is_workspace_default_dev_sqlite_file`, `jobs_enable_scheduler`).
- **Critical operational footguns:**
  - **Non–SQLite-default metadata DB (e.g. Postgres):** `JOBS_ENABLE_SCHEDULER` defaults **`false`** unless env is set — operators **must** set `JOBS_ENABLE_SCHEDULER=true` (or external cron) for in-process alert + retention ticks; this is the main “silent scheduler” risk outside the SQLite golden path.
  - **DuckDB + multiple API replicas** — shared file is not a multi-writer HA pattern for the **event plane**; docs call this out; enforcement is operational ([DEPLOYMENT_MULTI_INSTANCE.md](./ops/DEPLOYMENT_MULTI_INSTANCE.md)).
  - **WebSockets in-process** — sticky sessions or single WS replica required for correct “live” UX across replicas ([PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md) §4).
  - **Alembic on API startup** — every replica may run migrations; blast radius and race risk for DDL ([backend/src/autopulse_backend/lifespan.py](../backend/src/autopulse_backend/lifespan.py) — pattern to validate in your deploy model).

### 1.4 Principal engineer (SDK + ingest)

- **Strength:** Bounded queue, drop-when-full, scrub defaults, re-raise after capture — aligned with workspace engineering rules.
- **Gaps:** SDK retries broadly on non-401 HTTP errors; **no `Idempotency-Key` from SDK** while server supports it; possible **half-configured `monitor()`** if lifecycle hooks fail after middleware attach ([sdk/src/autopulse/_monitor.py](../sdk/src/autopulse/_monitor.py)); OTLP path may not share the same body-size streaming discipline as `POST /ingest` ([backend/src/autopulse_backend/ingestion/body_size.py](../backend/src/autopulse_backend/ingestion/body_size.py)).

### 1.5 Head of engineering / delivery

- **CI:** Strong static analysis on default path (Ruff, mypy, bandit, pip-audit, pytest) per [.github/workflows/ci.yml](../.github/workflows/ci.yml). **SQLite matrix is the primary quality signal** for the embedded story; the Postgres job should remain **green** for users who upgrade metadata DB — if its gate set is narrower than SQLite, document that as an explicit policy (see [§8.5](#85-ops--release)).
- **Release:** [scripts/release_gates.sh](../scripts/release_gates.sh) exists; Playwright journey documented as **optional** ([E2E_CORE_JOURNEY.md](./testing/E2E_CORE_JOURNEY.md)) — **no substitute in CI** for golden-path regression today.
- **Shipping:** **No `Dockerfile` in repo** (verified 2026-05-05) — teams must supply images/recipes; increases variance and onboarding friction for self-host.

---

## 2. Risk scoring model

Each finding is scored for **launch risk** (would we block GA on it?) and impact dimensions:

| Dimension | Meaning |
|-----------|---------|
| **User** | Wrong data, confusion, failed onboarding |
| **Reliability** | Outage, staleness, silent non-scheduling |
| **Security / privacy** | Auth bypass, secret leakage, CSRF/CORS misuse |
| **Ops** | Undocumented topology, failed deploy, bad LB config |

**Severity labels used below:** `Critical` | `High` | `Medium` | `Low`

---

## 3. Product & UX audit

### 3.1 Canonical promise vs shipped reality

| Source | Claim |
|--------|--------|
| [DEVELOPMENT.md](../DEVELOPMENT.md) | MVP answers “what broke, when, what requests”; non-goals include distributed tracing, query language, enterprise audit |
| Code + roadmap | Diagnosis APIs, constrained/SQL-scoped querying, traces UI, orgs/RBAC, widgets — **ahead of literal MVP doc** |

**Finding (Medium, User + Ops):** Marketing, support, and internal prioritization diverge unless **one governed narrative** is chosen (narrow MVP vs “Pro” tier vs doc update). See [§11 Decision log](#11-decision-log-scope-vs-shipped-reality).

### 3.2 Onboarding and diagnosis UX

| Topic | Severity | Notes |
|-------|----------|-------|
| First-run / empty states | Medium | Roadmap: ingest misconfig and “no data” explanations partially improved; still a differentiator vs incumbents ([AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md) §4.2) |
| Alerts split (Alerts page vs Settings) | Medium | Discoverability; consolidate or cross-link |
| Scope / filter paradigms (toolbar vs facet row) | Medium | Cognitive load; roadmap notes partial fixes |
| Naming (`/requests` vs “logs”) | Low | Support burden |
| “Five second overview” vs complexity | Medium | Legacy vs phased overview, Settings depth — roadmap §3.5, §6 |

### 3.3 Plans, billing, quotas

**Deferred — not a current production gate.** The roadmap may mention plan multipliers; treat those as **future** unless scope changes under governance. Hardening priorities in this document **do not** depend on billing or plan UX.

---

## 4. Backend & platform audit

### 4.1 Strengths

- **Data model clarity:** Configurable **SQL metadata** database (SQLite default for speed-to-value; other URLs supported) holds projects, key hashes, sessions, aggregates, etc. **DuckDB** remains the **dedicated high-volume event / analytical plane** for raw telemetry aligned with product direction ([PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md) §1).
- Composed FastAPI app: health vs ready, gzip, CORS, ingest body limits, dashboard static mount ([backend/src/autopulse_backend/app.py](../backend/src/autopulse_backend/app.py)).
- API keys: PBKDF2 hashes, constant-time verify ([backend/src/autopulse_backend/auth/api_keys.py](../backend/src/autopulse_backend/auth/api_keys.py)).
- Production config validation ([backend/src/autopulse_backend/core/config.py](../backend/src/autopulse_backend/core/config.py), tests in `test_deployment_settings.py`).
- Ingest: validation, optional HTTPS, rate limits, idempotency header path, aggregate worker with DLQ story ([backend/src/autopulse_backend/routes/ingest.py](../backend/src/autopulse_backend/routes/ingest.py), [ingest_aggregate_worker.py](../backend/src/autopulse_backend/services/ingest_aggregate_worker.py)).

### 4.2 Critical / high risks

| ID | Finding | Severity | Impact |
|----|---------|----------|--------|
| B1 | **Scheduler outside SQLite golden path:** `JOBS_ENABLE_SCHEDULER` false by default; auto-true only for known workspace default **SQLite** filenames — **Postgres (or other non-matching) metadata DB without explicit env misses full scheduler** | **Critical** (when using non-SQLite-default metadata DB and expecting in-process jobs) | Reliability — no alerts/retention tick unless explicitly enabled or external cron |
| B2 | **DuckDB file + N replicas** | **Critical** (if scaled blindly) | Reliability — lock contention / corruption class risk |
| B3 | **Migrations on every API boot** | **High** | Ops — DDL races, deploy coupling |
| B4 | **Ingest ordering:** DuckDB write before SQL aggregates/widgets — partial failure modes | **High** | Correctness — dashboard SQL vs raw store skew |
| B5 | **Distributed rate limit** concurrent insert race (unique window) | **High** | Reliability — possible 5xx under first-hit race |
| B6 | **In-process WebSocket hub** | **High** (multi-replica) | User + Reliability — stale “live” without stickiness |
| B7 | **`DASHBOARD_AUTH_ENABLED=false` in production** allowed by validator | **High** (if exposed) | Security — must be network-compensated |
| B8 | **Forwarded proto trust** (`INGEST_TRUST_FORWARDED_PROTO`) | **Medium** | Security — misconfigured LB weakens HTTPS assumptions |

### 4.3 Medium / lower

- Fire-and-forget WS fan-out tasks — shutdown / observability of task failures.
- Fail-open distributed rate limit — documented burst behavior when DB unhealthy.
- Dashboard read paths without uniform rate limits on expensive queries (query explorer, traces) — abuse / overload surface.
- Postgres CI job vs SQLite job gate parity ([.github/workflows/ci.yml](../.github/workflows/ci.yml)).

---

## 5. SDK & ingestion audit

### 5.1 Strengths

- Non-blocking enqueue, bounded queue, batch sender, gzip for large payloads.
- Default scrub keys; optional header/query capture off by default.
- Backend idempotency support for batches.

### 5.2 Gaps (severity)

| ID | Finding | Severity |
|----|---------|----------|
| S1 | **Half-configured monitor:** middleware added before guaranteed startup/shutdown registration | **High** |
| S2 | **Retries:** non-401 4xx (e.g. 413, 422) and 429 without `Retry-After` handling | **High** |
| S3 | **No SDK `Idempotency-Key`** — duplicates on timeout/retry | **High** |
| S4 | **OTLP vs ingest body limits** — path-scoped middleware may not cap OTLP like `/ingest` | **High** |
| S5 | **`model_extra` on events** — count limit but weak nested size caps | **Medium** |
| S6 | **Stack/message scrubbing** — key-based only; secrets in free text remain | **Medium** |
| S7 | **Backoff without jitter** | **Low** |
| S8 | **httpx timeout** not env-configurable | **Low** |

---

## 6. Frontend quality audit

### 6.1 Strengths

- Diagnosis-first nav and metadata ([DashboardLayoutClient.tsx](../frontend/components/dashboard/DashboardLayoutClient.tsx)).
- Central boundary for loading/error/empty ([DashboardPageBoundary.tsx](../frontend/components/dashboard/DashboardPageBoundary.tsx)); fetch error normalization.
- `npm run build` static export in CI; accessibility primitives in places (skip link, landmarks, sidebar labels).

### 6.2 Gaps

| ID | Finding | Severity |
|----|---------|----------|
| F1 | **No Playwright in CI** — golden path regressions possible | **High** |
| F2 | **Guided troubleshooting** — runbook expects panel on Dashboard + Diagnosis; verify parity with [PHASE5_RELEASE_CHECKLIST.md](./runbooks/PHASE5_RELEASE_CHECKLIST.md) | **Medium** |
| F3 | **Loading state a11y** — some branches visual-only without `aria-live` | **Medium** |
| F4 | **No RUM / client error reporting** — production blind spot | **Medium** |
| F5 | **Bundle weight** — Chart.js stack; no enforced bundle budget in repo | **Low** |
| F6 | **Magic link token in URL** — operational hygiene (TTL, one-time use, referrer risk) | **Medium** |

---

## 7. Operations & release audit

### 7.1 Strengths

- Canonical [PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md): topology, `/health` vs `/ready`, SLO starters, backup/drill pointers.
- [DEPLOYMENT_MULTI_INSTANCE.md](./ops/DEPLOYMENT_MULTI_INSTANCE.md), [BACKUP_RESTORE.md](./ops/BACKUP_RESTORE.md), Phase 5 runbooks.
- [release_gates.sh](../scripts/release_gates.sh) for local/CI-adjacent discipline.

### 7.2 Gaps

| ID | Finding | Severity |
|----|---------|----------|
| O1 | **No Dockerfile / official image** in repo | **High** |
| O2 | **Browser E2E optional** — not blocking merges | **High** |
| O3 | **Multi-instance runbooks** must be executed in *your* LB target — not automated | **Medium** |
| O4 | **`npm audit --audit-level=high`** — moderate CVEs may pass | **Low** |

---

## 8. Missing features catalog

Grouped by pillar. Items marked **MVP doc** come from [DEVELOPMENT.md](../DEVELOPMENT.md) “Build soon” or implied ops needs.

### 8.1 Product / UX

- Progressive disclosure / “solo mode” product shell for orgs, OIDC, SQL explorer, traces.
- Unified alerts configuration story (single mental model).
- Consistent “Requests” vs “logs” language and URLs.
- **Auth positioning in UX:** clear paths for **basic first-party auth** vs **bring-your-own / host-app SSO** (copy and settings layout), without conflating the two.
- ~~Billing / quota transparency~~ — **deferred** (see [Maintainer direction](#maintainer-direction-2026-05-05)).

### 8.2 Backend / platform

- **SQLite golden-path documentation:** single binary / single process expectations, file locations (`AUTOPULSE_DATA_DIR`), backup of **both** SQLite metadata file and DuckDB events file.
- **Optional metadata DB upgrade path:** documented `DATABASE_URL` examples and migration notes for Postgres (and parity tests policy).
- Explicit **migration job** vs API replicas (documented + optional env to skip DDL on workers).
- **Cross-replica realtime bus** (Redis/NATS) or formal “single writer + polling” product stance.
- **Multi-writer-safe event store** or hard enforcement of single-writer DuckDB topology.
- **Rate-limit race** hardening + tests.
- **Transactional or compensating** ingest path for DuckDB + SQL consistency.
- Dashboard/API **read-path rate limits** on expensive endpoints.

### 8.3 SDK

- **Non-retryable 4xx** policy + **429 + Retry-After**.
- **Per-batch `Idempotency-Key`** from SDK.
- **All-on or all-off** `monitor()` lifecycle vs middleware ordering.
- **Request sampling** and **health-route ignore list** (MVP “build soon”).
- Optional **metrics hooks** for drops (behind config) for operators.

### 8.4 Frontend

- **CI Playwright smoke** (or scripted smoke) for core journey ([E2E_CORE_JOURNEY.md](./testing/E2E_CORE_JOURNEY.md)).
- Optional **RUM** behind env flag.
- **429-specific** user messaging where applicable.

### 8.5 Ops / release

- **Official container** (API + static UI mount) and example compose / Helm stub.
- **Optional Postgres metadata DB:** CI parity with SQLite gates **or** an explicit, published policy that Postgres runs a documented subset (no silent gap).

---

## 9. Top 15 missing features for production

| # | Feature / control | Pillar | Why it matters |
|---|-------------------|--------|----------------|
| 1 | **SQLite + DuckDB golden-path runbook** (paths, backup, single-process scheduler behavior) | Ops / Product | Time-to-value and safe embedded operation |
| 2 | Explicit **`JOBS_ENABLE_SCHEDULER=true`** (or cron) when **metadata DB is not** the auto-scheduler SQLite filenames | Backend / Ops | Prevents silent loss of alerts/retention on Postgres et al. |
| 3 | **Documented + enforced DuckDB topology** (single writer or dedicated event node) | Ops | Data integrity under scale |
| 4 | **LB sticky sessions or single WS replica** for live dashboard | Ops / Frontend | Matches implemented realtime model |
| 5 | **SDK `Idempotency-Key` + smarter retries** | SDK | Prevents duplicate metrics and retry storms |
| 6 | **OTLP / ingest uniform body limits** | Backend | Abuse and OOM protection |
| 7 | **Decouple Alembic** from N-replica API boot | Ops | Safe rolling deploys |
| 8 | **Distributed rate-limit race fix** | Backend | Prevents ingest 5xx under concurrency |
| 9 | **Ingest cross-store consistency** strategy (outbox / reorder / reconcile) | Backend | Truth vs dashboard mismatch |
| 10 | **Official Docker image + static export mount** | Ops | Repeatable self-host |
| 11 | **CI browser E2E** (minimal smoke) | Frontend / Ops | Regressions on sign-in → diagnosis |
| 12 | **Scope narrative** (doc + UI) without billing/tier story | Product | Reduces confusion; aligns with deferred commercial work |
| 13 | **Auth modes documented and tested:** basic OOTB vs host / OIDC integration | Product / Backend | Matches dual deployment reality |
| 14 | **Read-path rate limits** on heavy dashboard queries | Backend | Protects API under abuse (especially when metadata DB is SQLite) |
| 15 | **Postgres (optional metadata DB) CI parity** with SQLite gates or explicit “documented subset” policy | Delivery | Users upgrading metadata DB are not second-class |

**Also tracked (not top-15):** SDK **request sampling** and **health-route ignore lists** ([DEVELOPMENT.md](../DEVELOPMENT.md) “Build soon”) — cost/noise control after core reliability gates.

---

## 10. Production hardening roadmap (P0 / P1 / P2)

### P0 — Ship blockers (acceptance criteria)

| Item | Owner | Acceptance criteria |
|------|-------|---------------------|
| SQLite + DuckDB embedded path | SRE + Docs | Runbook: default paths, backup both stores, scheduler behavior for default SQLite filenames verified; “when to move metadata off SQLite” guidance |
| Scheduler when metadata DB ≠ SQLite golden path | SRE + Backend | Runbook + env template require `JOBS_ENABLE_SCHEDULER=true` (or documented cron) for Postgres etc.; `/ready` or metrics expose scheduler state; optional fail-fast when alerts expected but scheduler off |
| Topology doc + enforcement | SRE | Written “DuckDB single writer” or equivalent; staging load test with **intended** replica count |
| WS + LB | SRE | Sticky sessions verified OR single WS replica; runbook symptom: “live stale” |
| SDK idempotency + retries | SDK | Integration tests: no retry on 413/422; 429 honors `Retry-After` if present; `Idempotency-Key` sent; backend dedup verified |
| monitor() lifecycle | SDK | Unit/integration: failed startup handler does not leave middleware without sender |
| OTLP body limits | Backend | Oversized OTLP rejected without full unbounded parse; test added |

### P1 — 30-day stabilization

| Item | Owner | Acceptance criteria |
|------|-------|---------------------|
| Migration strategy | SRE + Backend | One-shot migrate job documented; env to disable migrate-on-boot for replicas |
| Rate-limit races | Backend | Concurrency test; no IntegrityError surfacing as 500 |
| Ingest consistency | Backend | Documented recovery + metric for “SQL lag behind DuckDB” if any |
| Dashboard guided panel parity | Product + FE | Align [PHASE5_RELEASE_CHECKLIST.md](./runbooks/PHASE5_RELEASE_CHECKLIST.md) with UI |
| Auth misconfig guardrails | Backend | Explicit “air-gapped” flag if `DASHBOARD_AUTH_ENABLED=false` in production; **document** basic vs OIDC/host integration checklist (no new product surface required beyond clarity) |
| Forwarded headers runbook | SRE | LB checklist for `X-Forwarded-Proto`, cookie Secure, HTTPS ingest |

### P2 — 60–90 day strategic

| Item | Owner | Acceptance criteria |
|------|-------|---------------------|
| Shared realtime bus | Backend | WS updates correct with N replicas without stickiness requirement |
| Alternative / scaled event store | Platform | ADR published with migration phases, MVP compatibility/cost analysis, and explicit hard/soft adoption triggers (see [ADR_EVENT_STORE_SCALING.md](./ops/ADR_EVENT_STORE_SCALING.md)) |
| Bundle budget + lazy charts | FE | p95 JS budget on overview path measured |
| Optional RUM | FE / Ops | Env-gated, privacy-reviewed |
| Postgres CI parity | Delivery | Same linters + expanded pytest on PG job OR documented policy |

---

## 11. Decision log (scope vs shipped reality)

| Decision | Options | Recommendation |
|----------|-----------|------------------|
| Billing / plans | Ship now vs defer | **Defer** — not in current production readiness scope |
| Metadata DB | SQLite only vs SQLite default + optional Postgres | **SQLite-first** for time-to-value; **keep optional upgrade** via `DATABASE_URL` and documented ops |
| Event plane | DuckDB vs alternate | **DuckDB remains the dedicated event / analytical store** per architecture; HA/topology is an ops concern, not a “pick another engine” gate for MVP |
| Dashboard auth | Single mode vs dual | **Dual path:** basic OOTB session/magic link **and** host-aligned auth (e.g. OIDC) where the operator owns identity |
| Query / SQL explorer | Remove vs gate vs promote to “Pro” | **Gate + copy** until `DEVELOPMENT.md` non-goals are formally revised under governance |
| Traces UI | Remove vs “beta” vs full product | **Beta / adjacent** unless strategy elevates tracing; align marketing with `DEVELOPMENT.md` |
| Orgs / RBAC | Default-on vs progressive | **Progressive disclosure** for solo ICP; keep power path for teams |
| Scheduler | Magic default vs explicit | **Auto for known default SQLite files** (current code); **explicit env or cron** for all other metadata DB URLs |

---

## 12. Go / no-go production checklist

Use this as a **binary gate** before pointing production traffic.

### 12.1 Configuration

- [ ] `AUTOPULSE_ENV=production` with `validate_deployment_settings` passing
- [ ] **Metadata DB:** deliberate choice — **default SQLite** (embedded path) **or** upgraded `DATABASE_URL` (e.g. Postgres); understand SQLite file caps and concurrency limits if staying on SQLite
- [ ] **Scheduler:** if **not** using the auto-enabled default SQLite filenames, confirm **`JOBS_ENABLE_SCHEDULER=true`** or external cron for alerts/retention
- [ ] **Auth mode chosen:** basic dashboard auth configured **or** OIDC / host integration path documented and tested for your deployment
- [ ] `AUTOPULSE_DATA_DIR` / `AUTOPULSE_DUCKDB_PATH` agreed across all processes (**DuckDB event plane**)
- [ ] `INGEST_REQUIRE_HTTPS`, `CORS_ALLOW_ORIGINS`, dashboard origin middleware aligned with real UI origins
- [ ] `INTERNAL_METRICS_BEARER_TOKEN` set; scraping configured
- [ ] Secrets in secret manager (DB, SMTP, OIDC, metrics token)

### 12.2 Topology

- [ ] DuckDB: **single writer** process or documented unsupported multi-writer
- [ ] API replicas >1: **`INGEST_DISTRIBUTED_RATE_LIMIT_ENABLED`** understood + fail-open documented
- [ ] WebSocket: **sticky LB** or **single WS-capable replica**

### 12.3 Data and recovery

- [ ] Backup/restore drill: SQL + DuckDB per [BACKUP_RESTORE.md](./ops/BACKUP_RESTORE.md)
- [ ] Incident drill: ingest overload + provider failure ([PHASE5_INCIDENT_DRILLS.md](./runbooks/PHASE5_INCIDENT_DRILLS.md))

### 12.4 Quality

- [ ] `bash ./scripts/release_gates.sh` green on release candidate
- [ ] Manual smoke: `/ready`, magic link or OIDC, overview, diagnosis, requests, alerts
- [ ] (Recommended) Playwright smoke per [E2E_CORE_JOURNEY.md](./testing/E2E_CORE_JOURNEY.md)

### 12.5 No-go triggers

- **Non–SQLite-default metadata DB** (e.g. Postgres) + **`JOBS_ENABLE_SCHEDULER` unset/false** while expecting email/webhook alerts or scheduled retention **without** external cron replacement
- Multiple API replicas writing **one DuckDB file** without single-writer enforcement
- Production dashboard exposed with **`DASHBOARD_AUTH_ENABLED=false`** and no compensating network controls

---

## Appendix A — Evidence index (quick)

| Area | Primary paths |
|------|----------------|
| Product truth | [DEVELOPMENT.md](../DEVELOPMENT.md) |
| Prior audit | [AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md) |
| Ops | [PRODUCTION_DEPLOYMENT.md](./ops/PRODUCTION_DEPLOYMENT.md), [DEPLOYMENT_MULTI_INSTANCE.md](./ops/DEPLOYMENT_MULTI_INSTANCE.md) |
| Scheduler default | [config.py](../backend/src/autopulse_backend/core/config.py) (`jobs_enable_scheduler`, `_is_workspace_default_dev_sqlite_file`) |
| Ingest | [routes/ingest.py](../backend/src/autopulse_backend/routes/ingest.py), [ingest_service.py](../backend/src/autopulse_backend/services/ingest_service.py) |
| SDK | [_monitor.py](../sdk/src/autopulse/_monitor.py) |
| CI | [.github/workflows/ci.yml](../.github/workflows/ci.yml), [release_gates.sh](../scripts/release_gates.sh) |
| E2E doc | [E2E_CORE_JOURNEY.md](./testing/E2E_CORE_JOURNEY.md) |

---

## Appendix B — Consistency with prior roadmap

[docs/AUTOPULSE_FULL_AUDIT_ROADMAP.md](./AUTOPULSE_FULL_AUDIT_ROADMAP.md) remains the detailed UX/capability matrix and flow notes. **This master audit** adds:

- Explicit **production** and **topology** gates (scheduler, DuckDB, WS, migrations)
- **SDK + ingest** reliability gaps tied to launch risk
- **Go/no-go checklist** and **P0–P2** acceptance criteria
- **Decision log** to resolve MVP doc vs shipped drift

---

## Document maintenance

- Re-run this audit after major releases or when `DEVELOPMENT.md` scope changes under governance.
- Keep tracker rows in `AUTOPULSE_FULL_AUDIT_ROADMAP.md` aligned with **§9 Top 15** here to avoid duplicate conflicting priorities. **Ignore billing/plan rows** in the roadmap until commercial scope is explicitly reopened.
