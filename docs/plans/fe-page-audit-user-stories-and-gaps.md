# Frontend Page Audit — User Stories, Featureset & Gaps

**Status:** Draft for maintainer review · **Date:** 2026-05-14 · **Type:** transient plan doc

This audit walks every frontend page/route in `frontend/app/`, lists the user stories
and featureset each page should satisfy, records what is actually implemented today,
maps the backend endpoints it consumes, and enumerates the gaps (FE-missing,
BE-missing, FE/BE mismatch, broken-or-stub, scope-drift, UX/a11y).

It is the **audit deliverable** requested before implementation. The prioritized
backlog at the end is the proposed implementation order; nothing is built until the
maintainer signs off, and material MVP/scope shifts route through
`docs/DOCUMENTATION_GOVERNANCE.md`.

Scope reference (`DEVELOPMENT.md`): the MVP promise is **"what broke, when did it
break, which requests led to it."** Explicit non-goals: distributed tracing, custom
dashboard builder, query language, complex alert rules, enterprise RBAC/audit.
"Layered capabilities" (org governance, OIDC, retention presets, SQL-scoped filters,
multi-channel alerts) are allowed **only as progressive disclosure** on the diagnosis
path.

---

## How to read this

- **Severity:** `BLOCKER` > `HIGH` > `MEDIUM` > `LOW`.
- **Category:** `FE-missing` · `BE-missing` · `FE-BE-mismatch` · `broken-or-stub` ·
  `scope-drift` · `UX` · `a11y`.
- Page sections are ordered by the sidebar IA: primary diagnosis paths first, then
  advanced, then settings, then auth/shell/misc.

---

## Route inventory

| Route | Kind | Content component |
|---|---|---|
| `/` | redirect → `/dashboard` | `app/page.tsx` |
| `/dashboard` | page | `DashboardHomeContent` |
| `/diagnosis` | page | `DiagnosisContent` |
| `/requests` | page | `LogsContent` |
| `/logs` | redirect → `/requests` | `app/(main)/logs/page.tsx` |
| `/incident` | page | `IncidentWorkspaceContent` |
| `/incidents` | redirect → `/incident?saved_incidents=1` | `app/(main)/incidents/page.tsx` |
| `/bookmarks` | page | `BookmarksContent` |
| `/alerts` | page | `AlertsContent` |
| `/query-explorer` | page | `QueryExplorerContent` |
| `/traces` | page | `TracesContent` |
| `/settings` | page | `SettingsContent` (+ 11 sections) |
| `/onboarding` | page | `OnboardingContent` |
| `/w/[pageId]` | dynamic page | `DashboardBackendWidgetGalleryContent` |
| `/widgets` | redirect → `/w/lx_showcase` | `app/(main)/widgets/page.tsx` |
| `/widgets-showcase` | redirect → `/w/lx_showcase` | `app/(main)/widgets-showcase/page.tsx` |
| `/widgets-showroom` | redirect → `/w/lx_showcase` | `app/(main)/widgets-showroom/page.tsx` |
| `/auth/magic-link` | page | `verify-client.tsx` |
| `not-found` / `(main)/error` | boundaries | `app/not-found.tsx`, `app/(main)/error.tsx` |

---

# 1. Overview — `/dashboard`

**Purpose.** Default landing page after onboarding: a single fast-diagnosis view that
answers "what is broken, when, which requests led to it" in ~5 seconds, scoped by a
shared window/method/status/env/service facet bar.

### User stories

- As a solo dev, I want request rate, error rate, and average latency for a chosen
  window at a glance, so I can tell within seconds whether my app is healthy.
- As a solo dev, I want my top failing routes, so I know where to look first.
- As a solo dev, I want my most recent grouped errors with counts and last-seen, so I
  can jump straight to the worst current problem.
- As a solo dev, I want to click a recent error and see evidence (stack trace / sample
  events) without leaving the overview.
- As a solo dev, I want a traffic-volume chart over time with release markers, so I can
  correlate a spike/regression with a deploy.
- As a solo dev, I want to narrow the whole page by window, method, status class, env,
  and service, so I can isolate one service or failure mode.
- As a solo dev, I want the page to keep prior data visible while it refreshes.
- As a solo dev, I want clear empty states when no traffic exists yet.
- As a small-team operator, I want an at-a-glance pipeline/operator-health summary.
- As a solo dev, I want recent background-job failures surfaced.
- As a solo dev, I want to bookmark a scoped view.
- As a solo dev, I want to click a headline metric to drill into its cause.

### Featureset implemented

- Scope facet bar (`OverviewScopeFacetBoard`): window/method/status/env/service selects
  driving the shared `DashboardDataContext`; sticky; data-age timer.
- Correlation clear bar when a `correlation_request_id` scope is active.
- 4 primary metric cards (active incidents, error rate, latency p95, requests/min) +
  5 secondary cards (errors, latency avg/p99, APDEX, active sessions estimate).
- `RecentJobFailuresStrip` with a "more" link into Diagnosis.
- `OperatorPipelineHealthSection` (separate `GET /dashboard/operator-health` fetch;
  falls back to `OperatorReliabilityCallout` for non-admins).
- `VolumeChart` with window summary line and release-marker chips.
- `<details open>` "Advanced infrastructure insights" → `DashboardInfrastructureSection`
  (host CPU/mem/disk/network, DB query / cache hit-miss / dependency panels).
- Errors & latency mini sparklines; top failing routes; top services; recent errors
  (row click → evidence modal, row menu → copy/bookmark).
- Loading skeletons, empty state, error banner; `DashboardDetailModal` +
  `SaveBookmarkModal`; light/heavy bundle alternation preserves prior data.

### Backend endpoints consumed

- `POST /dashboard/query` — batch (`overview`, `requests`, on heavy refresh
  `overview_extended`, `widgets`, `error_groups`, `recent_job_failures`).
- `GET /dashboard/operator-health` — direct fetch (admin/owner only).
- `GET /dashboard/bootstrap` — seeds onboarding/api-keys/theme/retention/alert settings.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| O1 | HIGH | scope-drift | Page is far heavier than the MVP "5-second diagnosis" mandate: 9 metric cards, APDEX, active-sessions estimate, a full infra section (host CPU/mem/disk/network, DB, cache, dependency map). `DEVELOPMENT.md` says Overview shows requests/min, error rate, avg latency, top failing routes, recent errors — nothing else. | Reduce headline grid to the 5 MVP signals; demote APDEX/active-sessions to a "more metrics" disclosure; move infra to a collapsed-by-default (or separate) surface. |
| O2 | HIGH | broken-or-stub | `DashboardInfrastructureSection` **fabricates** "DB query performance" from route latency, "cache hit/miss" from 2xx/3xx-vs-4xx/5xx counts, and a "service dependency map" from service volume (`DashboardInfrastructureSection.tsx:943-955`). Labeled as real telemetry with only a small caption. | Remove these three panels (no backend ever feeds them — see O3), or render an honest empty state. |
| O3 | HIGH | FE-BE-mismatch | The DB/cache/dependency panels search for widget keywords (`db`/`cache`/`dependency`) that **no backend code path ever produces** — `infrastructure_metrics.to_widget_payload` only emits host CPU/mem/disk/network/log-store. Those panels are permanently on their fabricated fallback. | Delete the dead keyword-search + fallback code, or file a BE task (but per MVP scope it should not ship). |
| O4 | MEDIUM | broken-or-stub | `overview_extended.alerts_timeline` is hard-coded `[]` in the DuckDB event-store path (`overview.py:503-523`) — the default stack. The legacy SQL path populates it. | Populate `alerts_timeline` in the DuckDB branch by querying `AlertDispatch` from SQL (data lives in SQL regardless of event store). |
| O5 | MEDIUM | broken-or-stub / scope-drift | The legacy non-phased branch of `DashboardHomeContent.tsx` (~700 lines: donuts, heatmaps, scatter, histograms) is dead code in normal builds and is the only place `MetricCard` drill-down `onClick` exists. | Delete the legacy branch; port the `pushDiagnosisWithScope`/`pushRequestsWithScope` handlers into the phased-lite cards. |
| O6 | MEDIUM | FE-missing / UX | In the live (phased-lite) branch the primary `MetricCard`s have **no `onClick`** — "active incidents", "error rate", "latency p95" are not clickable. Drill-down story unmet. | Wire `onClick` on the phased-lite cards routing to `/diagnosis`/`/requests` with current scope. |
| O7 | MEDIUM | UX | Phased-lite error banner uses `text-rose-200` on `bg-rose-500/10` — near-invisible in light theme; no light-mode pair; no `role`. | Add light+dark color pairs and `role="alert"`. |
| O8 | LOW | UX | "Advanced infrastructure insights" `<details>` has no chevron affordance and is open by default. | Add a disclosure affordance; default closed. |
| O9 | LOW | UX | Top-routes/top-services/recent-errors panels can't distinguish "loading" from "genuinely empty" during a slow heavy refresh. | Tie empty copy to `homeSlice.chartsScopePending`. |
| O10 | LOW | a11y | Severity badges/incident tone bars convey state by color only. | Add a non-color cue (icon/text label). |

---

# 2. Errors & Diagnosis — `/diagnosis`

**Purpose.** The "what broke" surface: correlates grouped exceptions with recent traffic
in a shared window, ranks incidents, and offers symptom-driven next steps.

### User stories

- As a solo dev, I want exceptions grouped by type/route with counts and last-seen.
- As a solo dev, I want a sample stack trace per error group.
- As a solo dev, I want top failing routes (5xx) for the current window.
- As a solo dev, I want to jump from an error group to the matching request rows.
- As a small-team member, I want symptom-driven guidance (spike / outage / alert-delivery
  failure) with concrete next steps.
- As a solo dev, I want background job/cron failures surfaced alongside HTTP errors.
- As a solo dev, I want a traffic volume chart for the same scope, so I can see *when*
  the break started and correlate it with a release.
- As a solo dev, I want to deep-link/bookmark a specific error group.
- As a solo dev, I want a clear empty/partial-scope state.
- As a small-team member, I want to sort/page grouped errors by count or last-seen.

### Featureset implemented

- Sticky scope bar (`DiagnosisRequestsStickyScopeBar`) + correlation clear bar.
- `RecentJobFailuresStrip`; "Traffic in scope" `VolumeChart` with release markers.
- 3 `MetricCard`s (incident summary, timeline bucket count, error-group total).
- `GuidedTroubleshootingPanel` symptom hints with next-step links.
- "Quick diagnosis": recent-errors preview + top failing routes, with deep links to
  Requests.
- "Grouped errors" table: expandable rows, sort select, route-filter banner,
  pagination, per-row actions menu, `ErrorGroupEvidenceBody`, modal view.
- "Error-group event evidence" section (up to 8 raw events for the first group).
- Deep-link handling (`#error-group:<key>`, `#grouped-errors`) with auto-retry.
- Loading/empty/stale/partial-scope states; RUM events.

### Backend endpoints consumed

- `POST /dashboard/query` — `overview`, `requests`, `error_groups`, `diagnosis_timeline`,
  `diagnosis_failures`, `recent_job_failures`, `diagnosis_error_group_events`,
  `alert_dispatches` slices.
- `GET /dashboard/bootstrap` — retention/alert settings for guidance hints.
- `POST /dashboard/log-query/validate` — only when the advanced SQL UI flag is on.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| D1 | HIGH | broken-or-stub | `diagnosis_timeline` and `diagnosis_failures` slices are fetched on every heavy query (real BE work) and **gate the page render**, but only their `.length`/`reduce` are shown as bare count badges (`DiagnosisContent.tsx:465-469`). The per-minute timeline and failures-by-route breakdown — the literal "when did it break / which routes" payloads — are never visualized. | Render a real timeline chart (error vs total per bucket) and a failures-by-route list from these slices. This is the highest-value MVP fix on this page. |
| D2 | MEDIUM | FE-BE-mismatch | "Top failing routes" is computed client-side from the loaded request sample (`DashboardDataContext.tsx:1655`), while the incident-summary card uses the full-scope `diagnosis_failures` aggregate — they disagree on partial scopes. | Drive "Top failing routes" from `diagnosis_failures.items`. |
| D3 | MEDIUM | UX | "Error-group event evidence" only ever loads events for `recentErrorsPreview[0]`; expanding a different row doesn't change it. Empty copy ("Select a busier window…") is misleading. | Wire the section to the currently expanded error group, or fold events into `ErrorGroupEvidenceBody`. |
| D4 | MEDIUM | scope-drift | Recent-errors deep links claim "same time window and filters" but force `statusClass: "ALL"` (`DiagnosisContent.tsx:518`), silently dropping the active status filter. | Preserve the active `statusClass`, or make the copy explicit. |
| D5 | LOW | UX | `recentErrorsPreview` is always sorted by `last_seen` even when the table is sorted by count — inconsistent ordering. | Honor `errorGroupSort` for the preview. |
| D6 | LOW | a11y | "Recent errors" anchors scroll to `#grouped-errors` (table top) instead of expanding/focusing the matching row. | Deep-link to `#error-group:<key>` which already triggers expansion. |
| D7 | LOW | UX | Grouped-errors pagination shows "Page N · Offset M" but no total page count. | Surface total pages. |
| D8 | LOW | scope-drift | "Jobs & cron (deeper slice)" card + `RecentJobFailuresStrip` route to `/query-explorer` SQL on the primary diagnosis path. Job tracking is "Build Soon After MVP"; SQL is a non-goal. | Keep these as low-prominence progressive disclosure; don't let them overshadow the core loop. |

---

# 3. Requests — `/requests` (`/logs` redirects here)

**Purpose.** The request-evidence explorer: a filterable, groupable table of recent HTTP
requests with full per-request detail.

### User stories

- As a solo dev, I want a table of recent requests with time/method/path/status/latency/
  service/env.
- As a solo dev, I want to filter by time range, status, route, method, env.
- As a solo dev, I want to sort by any column.
- As a solo dev, I want to expand a row for full evidence (request id, trace/span id,
  SDK version, log message, received-at).
- As a solo dev, I want to jump from a request to the diagnosis view for that route.
- As a small-team member, I want to follow a correlation trail by request id.
- As a solo dev, I want quick at-a-glance counts (loaded rows, 5xx, slow, p95).
- As a solo dev, I want to export the current scope to CSV/JSON.
- As a solo dev, I want to group rows (e.g. by route/status).
- As a solo dev, I want to bookmark a specific request row or a filtered view.
- As a solo dev, I want clear empty/loading/error states.

### Featureset implemented

- Sticky scope bar + correlation clear bar (shared with diagnosis).
- "Request evidence flow" stat tiles: loaded rows, errors (5xx), slow (≥300ms), p95.
- "Local view controls": group-by select, env/service `TagSelector`, reset button.
- Sortable, groupable, expandable request table (`ExpandableTableRow`,
  `RequestEvidenceBody`), per-row actions menu (copy JSON/text, bookmark, correlation
  trail), modal detail view.
- Export CSV/JSON via `GET /dashboard/requests/export` (capped 500/click in FE).
- Client-side "load 100 more" + server-side Prev/Next pagination.
- Deep-link `#request-row:<rowId>`; `SaveBookmarkModal`.
- Loading/empty/filtered-empty/stale states; export error `role="alert"`.

### Backend endpoints consumed

- `POST /dashboard/query` — `requests` (+ `overview` for the scope bar).
- `GET /dashboard/requests/export` — CSV/JSON export.
- `GET /dashboard/bootstrap`; `POST /dashboard/log-query/validate` (flag-gated).

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| R1 | HIGH | broken-or-stub | `POST /dashboard/log-query/execute` exists in the backend (`log_query_routes.py:70`) but **no FE code calls it** — dead surface. Only `/log-query/validate` is used. "Query language" is an explicit non-goal. | Remove/quarantine `log-query/execute` as internal-only, or confirm a planned consumer. |
| R2 | MEDIUM | FE-BE-mismatch | `GET /requests` and the export route accept a `focus` param (`DashboardRequestsFocus`) the FE never sends; FE instead recomputes errors/slow client-side over the loaded sample only. | Wire `focus` into scope/export params, or drop it from the route. |
| R3 | MEDIUM | UX | Stat tiles (errors 5xx, slow, p95) are computed over only the **loaded page**, not the full window — "Errors (5xx): 3 — prioritize these first" can badly understate reality. | Label tiles "in loaded rows" (like the p95 tile), or source counts from a server aggregate. |
| R4 | MEDIUM | UX | Two pagination mechanisms coexist confusingly (server Prev/Next + client `rowsPerGroup` "load 100 more"); they interact unpredictably with grouping. | Consolidate to one paging model; scope "load more" as group-local expansion. |
| R5 | LOW | FE-BE-mismatch | `RequestEvidenceBody` renders `trace_id`/`span_id`. Distributed tracing is a non-goal and the event model has no trace/span fields. | Confirm whether the SDK/backend populate these; if not, remove; if yes, document. |
| R6 | LOW | UX | Export hardcoded to 500 rows/click with no offset control; API allows up to 2000 + offset to 50000. | Expose offset/next-batch controls or raise the per-click limit. |
| R7 | LOW | UX | Empty-state copy references "the manual test script" and `POST /ingest` — dev-facing language in the product UI. | Point users to onboarding / "send a request from your app". |
| R8 | LOW | a11y | Sticky `<thead>` can overlap the sticky scope bar; verify stacking. | Verify/fix z-index + offset. |
| R9 | LOW | UX | `rowsPerGroup` is one shared state across all groups — "load 100 more" in one group raises the cap for every group. | Make per-group state. |

---

# 4. Incident — `/incident` (`/incidents` redirects here)

**Purpose.** A per-scope "incident notebook" workspace where a dev captures the incident
narrative (markdown/SQL/checklist/scope cells), pins a dashboard scope, runs scoped SQL,
and publishes server-backed saves / share links.

### User stories

- As a solo dev, I want to record what broke and when in a structured notebook tied to a
  time window.
- As a dev, I want to capture the current dashboard scope into the notebook.
- As a dev, I want to re-apply a saved scope back onto the dashboard.
- As a dev, I want to run scoped SQL inside the notebook against `scoped_events`.
- As a dev, I want my notebook to autosave.
- As a team member, I want to publish a notebook as a share link (org-wide or restricted).
- As a team member, I want to open, rename, and delete saved incidents.
- As a dev arriving from an alert, I want a link that drops me into the incident
  workspace with the relevant scope.
- As a dev, I want quick links from the notebook to Errors/Requests/Overview.

### Featureset implemented

- Notebook cell types (scope, markdown, note, SQL, divider, checklist, link); reorder/
  duplicate/collapse/delete; 3 templates.
- Scope cell edit + "capture from session" / "apply to dashboard".
- SQL cell executes against `POST /dashboard/query-explorer/execute`.
- localStorage persistence keyed by project + scope hash, legacy-notes migration.
- Server-backed saved incidents: create/get/list/patch/delete; share-link create+redeem;
  "wrong project" 409 handling; autosave badge with PATCH coalescing.
- Saved-incidents modal (list/open/rename/delete); restricted-share user picker via org
  members.

### Backend endpoints consumed

- `POST/GET/PATCH/DELETE /dashboard/incident-shares` (+ `/{id}`, `/redeem`).
- `POST /dashboard/query-explorer/execute`.
- `GET /dashboard/organizations/{id}/members`.

All consumed endpoints exist; no path mismatches.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| I1 | HIGH | UX | Errors are surfaced via blocking `window.alert()` throughout (`IncidentWorkspaceContent.tsx:336,348,358,381,401,409,449`). Inconsistent with inline `role="alert"` banners elsewhere. | Replace with inline error banners / toast per the console design system. |
| I2 | MEDIUM | scope-drift | The whole page (notebook + SQL cells + multi-mode sharing + restricted ACLs) goes well beyond the MVP loop and edges toward "thinks like an observability engineer." | Confirm it's intentionally layered; keep the default diagnosis path off this page; gate SQL cells behind an "advanced" affordance. |
| I3 | MEDIUM | FE-BE-mismatch | `openFreshIncidentNotebook` posts `access_mode: "organization"` + `expires_in_days: 90` — every "New notebook" is immediately org-visible/listed; no private/draft mode. | Add a private/draft access mode; default new notebooks to creator-only until shared. |
| I4 | MEDIUM | broken-or-stub | Non-server notebooks persist localStorage-first, keyed by a djb2 hash of the scoped query — different scopes silently get different notebooks; clearing storage loses the record. | Always create a server row on first edit, or prominently warn that unsaved notebooks are browser-local. |
| I5 | MEDIUM | FE-missing | No loading/error UI while a saved incident / share is fetched on mount; failures fall to `alert()` + default notebook. | Add an explicit hydration loading state + retry affordance. |
| I6 | MEDIUM | FE-BE-mismatch | `GET /dashboard/incident-shares` returns only non-revoked rows, but the UI renders an unreachable "Revoked" state and offers no revoke action despite the model supporting `revoked_at`. | Expose a revoke action + include revoked rows, or remove the dead branch. |
| I7 | LOW | FE-BE-mismatch | `SavedIncidentsModalPanel.parseListPayload` drops a row if any of `created_at`/`updated_at`/`expires_at`/`access_mode` is missing — incidents can silently vanish. | Only require `id`; be lenient on display fields. |
| I8 | LOW | UX | `applyStarterTemplate` uses `window.confirm` to destroy notebook content; with localStorage-only persistence this is an easy data-loss path. | Non-blocking confirm modal + undo snapshot. |
| I9 | LOW | a11y | Transient status text (`shareMessage`, autosave, SQL run) is plain `<p>` without `role="status"`. | Wrap in `role="status" aria-live="polite"`. |
| I10 | LOW | UX | `redeem`/saved-load effects swallow errors in empty `catch {}` "to allow retry" but there is no retry trigger. | Surface a retry button on failure. |

---

# 5. Bookmarks — `/bookmarks`

**Purpose.** Lists the user's saved dashboard views (private + project-visible) and lets
them open, edit (title/notes/visibility), and delete them. Bookmarks are *created*
elsewhere via `SaveBookmarkModal`.

### User stories

- As a dev, I want to save a dashboard view (path + query + hash) as a named bookmark.
- As a dev, I want to see all my bookmarks in one place and open them in one click.
- As a dev, I want to edit a bookmark's title and notes.
- As an owner/admin, I want to share a bookmark with the project team / change visibility.
- As a dev, I want to delete bookmarks I own.
- As a dev, I want to know which project a bookmark belongs to.
- As a viewer, I want to open team bookmarks even if I can't edit them.

### Featureset implemented

- Initial fetch + spinner; grid of cards (title, "Team" badge, project name, href, notes).
- Inline edit of title+notes; visibility `<select>` for owner/admin; delete with
  `window.confirm`; per-row mutability gate `canMutateBookmark`.
- Empty state + inline `role="alert"` error banner.

### Backend endpoints consumed

- `GET/POST/PUT/DELETE /dashboard/bookmarks` (+ `/{id}`). All exist; no path mismatches.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| B1 | MEDIUM | broken-or-stub | `reload` is defined but **never called** — no refresh control; after a failed save the list drifts from the server with no resync short of a full page reload. | Wire a "Refresh" control / call `reload()` after error. |
| B2 | MEDIUM | UX / security | Bookmark hrefs are rendered as `<Link>` from a stored `pathname` + `query_string` + `hash_fragment` with no allowlisting; a project-visible bookmark from another member could carry an unexpected pathname. | Validate `pathname` against known dashboard routes (mirror `safeUrl` in `IncidentMarkdownBody.tsx`). |
| B3 | MEDIUM | scope-drift | Bookmarks/saved-views are not in the MVP scope and lean toward configurability. | Maintainer confirm it stays off the critical 5-second-diagnosis path. |
| B4 | LOW | UX | Per-row edit/delete errors are written into the page-level `loadError` banner state. | Separate per-row error state from list-load error. |
| B5 | LOW | UX | No count/pagination; backend caps at 500 — older bookmarks silently disappear at the cap. | Show a count + "showing first 500" note. |
| B6 | LOW | a11y | Delete uses native `window.confirm`; card grid lacks landmark/heading association. | Prefer in-app confirm modal; group Open/Edit/Delete controls. |

---

# 6. Alerts — `/alerts`

**Purpose.** Configure and review the project's automated alerting; shows current
error-rate / spike / outage heuristic state, lets owners/admins edit rules and
thresholds, mute/snooze, and review + acknowledge dispatch history.

### User stories

- As a solo dev, I want an email alert when my app's error rate spikes. *(Core MVP.)*
- As a solo dev, I want an email alert when my service appears down. *(Core MVP.)*
- As a dev, I want to set a destination email and enable/disable alerts with one switch.
- As a dev, I want to tune spike/outage thresholds and windows.
- As a dev, I want to mute or snooze notifications during planned work.
- As a dev, I want to see whether my current scope is over threshold right now.
- As a team member, I want to review past dispatches and their delivery status/reason.
- As a team member, I want to acknowledge an alert dispatch.
- As a dev, I want to send a test alert end-to-end.
- As a dev, I want to jump from an alert to the grouped errors that caused it.

### Featureset implemented

- 3 summary panels (error rate vs threshold, spike candidates, outage candidates) with
  sparklines.
- Tabs: "Alert rules" / "Dispatch history".
- Rules tab: master enabled toggle + destination email; error-spike rule card; outage
  rule card; notification pause panel (mute + 1/4/24h snooze + clear + acknowledge);
  save with client-side validation; read-only banner for non-admins.
- "Delivery channels" + "Runbook shortcuts" panels (the latter copies `alerts-once` /
  `retention-once` CLI commands).
- Dispatch history table with "Failed only" filter and per-row "Ack" button.
- Loading state + an error/empty fallback panel.

### Backend endpoints consumed

- `PUT /dashboard/alert-settings`; `POST /dashboard/alert-dispatches/{id}/acknowledge`;
  `GET /dashboard/alert-settings` + `GET /dashboard/alert-dispatches` (via the data slice).
- **Not consumed:** `GET /dashboard/alert-capabilities`, `POST /dashboard/alert-test`
  (both exist).

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| A1 | HIGH | FE-BE-mismatch | Summary panels' spike/outage state comes from `computeOperationalSignals(overview, M5_ALERT_DEFAULTS)` — **hard-coded constants** (`errorSpikeRatioThreshold: 0.4` …), not the project's saved `alertSettings`. A user who sets threshold 0.1 still sees "within threshold" until 0.4. | Compute operational signals from live `alertSettings`. |
| A2 | HIGH | FE-BE-mismatch | The preview evaluates over the dashboard scope window, not the configured `error_spike_window_minutes` / `outage_window_minutes` the alerts job uses — the "heuristic preview" doesn't reflect what will actually fire. | Evaluate the preview over the configured alert windows, or relabel the panels as "current dashboard scope". |
| A3 | MEDIUM | FE-missing | `POST /dashboard/alert-test` is core to the "verify delivery" story but the Alerts page only links out to Settings. | Surface a "Send test alert" button on the Alerts page. |
| A4 | MEDIUM | FE-missing | `GET /dashboard/alert-capabilities` (channel readiness) is never consumed here — a user can "save" alerts that will silently never deliver (no provider configured). | Fetch alert-capabilities; show per-channel readiness on the rules tab. |
| A5 | MEDIUM | FE-missing | The dispatch-history table has **no loading/error state**; `alertDispatches === null` renders the same empty message as a genuine empty result. | Thread loading/error state for dispatches. |
| A6 | MEDIUM | FE-BE-mismatch | `total` from the dispatches response is ignored; the page shows only `length` with no "X of Y" indicator or pagination. | Surface `total`; add pagination. |
| A7 | LOW | UX | `acknowledgeDispatch` silently does nothing on failure — no error feedback. | Show an inline error on ack failure. |
| A8 | LOW | UX | Snooze buttons compute `notifications_snoozed_until` into the draft but **don't save** until a separate "Save" click, while "Acknowledge" persists immediately — inconsistent. | Persist snooze/clear immediately, or visibly mark as pending-save. |
| A9 | LOW | UX | `snoozed until` / `last acknowledged` render raw ISO strings; the dispatch table uses `toLocaleString()`. | Format consistently. |
| A10 | LOW | a11y | `formError` / `alertSettingsMessage` are plain `<p>` with no `role` — save success/failure not announced. | Add `role="status"`/`role="alert"`. |
| A11 | LOW | UX | Dispatch-history rows aren't clickable; "Open grouped errors" uses the current dashboard scope, not the dispatch's `window_start..window_end`. | Make dispatch rows link to `/diagnosis` scoped to that dispatch's window. |
| A12 | LOW | scope-drift | "Runbook shortcuts" exposes raw `alerts-once`/`retention-once` CLI commands — operator-facing, against the "no DevOps overhead" positioning. | Maintainer check; consider moving behind an advanced disclosure. |

---

# 7. Query Explorer — `/query-explorer`

**Purpose.** A power-user, read-only SQL surface (DuckDB `SELECT`/CTE) over the
`scoped_events` view.

### User stories

- As a backend dev triaging an incident, I want curated SQL templates (volume by route,
  slowest requests, 5xx by service, captured error events, status distribution, env mix,
  request-id correlation).
- As a power user, I want to write my own `SELECT`/CTE against `scoped_events`.
- As a dev arriving from a "job failures" link, I want a starter query pre-loaded via
  `?preset=job_failures`.
- As a user, I want the header time-scope applied, with a toggle to scan the whole project.
- As a user, I want a tunable row limit (1–500).
- As a user, I want ⌘/Ctrl+Enter to run.
- As a user, I want clear failure messages and a truncation indicator.

### Featureset implemented

- 7 curated templates + "Custom SQL"; `?preset=job_failures` starter.
- `<textarea>` editor with a (non-scrolling) line-number gutter; "apply time window"
  toggle; row-limit input clamped 1–500; Run button + ⌘/Ctrl+Enter.
- Builds POST payload from shared dashboard scope/filter state.
- Results table with null styling, loading spinner, truncation chip, empty state, error
  banner. Backend enforces read-only (`SELECT`/`WITH` only, forbidden keywords,
  `scoped_events`-scoped, rate-limited, DuckDB-only).

### Backend endpoints consumed

- `POST /dashboard/query-explorer/execute`.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| Q1 | MEDIUM | scope-drift | A free-form SQL editor is heavier than the line-87 "SQL-scoped filters" progressive-disclosure example; "query language" is an explicit non-goal. | Maintainer decision: either document a free-form SQL editor explicitly in `DEVELOPMENT.md`, or reduce to parameterized templates only. |
| Q2 | MEDIUM | broken-or-stub | The `job_failures` preset + job templates assume event `type='job'`, but job tracking is "Build Soon After MVP" and `job` rows are rarely produced — the preset returns zero rows for real users. | Hide the `job_failures` preset until job tracking ships, or add an empty-state hint. |
| Q3 | LOW | FE-BE-mismatch | FE clamps `row_limit` to 1–500 but it's unclear the backend `DashboardQueryExplorerRequest.row_limit` has a server-side bound. | Verify/add a server-side `le=500` bound. |
| Q4 | LOW | UX | Line-number gutter is `position:absolute` and doesn't scroll with the textarea. | Sync gutter scroll, or drop the gutter. |
| Q5 | LOW | UX | No way to copy/export results. | Add "Copy as CSV/JSON" (reuse `copyTextToClipboard`). |
| Q6 | LOW | UX | Toggling "apply time window" off ("full project scan") has no cost warning beyond footer text. | Add a confirm / warning tone. |
| Q7 | LOW | a11y | Results table has no `<caption>`, `<th>` lacks `scope="col"`, query status isn't announced. | Add `scope="col"` + an `aria-live` status region. |

---

# 8. Traces — `/traces`

**Purpose.** A correlated-span explorer: searches OTLP spans grouped by `trace_id` within
a window and renders a per-trace span-latency view.

### User stories

- As a dev using OTLP instrumentation, I want to search traces by id/service/path/span
  name within a window.
- As a dev, I want preset windows (1h/6h/24h/7d) and Older/Newer paging.
- As a dev, I want to filter by service, env, path, method, and "5xx spans only".
- As a dev, I want to click a trace and see its spans as a latency view with status codes.
- As a dev, I want a clear empty state explaining why no traces show (wrong project,
  missing DuckDB event store, window too short).
- As a dev, I want to know which project and window the results are scoped to.

### Featureset implemented

- Trace search (free-text `q`, time window, 6 filters); window presets + Older/Newer
  paging; auto-runs an initial 24h search.
- Results list (severity dot, trace id, span/error counts, services).
- Trace detail "waterfall" (per-span name/service/path, latency bar by status class,
  `StatusCode` badge).
- Empty states; loading spinners; non-disruptive refresh; error banner.

### Backend endpoints consumed

- `GET /dashboard/traces/search`; `GET /dashboard/traces/{trace_id}`.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| T1 | HIGH | scope-drift | Distributed tracing is the **first explicit MVP non-goal**. This is a full trace-search + span-waterfall feature; the in-UI banner even calls it "Full tracing". Not covered by the line-87 progressive-disclosure list. | Escalate via `docs/DOCUMENTATION_GOVERNANCE.md`: either explicitly widen MVP scope in `DEVELOPMENT.md`, or gate the route behind a feature flag / mark experimental. |
| T2 | MEDIUM | broken-or-stub | The "waterfall" isn't one — every bar is `latency/max` anchored at the same left edge; `parent_span_id` is fetched but never used, so it can't show nesting/sequencing. | Compute real start-offset/indentation from timestamps + `parent_span_id`, or relabel "span latency comparison". |
| T3 | MEDIUM | FE-BE-mismatch | `errorsOnly` sends `status_class=5` on the **search** path (filters spans before grouping → undercounts `error_count`); the **detail** path ignores list filters → list and detail show different numbers for the same trace. | Apply `status_class` as a post-group (HAVING) filter on search so counts match detail. |
| T4 | MEDIUM | UX | Time window/filters/query are page-local `useState`, disconnected from the global scope bar every other page uses. | Consume `useDashboardData()` window state, or add a visible "Traces has its own time scope" note. |
| T5 | LOW | UX | No empty state distinguishes the SQLite-event-store 400 from a generic error — it shows raw `detail` in the danger banner. | Detect the "requires DuckDB event store" 400; render a friendly setup panel. |
| T6 | LOW | UX | Changing a filter gives no hint that results are now stale (filters only apply on next "Search"). | Show a "filters changed — re-run search" hint or debounce-search. |
| T7 | LOW | a11y | Detail waterfall rows are plain `<div>`s; latency bars convey status by color only; 4xx vs 2xx is color-only. | Add text/`aria-label` conveying status class to span rows. |

---

# 9. Settings — `/settings`

**Purpose.** A single multi-section page (11 sections + sticky section nav) for project/
operator configuration.

### User stories (by section)

- **RetentionPolicy** — set raw-event retention days, max SQL window, DB size cap, max
  log rows; pick a tier; toggle "archive before delete"; viewers see it read-only.
- **SdkNoise** — guidance on `LUMONOX_IGNORE_PATH_PREFIXES` /
  `LUMONOX_REQUEST_SAMPLE_RATE`.
- **InternalMetrics** — operator health snapshot (scheduler, retention poll, WS tick,
  realtime subscriber, aggregate queue, ingest pressure).
- **SystemDiagnostics** — support snapshot (topology guardrails, scheduler + per-job
  table, repairs, dead-letter backlog, ingestion lag, raw JSON).
- **EventPlaneCutover** — per-project switch to read from the published snapshot vs live
  DuckDB, with a parity gate.
- **ExcludeLumonoxTraffic** — exclude Lumonox's own traffic from analytics.
- **AlertDelivery** — enable project alerts, pick channels (email + address, Slack/
  Discord/generic webhook), see per-channel readiness, send a test alert.
- **ActiveProject** — switch the project the dashboard session is scoped to.
- **OrganizationsMembers** — promote/demote members (bulk), invite by email + role, see
  the roster.
- **ApiKeyLifecycle** — issue/rotate/revoke ingest keys (individually + bulk); viewers
  see active keys read-only.
- **AppearanceSession** — set theme (system/light/dark); sign out.
- **SectionNav** — sticky nav that scrolls to and highlights the current section.

### Featureset implemented

All 11 sections are implemented with role-gated edit, loading/error/empty states, and
save feedback. (Full per-section detail in the audit working notes; condensed here.)

### Backend endpoints consumed

`PUT/GET /dashboard/retention-settings`, `GET /dashboard/internal-metrics`,
`GET /dashboard/system-diagnostics`, `GET/PUT /dashboard/event-plane-cutover`,
`PUT /dashboard/theme-settings`, `PUT /dashboard/alert-settings`,
`POST /dashboard/alert-test`, `POST /dashboard/auth/active-project`,
`GET /dashboard/organizations`, `GET /dashboard/organizations/{id}/members`,
`POST .../members/invite`, `PUT .../members/{userId}/role`,
`GET/POST /dashboard/auth/api-keys` (+ `/issue`, `/rotate`, `/revoke`),
`POST /dashboard/auth/logout`. All exist; no dead-call mismatches.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| S1 | HIGH | FE-BE-mismatch | RBAC role mismatch: backend enum is `owner\|admin\|member\|viewer`, but the FE invite form + bulk-role control only offer `owner` and `member` (`useSettingsOrganizationsMembers.ts:25` types `inviteRole` as `"owner" \| "member"`). Admins/viewers render in the table but can't be created/assigned via the UI; can't demote to viewer or set admin. | Extend FE role selectors + `inviteRole`/`memberBulkRole` types to the full 4-role enum, with the same admin-can't-assign-owner/admin restriction the backend enforces. |
| S2 | MEDIUM | broken-or-stub | `SettingsSdkNoiseSection` is a static doc card with no functionality but occupies a top-level section + nav slot labeled "SDK noise", implying a control panel. | Relabel "SDK noise (docs)" or move the content into onboarding/docs and drop the section. |
| S3 | MEDIUM | UX | Section render order buries product-relevant settings under operator plumbing: retention → SDK noise → internal-metrics → system-diagnostics → event-plane → exclude-traffic → alert-delivery → active-project → members → api-keys → appearance. A solo dev scrolls past 4 operator-only sections to reach alert delivery or their API key. | Reorder so product settings (active project, API keys, alert delivery, retention) come first, operator/diagnostics last; or split into "Project" / "Operator" tabs. |
| S4 | MEDIUM | scope-drift | EventPlaneCutover / SystemDiagnostics / InternalMetrics are operator/internal-rollout tooling not named in `DEVELOPMENT.md` scope. Role-gated, which mitigates clutter. | Maintainer confirm operator-plumbing belongs in product Settings vs a separate `/ops` surface; at minimum keep them below the diagnosis-relevant sections. |
| S5 | MEDIUM | FE-BE-mismatch | API-key bulk-revoke "oldest active key can't be bulk-revoked" is enforced **client-side only**; if the backend `revoke` doesn't enforce last-active-key protection, a direct call could lock out ingestion. | Verify `auth_routes.py` revoke enforces last-active-key protection server-side. |
| S6 | LOW | UX | Bulk member/API-key actions use blocking `window.confirm`. | Replace with an in-app confirm dialog. |
| S7 | LOW | UX | Bulk operations loop one request per item; partial failure shows "3 succeeded, 2 failed" with no per-item detail or retry. | Surface per-item failure detail, or add a batch endpoint. |
| S8 | LOW | FE-missing | `membersLoadState` has no `error` state — a failed members fetch renders as "No members returned" (indistinguishable from an empty org). | Add an `error` state + distinct message. |
| S9 | LOW | a11y | Most save-feedback messages (retention, API-key, theme, event-plane) aren't in `aria-live` regions. | Wrap status messages in `aria-live="polite"` consistently. |
| S10 | LOW | a11y | `SettingsSectionNav` sets `aria-current` only from the `IntersectionObserver`; with IO unavailable the active highlight never updates. | Also set `aria-current` from the click handler. |
| S11 | LOW | UX | `SettingsActiveProjectSection` error branch ("Could not load projects") has no retry affordance. | Add a retry button. |
| S12 | LOW | scope-drift | RetentionPolicy helper text is dense (3 paragraphs referencing `plan_limits.py`, env vars, deprecated aliases) — observability-engineer-level detail. | Move env-var/alias detail to docs; one sentence per field in-UI. |

---

# 10. Onboarding — `/onboarding`

**Purpose.** A 3-step guided setup card: signed in → ingest key issued → first event
received, then "mark complete and continue".

### User stories

- As a new user, I want to confirm I'm signed in.
- As an owner/admin, I want to issue an ingest API key with one click and see/copy its
  value.
- As a member/viewer, I want clear guidance that an owner/admin must issue the key.
- As a new user, I want a copy-pasteable one-line FastAPI integration snippet.
- As a Django dev, I want a Django integration snippet (Lumonox supports FastAPI **and**
  Django).
- As a new user, I want to refresh and see whether my first event arrived.
- As a new user, I want concrete "next action" guidance when no data has arrived.
- As a new user, I want to mark onboarding complete and land on the dashboard.
- As a new user, I want to open the dashboard read-only before finishing.

### Featureset implemented

- Step 1 (session): static "Done" badge. Step 2 (ingest key): issue/refresh buttons,
  status pill, issued-key display, role-aware copy. Step 3 (first ingest): refresh
  button, status pill, no-data guidance, noise-control hint, FastAPI snippet.
- Role- and subpath-aware copy throughout; footer "Open dashboard (read-only)" + "Mark
  complete and continue"; activation telemetry; inline message line.
- `OnboardingCompletionNudge` — a separate dismissible banner shown on *other* pages.

### Backend endpoints consumed

- `POST /dashboard/auth/api-keys/issue`; `GET /dashboard/auth/api-keys`;
  `POST /dashboard/auth/onboarding-complete`; `GET /dashboard/bootstrap`.
- **Not consumed:** `GET /dashboard/auth/onboarding-status` (exists; FE only gets
  onboarding status via bootstrap / the complete response).

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| N1 | ~~HIGH~~ → **CORRECTED: not a bug** | broken-or-stub | **Audit false positive.** Verified against `sdk/src/lumonox/__init__.py` + `sdk/README.md`: `from lumonox import lumonox` / `lumonox(app, ...)` is valid and is the **recommended** form (`monitor` is the documented back-compat alias). The snippet does *not* throw `ImportError`. Real residual issues are folded into N3 (no Django variant) and N8 (lead with the bare one-liner). `DEVELOPMENT.md:185-191` shows the `monitor(app)` alias — also valid, left as-is. | No fix to the snippet's import. Address via N3 + N8: make `lumonox(app)` the clean primary one-liner, add a Django variant, demote noise-control kwargs. |
| N2 | HIGH | FE-missing | Step 3 "Refresh" only bumps `refreshToken` (refreshes the `POST /dashboard/query` bundle) — it does **not** refresh `onboardingStatus`. The step-3 pill and "Mark complete" enablement rely on a fallback rather than authoritative status; a user who genuinely sent an event can be stuck on "…". | Add `refreshOnboardingStatus()` to `DashboardDataContext` calling `GET /dashboard/auth/onboarding-status`; wire it to steps 2 & 3 "Refresh". |
| N3 | MEDIUM | FE-missing | No Django integration snippet, despite "FastAPI **and** Django" positioning. | Add a Django ASGI middleware snippet (or a FastAPI/Django toggle) from `sdk/docs/adapters.md`. |
| N4 | MEDIUM | broken-or-stub | Step 1 "Session" is a hard-coded "Done" badge; it never reads `onboardingStatus.session_authenticated`. | Drive the badge from `onboardingStatus?.session_authenticated` / `d.hasDashboardSession`. |
| N5 | MEDIUM | UX | `issueApiKey`/`refreshApiKeys`/`completeOnboarding` return `false`/silently return on non-OK without surfacing *why* (e.g. 400 "event required", permission); the `useAsyncAction` wrappers have no `.catch` for network errors. | Parse + surface `response.json().detail`; wrap async actions so network failures produce a visible message. |
| N6 | LOW | a11y | The inline result `message` and step status pills have no `role="status"` / `aria-live`; "…" pill content isn't meaningfully labeled. | Add `aria-live="polite"`; give pills `aria-label`. |
| N7 | LOW | UX | No copy-to-clipboard for the issued key or snippet. | Add a copy button next to `lastIssuedApiKey` and the snippet. |
| N8 | LOW | scope-drift | The snippet leads with `request_sample_rate` / `ignore_path_prefixes` kwargs — sampling + ignore-lists are "Build Soon After MVP"; adds cognitive load on the critical first-run path. | Keep the bare `monitor(app)` one-liner primary; move noise-control kwargs to a secondary disclosure. |

---

# 11. Studio widget pages — `/w/[pageId]`

**Purpose.** A dynamic route family rendering backend-defined "studio" widget pages.
Today exactly one page exists: `lx_showcase`.

### User stories

- As a solo dev, I want SDK-defined custom widgets to appear on their own dashboard page.
- As a dev evaluating Lumonox, I want a "layout lab" showing every widget type.
- As a backend/SDK author, I want to register a widget page server-side without a FE
  code change.

### Featureset implemented

- `generateStaticParams` emits one static route per id in
  `STUDIO_STATIC_ROUTE_PAGE_IDS` (currently `["lx_showcase"]`); unknown id → `notFound()`.
- Renders `DashboardBackendWidgetGalleryContent` filtered to one `page_id`.
- Widget data via the shared `POST /dashboard/query` batch; sidebar entries
  backend-driven from `GET /dashboard/bootstrap` → `studio_nav_pages`.
- Loading + amber empty/error states. Backend `studio_showcase.py` synthesizes the
  entire `lx_showcase` page (7 widgets, synthetic point series) and merges it into every
  `/widgets` response.

### Backend endpoints consumed

- `POST /dashboard/query` (batch, includes `widgets`); `GET /dashboard/bootstrap`.
- `GET /dashboard/widgets` exists and merges the showcase but is **not called** by these
  pages.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| W1 | HIGH | scope-drift | The Studio data model — multi-page registration + a layout grid with `section`/`column_span`/`row_span`/`layout_order`/`page_id` — is the infrastructure of a **custom dashboard builder**, an explicit MVP non-goal. Currently throttled to one synthetic page so it *presents* as progressive disclosure. | Scope this explicitly as "SDK-defined widgets render on a fixed gallery page"; feature-flag/drop the multi-page + layout-grid machinery until maintainers widen scope; document the decision. |
| W2 | HIGH | broken-or-stub | The only shipping studio page (`lx_showcase`) is **100% server-side synthetic data**, unconditionally injected into *every* project's `/widgets` and `/dashboard/query` response (`widgets.py:89`). Real users see fabricated routes (`/api/v1/orders`), fake envs, fake latency. | Gate the showcase merge behind a dev/demo flag (e.g. `LUMONOX_STUDIO_SHOWCASE_DEMO`), default off in production. |
| W3 | MEDIUM | broken-or-stub | `DashboardWidgetGalleryContent.tsx` (243 lines) is **dead code** — no route/component imports it. | Delete it (or wire it intentionally). |
| W4 | MEDIUM | FE-BE-mismatch | The static-route allowlist (`studioStaticRoutePageIds.ts`) must be hand-synced with `studio_nav_pages.py`; a backend-added page silently 404s until the TS array is updated and the export rebuilt. | Generate the allowlist from the backend list at build time, or make `/w/[pageId]` validate against `studioNavPages` from bootstrap at runtime. |
| W5 | LOW | UX | Page title/subtitle exist in both the backend `DashboardStudioNavPage` and a hardcoded `PAGE_META["/w/lx_showcase"]`. | Drop the `PAGE_META` entry; let the backend be the single source. |
| W6 | LOW | scope-drift | "Layout lab" naming + per-widget span descriptions expose grid-layout vocabulary to end users. | Rename to something diagnosis-oriented or move behind a docs/dev surface. |

---

# 12. Widgets Showcase / Showroom — `/widgets-showcase`, `/widgets-showroom`

**Purpose.** Two legacy URLs that now only `redirect()` to `/w/lx_showcase`. The
showcase/showroom *components* survive but are orphaned.

### User stories

- As a dev with no traffic yet, I want a mock preview of all widget/chart types.
- As a QA engineer, I want an always-mounted modal sample for Playwright.
- As a returning user with an old bookmark, I want the redirect to preserve my params.

### Featureset implemented

- `/widgets-showcase` → unconditional redirect (drops params). `/widgets-showroom` →
  redirect preserving `searchParams`.
- `WidgetsMockPreviewSection` (2s-interval synthetic data), `widgetsShowroomMockData.ts`
  (332 lines of mock builders), `WidgetsModalAccessibilitySample` (always-mounted modal
  for E2E), `DashboardChartShowcaseGrid` — all only referenced by the dead
  `DashboardWidgetGalleryContent`.

### Backend endpoints consumed

- None (pure redirects + in-browser synthetic data).

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| WS1 | HIGH | scope-drift | `widgetsShowroomMockData.ts` + `WidgetsMockPreviewSection` exist solely to render fabricated metrics; currently orphaned, bloating the bundle without being reachable. | Delete `WidgetsMockPreviewSection`, `widgetsShowroomMockData.ts`, `DashboardWidgetGalleryContent`. |
| WS2 | MEDIUM | broken-or-stub | `WidgetsModalAccessibilitySample` is production code whose only purpose is "so Playwright can verify Escape closes the modal". | Relocate to a test-only fixture, or assert modal behavior against a real modal in E2E. |
| WS3 | LOW | UX | `/widgets`, `/widgets-showcase`, `/widgets-showroom` all redirect to the same destination — redirect sprawl. | Keep one legacy alias if analytics show old links exist; drop the rest. |
| WS4 | LOW | FE-BE-mismatch | `/widgets-showcase` drops `searchParams` on redirect; `/widgets-showroom` preserves them — inconsistent. | Standardize a shared `redirectPreservingParams` helper. |

---

# 13. Magic-link auth — `/auth/magic-link`

**Purpose.** The magic-link landing page: user arrives from a sign-in email with
`?token=...`, the page POSTs the token to establish a session, then routes to
`/onboarding` or `/dashboard`.

### User stories

- As a dev, I want to click the link in my sign-in email and be signed in automatically.
- As a new user, I want to land on onboarding after first sign-in.
- As a returning user, I want to land on the dashboard directly.
- As a user with an expired/malformed link, I want a clear error and a way to get a fresh
  email.

### Featureset implemented

- Suspense boundary; reads/trims `token`; missing token → error state.
- `POST /dashboard/auth/magic-link/verify` with `credentials: "include"`; non-2xx → error.
- Post-verify `GET /dashboard/auth/onboarding-status` → destination `/onboarding` vs
  `/dashboard`; success → delayed `router.replace` + `router.refresh`.
- Three visual states (verifying/success/error) with `aria-live`, `role="status"`,
  `motion-reduce` handling; unmount cancellation guard.

### Backend endpoints consumed

- `POST /dashboard/auth/magic-link/verify`; `GET /dashboard/auth/onboarding-status`.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| M1 | MEDIUM | FE-missing | There is **no magic-link *request* page** — no canonical "enter your email to sign in" route. `POST /dashboard/auth/magic-link/request` exists but the only caller is the `ApiKeyMissing` fallback panel. | Add `/auth/login` (or `/auth/magic-link/request`) with an email form + "check your email" confirmation. |
| M2 | MEDIUM | FE-BE-mismatch | On verify failure the page tells users to "Request a new sign-in email" but the only action is "Back to dashboard", which loops through `ApiKeyMissing`. | Add a "Request new link" button that calls `/dashboard/auth/magic-link/request`. |
| M3 | MEDIUM | UX | No OIDC entry point — backend ships `GET /auth/oidc/login` + `/callback` but no `/auth` route surfaces a "Sign in with SSO" option. | Add an OIDC button on the sign-in page when `dashboard_oidc_enabled` (expose via bootstrap or a public config endpoint). |
| M4 | LOW | UX | Verify errors collapse to one generic message — a 401 (bad token) vs 5xx (backend down) vs network failure are indistinguishable. | Branch on `response.status` for "expired link" vs "service unavailable". |
| M5 | LOW | broken-or-stub | `oidc_routes.py:148` hardcodes a `post_login` fallback of `http://localhost:3000/lumonox/ui/` when `dashboard_oidc_post_login_redirect` is unset. | Fail closed (503) instead of redirecting to a localhost dev URL. |

---

# 14. Misc routes & shell

**Purpose.** The dashboard shell (sidebar + header + footer), the route-group layout
wiring the data provider, the global 404 / error boundaries, and redirect stubs.

### User stories

- As a user landing on `/` or the mounted UI root, I want to be taken to the dashboard.
- As a user with an old `/logs` or `/incidents` bookmark, I want to land on the renamed
  route with my scope preserved.
- As a user hitting a nonexistent URL, I want a clear "page not found" with a way back.
- As a user when the dashboard throws, I want a recoverable error screen.
- As any user, I want a consistent sidebar/header with diagnosis-first navigation.

### Featureset implemented

- `not-found.tsx` (branded 404 + "Go to Dashboard"); `(main)/error.tsx` (client error
  boundary, "Try again" / "Reload").
- `app/page.tsx` (`/` → `/dashboard`, preserves search); `logs/page.tsx` (`/logs` →
  `/requests`, preserves params); `incidents/page.tsx` (→ `/incident?saved_incidents=1`,
  **drops** params); `widgets/page.tsx` (→ `/w/lx_showcase`, **drops** params).
- `(main)/layout.tsx` + `DashboardLayoutClient` (data provider, scoped-query URL sync,
  session/onboarding gating, theme, status strip, workspace bootstrap retry).
- `AppShell` (collapsible sidebar, backend-driven studio nav, skip-to-content, live-data
  pulse dot, header command search, scope-aware nav hrefs).

### Backend endpoints consumed

- Directly: none. Indirectly via `DashboardDataProvider`: `GET /dashboard/bootstrap`,
  `GET /dashboard/auth/session`, `GET /dashboard/auth/onboarding-status`,
  `POST /dashboard/query`, `POST /dashboard/auth/onboarding-complete`.

### Gaps

| # | Severity | Category | Description | Suggested fix |
|---|---|---|---|---|
| X1 | ~~HIGH~~ → **CORRECTED: not a bug** | FE-BE-mismatch | **Audit false positive.** Verified: the backend's `index.html` fallback (`static_export_mount.py`) is standard SPA behavior — on a hard-load of an unknown `/lumonox/ui/*` route it serves `index.html`, the Next App Router hydrates at that URL, finds no match, and **renders `not-found.tsx` client-side**. `not-found.tsx` uses a basePath-aware `<Link href="/dashboard">`. The only nuance is the HTTP status is 200 not 404, which is the normal SPA tradeoff and fine for an internal dashboard. No code change needed. | None — confirmed reachable client-side. |
| X2 | MEDIUM | UX | `incidents/page.tsx` and `widgets/page.tsx` **drop incoming query params** on redirect, while `logs/page.tsx`, `widgets-showroom/page.tsx`, and `app/page.tsx` preserve them. | Standardize a shared `redirectPreservingParams` helper across all stub routes. |
| X3 | MEDIUM | scope-drift | The sidebar "Advanced" section routes users to Query Explorer (SQL) and Traces (OTLP) — near/at MVP non-goals. | Maintainer confirm these are intentionally widened scope (note it in `DEVELOPMENT.md`); otherwise gate behind a flag. |
| X4 | LOW | UX | `AppShell` renders an always-pulsing emerald "Live data" dot unconditionally — even when bootstrap failed / the WebSocket is down / no events exist. | Drive the dot from actual live-connection / freshness state. |
| X5 | LOW | UX | `(main)/error.tsx` renders raw `error.message` into the UI — can leak internal detail. | Show a generic message; keep detail in `console.error` only. |
| X6 | LOW | UX | `app/page.tsx` is a client redirect with a spinner; under static export the backend already redirects the root — two redirect hops to reach `/dashboard`. | Consider a static `index.html` meta-refresh or removing the client hop. |
| X7 | LOW | FE-BE-mismatch | `studioNavSidebarIcons.ts` whitelists 5 Lucide icons; `studio_nav_pages.py` only emits `"sparkles"` — any other backend icon string silently falls back to `LayoutGrid`. | Keep the whitelist in sync, or validate at the backend schema layer. |

---

# Cross-cutting themes

1. **Synthetic / fabricated data shipped to production.** The `lx_showcase` studio page
   injects synthetic widgets into *every* project's `/widgets` and `/dashboard/query`
   response (W2); `DashboardInfrastructureSection` fabricates DB/cache/dependency panels
   from unrelated data and labels them as real telemetry (O2/O3); `widgetsShowroomMockData`
   ships 332 lines of mock builders (WS1). **This is the highest-trust risk in the audit.**

2. **Backend work computed but never shown.** `diagnosis_timeline` / `diagnosis_failures`
   are fetched on every heavy query and gate the Diagnosis render, yet only their counts
   are displayed (D1) — directly underdelivering the "when did it break" half of the MVP
   promise.

3. **Dead / orphaned code.** `DashboardWidgetGalleryContent`, `WidgetsMockPreviewSection`,
   `WidgetsModalAccessibilitySample`, `widgetsShowroomMockData` (W3/WS1/WS2); the legacy
   non-phased `DashboardHomeContent` branch (O5); `POST /dashboard/log-query/execute` with
   no FE consumer (R1).

4. **Inconsistent error UX.** Bookmarks uses inline `role="alert"` banners; Incident uses
   blocking `window.alert()`; Alerts uses plain `<p>` + silent failures; `window.confirm`
   for destructive actions appears in Incident, Bookmarks, Settings. Standardize on the
   console design-system banner/toast + an in-app confirm modal.

5. **FE/BE config drift.** RBAC role enum mismatch (S1); studio static-route allowlist
   hand-sync (W4); alert preview using hard-coded constants instead of saved settings
   (A1/A2); `focus` param accepted but never sent (R2).

6. **Scope drift toward "thinking like an observability engineer."** Overview infra
   section (O1); Traces as a non-goal feature (T1); Query Explorer free-form SQL (Q1);
   the Studio dashboard-builder data model (W1); operator-plumbing Settings sections
   (S4); Incident SQL cells (I2). Several of these need a `DOCUMENTATION_GOVERNANCE.md`
   decision, not a silent code change.

7. **Unused-but-valuable backend surface.** `GET /dashboard/auth/onboarding-status`
   (would fix N2/N4), `GET /dashboard/alert-capabilities` + `POST /dashboard/alert-test`
   (would fix A3/A4) all exist server-side but aren't wired into the FE.

8. **Accessibility consistency.** Missing `role="status"`/`aria-live` on transient
   messages across Onboarding, Alerts, Settings, Incident; color-only state signalling on
   Overview, Traces.

---

# Proposed implementation backlog

Ordered by severity then trust impact. The maintainer-decision items are flagged — those
go through `DOCUMENTATION_GOVERNANCE.md` before any code lands.

### Phase 1 — Trust & correctness (BLOCKER/HIGH, no scope decision needed)

| ID | Gap | Area |
|---|---|---|
| P1.1 | ~~N1~~ — *withdrawn (audit false positive, snippet is valid)*; onboarding snippet improvements moved to P2.3 (N3 Django variant + N8 clean one-liner) | — |
| P1.2 | W2 — gate `lx_showcase` synthetic merge behind a dev/demo flag, default off | BE |
| P1.3 | O2/O3 — remove fabricated DB/cache/dependency infra panels (or honest empty state) | FE |
| P1.4 | D1 — render the diagnosis timeline chart + failures-by-route list | FE |
| P1.5 | A1/A2 — drive alert preview from saved `alertSettings` over the configured windows | FE |
| P1.6 | N2 — add `refreshOnboardingStatus()` + wire to step 2/3 "Refresh" | FE + (uses existing BE) |
| P1.7 | S1 — extend FE RBAC role selectors to the full 4-role enum | FE |
| P1.8 | O4 — populate `alerts_timeline` in the DuckDB overview path | BE |
| P1.9 | ~~X1~~ — *confirmed not a bug (404 boundary renders client-side via the App Router)* | — |
| P1.10 | S5 — verify/add server-side last-active-key revoke protection | BE |
| P1.11 | I1 — replace `window.alert()` in Incident with inline banners | FE |

### Phase 2 — Missing features wiring (MEDIUM, no scope decision needed)

| ID | Gap | Area |
|---|---|---|
| P2.1 | A3/A4 — surface "Send test alert" + alert-capabilities readiness on `/alerts` | FE |
| P2.2 | A5/A6 — dispatch-history loading/error state + `total`/pagination | FE |
| P2.3 | N3 — add Django integration snippet to onboarding | FE |
| P2.4 | M1/M2/M3 — add `/auth/login` request page + OIDC entry point + re-request action | FE |
| P2.5 | O6 — wire `onClick` drill-down on phased-lite Overview metric cards | FE |
| P2.6 | R3/R4 — label Requests stat tiles as "loaded rows"; consolidate pagination | FE |
| P2.7 | D2/D3 — fix top-failing-routes source; wire error-group event evidence to selection | FE |
| P2.8 | I3/I5/I6 — incident private/draft mode, hydration loading state, revoke action | FE + BE |
| P2.9 | S3 — reorder Settings sections (product first, operator last) | FE |
| P2.10 | S8 — add `error` state to `membersLoadState` | FE |
| P2.11 | X2 — shared `redirectPreservingParams` helper for redirect stubs | FE |
| P2.12 | T2/T3/T4 — real trace waterfall offsets; consistent error counts; scope-bar wiring | FE |
| P2.13 | B1/B2 — Bookmarks refresh control + pathname allowlisting | FE |
| P2.14 | W3/WS1/WS2 — delete orphaned showcase/showroom/gallery components | FE |
| P2.15 | O5 — delete the legacy non-phased `DashboardHomeContent` branch | FE |
| P2.16 | R1 — remove/quarantine `POST /dashboard/log-query/execute` | BE |
| P2.17 | W4 — generate studio static-route allowlist from the backend list | FE/BE |
| P2.18 | R2 — wire or drop the `focus` request param | FE/BE |

### Phase 3 — Polish: UX + a11y (LOW)

All remaining LOW items: O7–O10, D4–D8, R5–R9, I7–I10, B3–B6, A7–A12, Q3–Q7, T5–T7,
S6–S12, N4–N8, W5–W6, WS3–WS4, M4–M5, X3–X7. Batched by area (error-UX standardization,
`aria-live` pass, `window.confirm` → in-app modal, formatting consistency).

### Phase 0 — Maintainer scope decisions (block nothing else, but resolve before Phase 3)

These are **scope-drift** findings that need a `DOCUMENTATION_GOVERNANCE.md` call, not a
silent edit:

- **T1** — Traces is an explicit MVP non-goal ("distributed tracing"). Widen scope in
  `DEVELOPMENT.md`, or feature-flag the route.
- **W1** — Studio's multi-page + layout-grid model is custom-dashboard-builder
  infrastructure (explicit non-goal). Decide: constrain to a fixed gallery page, or widen
  scope.
- **Q1** — Query Explorer free-form SQL exceeds the "SQL-scoped filters" progressive-
  disclosure example. Document it explicitly or reduce to parameterized templates.
- **O1** — Overview infra section vs the "5-second diagnosis" mandate.
- **S4** — operator-plumbing Settings sections (EventPlaneCutover, SystemDiagnostics,
  InternalMetrics) — keep in product Settings or move to a separate `/ops` surface.
- **I2 / X3 / D8 / A12** — SQL cells, sidebar "Advanced" section, jobs-on-diagnosis-path,
  runbook CLI shortcuts.

---

*End of audit. Next step: maintainer review → confirm Phase 0 scope decisions → implement
Phase 1 → 2 → 3.*
