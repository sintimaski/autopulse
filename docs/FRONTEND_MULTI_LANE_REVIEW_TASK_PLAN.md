# Frontend Multi-Lane Review and Development Task Plan

Use this plan to execute a full frontend quality uplift across UX/UI, visual polish, DX, QoL, and maintainability for Lumonox dashboard MVP.

## 1) Plan header

- **Plan name:** Frontend multi-lane quality review -> implementation backlog
- **Owner:** Frontend + Platform (AI-assisted execution)
- **Date:** 2026-05-10
- **Status:** In progress (phase 1 shipped; refactors and validation backlog remain)
- **Scope summary (2-4 lines):**
  This plan converts a codebase-wide frontend review into execution tasks. It prioritizes high-impact UX clarity, visual consistency, accessibility, and developer productivity improvements while preserving Lumonox MVP constraints (fast diagnosis, low-friction onboarding, no advanced non-goal platform features).
- **Out of scope:**
  New product surfaces outside current MVP navigation; custom dashboard builder; distributed tracing UX redesign; backend schema redesign unrelated to frontend safety/consistency.

## 1b) As-built implementation record

**Important:** Not every task in section 5 is implemented in code. The table below is the source of truth versus `frontend/` as of the last plan edit.

| Task | Status | Notes |
|------|--------|--------|
| FE-01 | **Done** | Root `/` and magic-link `Suspense` use `CardSpinner` (`frontend/app/page.tsx`, `frontend/app/auth/magic-link/page.tsx`). |
| FE-02 | **Done** | Segment error and global not-found use `ap-surface` / `ap-btn*` (`frontend/app/(main)/error.tsx`, `frontend/app/not-found.tsx`). Optional extra snapshot/a11y tests from the original AC were not added (explicit defer). |
| FE-03 | **Done (superseded scope)** | Command palette was **removed** as redundant with the sidebar (`DashboardCommandPalette.tsx` deleted; not mounted from `DashboardLayoutClient.tsx`). `NavIaMigrationBanner` copy updated to sidebar-only. Original “add palette discoverability” work was **intentionally dropped**. |
| FE-04 | **Partial** | Overview traffic summaries (`aria-live`), Query Explorer / Traces labels, `TimeSeriesLineChart` `aria-describedby` + screen-reader trend line. Full chart/a11y audit still open. |
| FE-05 | **Partial** | WebSocket lifecycle in `live/useDashboardLiveWebSocket.ts`; fallback poll + visibility in `live/useDashboardLiveClientEffects.ts`; `bumpDashboardDataRefresh` in provider. Context file still large (value assembly / slice wiring). |
| FE-06 | **Partial** | `settingsContentTypes.ts`, `SettingsAppearanceSessionSection.tsx`, **`SettingsRetentionPolicySection.tsx`**, **`SettingsInternalMetricsSection.tsx`**. Other settings sections still inline. |
| FE-07 | **Partial** | Above plus **`parseDashboardDataQueryResponse`** in `frontend/utils/dashboardQueryResponseGuards.ts` for **`POST /dashboard/query`** (main fetch + diagnosis follow-up). |
| FE-08 | **Partial** | **`DashboardDataContext`** dashboard mutations use **`fetchWithTimeout`** (alert/theme/retention, api-keys, active-project, validate, logout, etc.). Further dedup vs context still open. |
| FE-09 | **Partial** | Guard unit tests (`dashboardResponseGuards.test.ts`) + Playwright **`settings-smoke.spec.ts`** (shared `authDevMagicLink.ts`). Further interaction coverage still open. |
| FE-10 | **Partial** | `frontend/README.md` architecture section; ESLint **`reportUnusedDisableDirectives: warn`**. Heavier custom rules still open. |

## 2) Context / background

- Problem statement: Frontend quality is uneven across key lanes (UX flow smoothness, visual consistency, discoverability, accessibility, code modularity, and test depth).
- Why now: Current architecture is functional but concentrated in several large files, increasing change risk and slowing iteration.
- Current behavior (as-is): Dashboard works end-to-end but contains blank transitional states, mixed styling patterns, large context/components, and limited interaction testing coverage.
- Desired behavior (to-be): Consistent and polished UX, improved accessibility and discoverability, safer typed data boundaries, smaller modular components/hooks, and stronger regression guardrails.
- User impact: Faster diagnosis and fewer confusing states for operators; better confidence when navigating and sharing scoped views.
- Technical impact: Reduced maintenance overhead, lower regression probability, clearer ownership boundaries, and improved onboarding for contributors.

## 3) Domain rules and constraints

- Product/domain rules: Keep workflows focused on "what broke, when, and what requests led to it"; avoid MVP scope expansion.
- Security/privacy rules: Do not expose secrets/tokens in UI logs; preserve existing auth and key flows.
- Performance/SLO constraints: Maintain static export compatibility and route bundle budget discipline; avoid heavy runtime overhead in hot paths.
- Compliance/governance constraints: Keep documentation aligned with `DEVELOPMENT.md` and governed doc policies.
- Non-goals: Custom query language UX expansion, enterprise permission system redesign, broad platform theming rewrite.

## 4) Inputs, outputs, and dependencies

- **Inputs:** Frontend code under `frontend/`, current docs, lint/test/build scripts, bundle budget script.
- **Outputs:** Code changes, updated frontend docs, tests, and verification notes.
- **Dependencies:** Frontend maintainers, backend contract stability for existing APIs, CI checks.
- **Tools available:** Cursor IDE, TypeScript, Next.js, Vitest, Playwright, ESLint, npm scripts.

## 5) Task breakdown

### Task `FE-01`: Remove blank transitional states in entry/auth flows

- **Description:** Replace blank render transitions in root redirect and magic-link verification with explicit loading/status UI.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Navigating to `/` never displays a blank page; a loading/status shell appears until redirect completes.
  - AC2: Magic-link verification route provides a visible and screen-reader-friendly fallback while params resolve.
  - AC3: No regression to auth success/failure behavior.
- **Inputs:** `frontend/app/page.tsx`, `frontend/app/auth/magic-link/page.tsx`, shared spinner/status components.
- **Outputs:** Updated loading/redirect UX and associated tests.
- **Dependencies:** None.
- **Constraints:** Preserve static-export compatibility and existing redirect destination.
- **Tools available:** Next.js App Router, shared dashboard UI components, Vitest/Playwright.
- **Steps / plan:**
  1. Implement non-null fallback UI for root redirect and magic-link suspense.
  2. Reuse existing status/spinner component style for consistency.
  3. Add/adjust tests for visible loading states and successful navigation.
- **Error handling:**
  - Expected failure modes: Unexpected auth token states; fallback persists too long.
  - Recovery steps: Guard fallback with completion conditions and timeout-safe path.
  - Rollback/backout conditions: If auth flow regressions appear in E2E, revert to prior navigation behavior and ship only test scaffolding.
- **Validation / verification:**
  - Automated checks: `npm run lint`, targeted unit tests, core E2E journey.
  - Manual checks: Visit `/` and magic-link URL; confirm no blank frames.
  - Observed evidence: Video/screenshot capture or test logs.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-10
  - Owner: Frontend
- **Implementation notes:** Shipped in commit `deb0eb3` (loading UI); pre-commit ran `frontend-eslint`, `frontend-typecheck`, `frontend-build`. Dedicated unit tests for these routes were not added (defer).
- **Related documents:** `frontend/README.md`, `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `frontend/components/dashboard/DashboardPageBoundary.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: Default to least intrusive loading pattern used elsewhere in dashboard.
  - If data conflicts: Prioritize actual route behavior over comments.
  - Escalation owner: Frontend tech lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Optional client timing marks for redirect and verify flow.
  - Alert thresholds: N/A
  - Success signals: Drop in "blank/unclear auth loading" QA reports.

### Task `FE-02`: Standardize visual consistency for error and not-found surfaces

- **Description:** Align error and 404 pages with dashboard design tokens and dark/light behavior.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Error and 404 pages use shared button/input/card visual language.
  - AC2: Keyboard focus states are visible and consistent with global focus ring patterns.
  - AC3: Dark mode does not visually clash with dashboard shell.
- **Inputs:** `frontend/app/(main)/error.tsx`, `frontend/app/not-found.tsx`, `frontend/app/globals.css`.
- **Outputs:** Token-aligned error/404 components with snapshot or component tests.
- **Dependencies:** FE-01 optional (can run in parallel).
- **Constraints:** Keep copy concise and operationally clear.
- **Tools available:** Existing CSS utility classes and shared UI primitives.
- **Steps / plan:**
  1. Replace ad-hoc classes with shared token/button patterns.
  2. Ensure focus-visible styles and dark mode parity.
  3. Add test coverage for classes/accessibility attributes.
- **Error handling:**
  - Expected failure modes: Styling regressions in static export.
  - Recovery steps: Revert to prior classes for broken sections and iterate.
  - Rollback/backout conditions: If theme regressions affect critical routes.
- **Validation / verification:**
  - Automated checks: Lint/build/component tests.
  - Manual checks: Trigger route error and 404 in both themes.
  - Observed evidence: Before/after screenshots.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-10
  - Owner: Frontend
- **Implementation notes:** Token-aligned surfaces shipped in commit `deb0eb3`. Snapshot/component tests called out in AC3 were not added (defer).
- **Related documents:** `frontend/README.md`
- **References / examples:** `frontend/components/dashboard/AppShell.tsx`, `frontend/app/globals.css`
- **Ambiguity handling:**
  - If requirement is unclear: Mirror AppShell tokens as baseline.
  - If data conflicts: Follow rendered result over static assumptions.
  - Escalation owner: Design owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: N/A
  - Alert thresholds: N/A
  - Success signals: Visual regression snapshots pass across theme variants.

### Task `FE-03`: Navigation QoL — sidebar as single surface (command palette removed)

- **Description:** **Supersedes** the earlier “improve command palette discoverability” idea. The command palette duplicated `DASHBOARD_NAV_SECTIONS`; product decision is **sidebar-only** navigation. Palette component and global `Cmd/Ctrl+K` handler were removed; migration banner copy points users to **Advanced** in the sidebar.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: No duplicate navigation system (palette removed; no orphaned ⌘K UX promises in chrome).
  - AC2: Users can reach all former palette destinations via existing sidebar nav.
  - AC3: `npm run build` succeeds after removal (static export / basePath unchanged).
- **Inputs:** `frontend/components/dashboard/DashboardLayoutClient.tsx`, `frontend/components/dashboard/NavIaMigrationBanner.tsx`, `frontend/components/dashboard/dashboardNavConfig.ts`.
- **Outputs:** Deleted `DashboardCommandPalette.tsx`; layout no longer mounts palette; banner text updated.
- **Dependencies:** None.
- **Constraints:** Preserve minimal chrome and performance.
- **Tools available:** Sidebar nav config only.
- **Steps / plan:**
  1. Remove palette mount and delete component file.
  2. Update any user-facing copy that referenced ⌘K / palette.
  3. Verify build and core manual navigation.
- **Error handling:**
  - Expected failure modes: Duplicate event handlers or focus traps.
  - Recovery steps: Consolidate to single open state handler.
  - Rollback/backout conditions: Palette usability regression.
- **Validation / verification:**
  - Automated checks: `npm run lint`, `npm run build` (pre-commit frontend pipeline).
  - Manual checks: Confirm ⌘K/Ctrl+K does nothing; navigate via sidebar to former palette targets.
  - Observed evidence: Commit `deb0eb3` + green build.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Done
  - % complete: 100
  - Last update: 2026-05-10
  - Owner: Frontend
- **Related documents:** `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `frontend/components/dashboard/dashboardNavConfig.ts`
- **Ambiguity handling:**
  - If requirement is unclear: Prefer smallest visible affordance that does not distract from main KPIs.
  - If data conflicts: Trust user-testing feedback over aesthetic preference.
  - Escalation owner: Product owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Optional palette open count and selection count.
  - Alert thresholds: N/A
  - Success signals: Increased palette usage and lower navigation friction feedback.

### Task `FE-04`: Accessibility pass on high-traffic dashboard interactions

- **Description:** Improve labels, focus handling, and chart-adjacent textual summaries for core diagnosis workflows.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: High-traffic inputs (e.g. scope, filters, modals) have explicit labels / `aria-*` where missing (palette removed — no palette input).
  - AC2: All critical interactive controls in overview/diagnosis paths have visible focus behavior.
  - AC3: Core charts expose concise textual trend summaries.
- **Inputs:** Chart panels, diagnosis/overview pages, modals/menus.
- **Outputs:** Accessibility-focused refinements and tests/checklist.
- **Dependencies:** FE-02 recommended.
- **Constraints:** Keep copy concise; no large non-MVP accessibility platform project.
- **Tools available:** Existing semantic components and ARIA patterns in codebase.
- **Steps / plan:**
  1. Audit keyboard/screen-reader behavior on key flows.
  2. Patch labeling/focus gaps.
  3. Add concise text summaries under selected charts.
- **Error handling:**
  - Expected failure modes: Over-verbose UI text.
  - Recovery steps: Keep summaries one line and data-driven.
  - Rollback/backout conditions: If chart cards become visually noisy.
- **Validation / verification:**
  - Automated checks: Lint + accessibility-focused component tests.
  - Manual checks: Keyboard traversal and screen reader spot checks.
  - Observed evidence: Accessibility checklist log.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend
- **Related documents:** `DEVELOPMENT.md`
- **References / examples:** `frontend/components/dashboard/DashboardDetailModal.tsx`, `frontend/components/dashboard/MetricCard.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: Prioritize keyboard and labeling fixes over broader AA-level redesign.
  - If data conflicts: Validate against actual chart data shape in context.
  - Escalation owner: Frontend + product
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: N/A
  - Alert thresholds: N/A
  - Success signals: Fewer accessibility defects in QA and reviews.

### Task `FE-05`: Decompose `DashboardDataContext` into focused hooks/modules

- **Description:** Refactor the large provider into maintainable units without behavior regressions.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Provider responsibilities are split into focused modules (bootstrap, fetching, live updates, filters/scope, slices).
  - AC2: Public context contract remains backward-compatible for existing consumers.
  - AC3: Performance and live update behavior are unchanged or improved.
- **Inputs:** `frontend/components/dashboard/DashboardDataContext.tsx` and dependent hooks/components.
- **Outputs:** New module structure and compatibility layer.
- **Dependencies:** FE-08 recommended for safer API boundaries.
- **Constraints:** No product behavior drift.
- **Tools available:** TypeScript, existing slice contexts, unit tests.
- **Steps / plan:**
  1. Extract pure helpers and side-effect domains into separate hooks.
  2. Keep thin provider orchestration layer with existing exports.
  3. Add regression tests around route/scoped fetch/live update flows.
- **Error handling:**
  - Expected failure modes: Stale closures, missed dependencies, websocket lifecycle bugs.
  - Recovery steps: Introduce staged extraction with snapshots and focused tests.
  - Rollback/backout conditions: Any live data or scope synchronization regressions.
- **Validation / verification:**
  - Automated checks: Lint, typecheck, targeted tests, full frontend build.
  - Manual checks: Core dashboard navigation and data refresh behaviors.
  - Observed evidence: No change in key metrics/cards and scope filters.
- **Idempotency (re-run safety):**
  - Safe to re-run? Partial
  - If partial/no, guardrails required: Keep each extraction branch small and mergeable.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend platform
- **Related documents:** `frontend/README.md`
- **References / examples:** `frontend/components/dashboard/data/useDashboardSlices.ts`
- **Ambiguity handling:**
  - If requirement is unclear: Preserve current context API shape, refactor internals only.
  - If data conflicts: Trust runtime behavior and tests over inferred abstractions.
  - Escalation owner: Frontend architect
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Optional debug metrics for fetch cycles during refactor branch.
  - Alert thresholds: N/A
  - Success signals: Reduced file size/complexity and stable behavior.

### Task `FE-06`: Split `SettingsContent` into domain-focused modules

- **Description:** Refactor `SettingsContent` into smaller sections/hooks to improve readability, ownership, and testing.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: `SettingsContent` is broken into coherent section modules with clear interfaces.
  - AC2: No regression in settings save/test actions.
  - AC3: Section-level tests cover critical settings flows.
- **Inputs:** `frontend/components/dashboard/dashboardPages/SettingsContent.tsx`.
- **Outputs:** Modular settings architecture.
- **Dependencies:** FE-05 optional.
- **Constraints:** Preserve existing API interactions and permission assumptions.
- **Tools available:** React composition, context hooks, test harness.
- **Steps / plan:**
  1. Identify coherent sections and extract local hooks/components.
  2. Keep shared helpers/types in dedicated files.
  3. Add tests for alerts/members/org key interactions.
- **Error handling:**
  - Expected failure modes: State desync across sections.
  - Recovery steps: Lift only truly shared state; keep section-local state local.
  - Rollback/backout conditions: Broken save/test actions.
- **Validation / verification:**
  - Automated checks: Lint/typecheck/tests/build.
  - Manual checks: Settings page full happy-path and error-path run-through.
  - Observed evidence: Existing API calls still fire with expected payloads.
- **Idempotency (re-run safety):**
  - Safe to re-run? Partial
  - If partial/no, guardrails required: Merge in section slices, not one giant rewrite.
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend
- **Related documents:** `frontend/README.md`
- **References / examples:** `frontend/components/dashboard/dashboardPages/AlertsContent.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: Keep current settings IA unchanged.
  - If data conflicts: Validate against backend contract and current UI behavior.
  - Escalation owner: Frontend lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Existing error messages plus optional section-level client error tags.
  - Alert thresholds: N/A
  - Success signals: Smaller file and faster review cycles.

### Task `FE-07`: Introduce typed API response validation for critical routes

- **Description:** Add a shared response parsing layer with runtime validation for high-risk endpoints to reduce unsafe casts.
- **Priority:** P0
- **Acceptance criteria (AC):**
  - AC1: Critical dashboard responses are parsed through shared helper(s) rather than direct `as` casts.
  - AC2: Validation failures surface clear, actionable frontend errors.
  - AC3: Existing happy-path behavior remains unchanged.
- **Inputs:** Fetch call sites across dashboard pages and context.
- **Outputs:** Shared typed parser + migrated high-priority call sites.
- **Dependencies:** None.
- **Constraints:** Keep parsing overhead bounded.
- **Tools available:** TypeScript schemas/guards, existing fetch utilities.
- **Steps / plan:**
  1. Implement shared parse utility and error mapper.
  2. Migrate critical paths (overview, diagnosis, traces/query explorer, settings updates).
  3. Add tests for invalid payload handling.
- **Error handling:**
  - Expected failure modes: False positives on permissive backend payloads.
  - Recovery steps: Start strict only on known stable fields, broaden incrementally.
  - Rollback/backout conditions: If parser causes user-visible failures on valid backend responses.
- **Validation / verification:**
  - Automated checks: Unit tests for parser + integration checks.
  - Manual checks: Validate unaffected happy paths and clearer failures.
  - Observed evidence: Removed unsafe cast hot spots.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend platform
- **Related documents:** `docs/contracts/ingest-api.md`
- **References / examples:** `frontend/components/dashboard/dashboardPages/QueryExplorerContent.tsx`, `frontend/components/dashboard/dashboardPages/TracesContent.tsx`
- **Ambiguity handling:**
  - If requirement is unclear: Parse minimum required fields first.
  - If data conflicts: Escalate with payload samples and contract diff.
  - Escalation owner: Frontend + backend API owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Client-side parse error counters (non-sensitive).
  - Alert thresholds: Spike in parse failures after deploy.
  - Success signals: Reduced runtime shape mismatch bugs.

### Task `FE-08`: Unify fetch/error handling and remove duplicated memoization patterns

- **Description:** Standardize request helpers and remove duplicate context slice memo logic.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Query/traces/settings fetch paths share timeout/error normalization patterns.
  - AC2: Duplicate `useMemo` wrapper in slice hooks is removed or justified with explicit comment/tests.
  - AC3: No user-facing latency/error regression.
- **Inputs:** Fetch utilities, `useDashboardSlices.ts`, query/traces/settings components.
- **Outputs:** Reduced duplication and clearer data-flow contracts.
- **Dependencies:** FE-07 recommended.
- **Constraints:** Keep code changes incremental and reviewable.
- **Tools available:** Existing `dashboardDataFetchUtils.ts`, `dashboardFetchErrors.ts`.
- **Steps / plan:**
  1. Migrate outlier fetch logic to shared helpers.
  2. Normalize cancellation and timeout handling.
  3. Simplify or document memoization layers.
- **Error handling:**
  - Expected failure modes: Changed error messaging semantics.
  - Recovery steps: Snapshot error text expectations in tests.
  - Rollback/backout conditions: Regression in request page failure handling.
- **Validation / verification:**
  - Automated checks: Tests for helper behavior and hooks.
  - Manual checks: Simulate network failures and inspect UI states.
  - Observed evidence: Fewer custom fetch blocks and consistent errors.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend
- **Related documents:** `frontend/README.md`
- **References / examples:** `frontend/utils/dashboardFetchErrors.ts`, `frontend/utils/dashboardDataFetchUtils.ts`
- **Ambiguity handling:**
  - If requirement is unclear: Prefer existing shared helper semantics.
  - If data conflicts: Prioritize consistency with dashboard boundary error handling.
  - Escalation owner: Frontend lead
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Optional categorized network failure telemetry.
  - Alert thresholds: N/A
  - Success signals: Consistent error UX across pages.

### Task `FE-09`: Expand automated frontend test coverage for interaction-critical paths

- **Description:** Improve test depth from static render checks toward interaction and context behavior.
- **Priority:** P1
- **Acceptance criteria (AC):**
  - AC1: Core interaction tests cover scope sync, modal keyboard behavior, and at least one settings path (palette removed — no palette tests).
  - AC2: At least one additional Playwright flow beyond current core journey is added.
  - AC3: CI signal quality improves (fewer regressions escaping review).
- **Inputs:** Existing tests under `frontend/components/**/*.test.tsx`, `frontend/tests/e2e`.
- **Outputs:** Added unit/integration/E2E tests and updated test docs.
- **Dependencies:** FE-01 to FE-04 preferred first.
- **Constraints:** Keep runtime manageable in CI.
- **Tools available:** Vitest, Testing Library setup, Playwright.
- **Steps / plan:**
  1. Add interaction tests for critical UI controls.
  2. Add E2E path for settings or query explorer.
  3. Document and enforce test execution order in CI/dev workflow.
- **Error handling:**
  - Expected failure modes: Flaky async/timing tests.
  - Recovery steps: Add deterministic waits and stable selectors.
  - Rollback/backout conditions: Test suite instability blocking deploys.
- **Validation / verification:**
  - Automated checks: `npm run test`, selected `npm run e2e`.
  - Manual checks: Re-run known flaky cases twice.
  - Observed evidence: Green CI with stable reruns.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: QA + Frontend
- **Related documents:** `docs/testing/E2E_CORE_JOURNEY.md`
- **References / examples:** `frontend/tests/e2e/core-journey.spec.ts`
- **Ambiguity handling:**
  - If requirement is unclear: Prioritize flows with highest customer impact.
  - If data conflicts: Validate against production-like seed data.
  - Escalation owner: QA owner
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: Test run duration and flaky test tracker.
  - Alert thresholds: Flake rate >5% weekly.
  - Success signals: Increased confidence and reduced hotfixes.

### Task `FE-10`: DX and quality guardrails (lint policy, architecture notes, contributor QoL)

- **Description:** Add practical contributor guardrails to reduce drift and improve onboarding speed.
- **Priority:** P2
- **Acceptance criteria (AC):**
  - AC1: Frontend docs describe architecture boundaries (context vs local state vs utils/lib).
  - AC2: ESLint rules are modestly tightened for consistency and maintainability.
  - AC3: Contributor workflow docs include recommended checks and expected troubleshooting.
- **Inputs:** `frontend/eslint.config.mjs`, `frontend/README.md`.
- **Outputs:** Updated DX docs and lint configuration.
- **Dependencies:** None.
- **Constraints:** Avoid noisy lint rules that block normal iteration.
- **Tools available:** ESLint, markdown docs, npm scripts.
- **Steps / plan:**
  1. Add architecture/contribution section to README.
  2. Introduce incremental lint constraints.
  3. Validate minimal false-positive impact with team trial.
- **Error handling:**
  - Expected failure modes: Excess lint noise.
  - Recovery steps: Downgrade contentious rules to warnings initially.
  - Rollback/backout conditions: Significant developer productivity drop.
- **Validation / verification:**
  - Automated checks: Lint pass in CI and local.
  - Manual checks: New contributor dry-run setup.
  - Observed evidence: Reduced onboarding questions and PR review churn.
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes
  - If partial/no, guardrails required: N/A
- **State / progress tracking:**
  - Status: Todo
  - % complete: 0
  - Last update: 2026-05-10
  - Owner: Frontend platform
- **Related documents:** `docs/DEVELOPMENT_PROCESS.md`
- **References / examples:** `frontend/README.md`
- **Ambiguity handling:**
  - If requirement is unclear: Favor low-friction defaults.
  - If data conflicts: Align with current CI behavior and standards.
  - Escalation owner: Engineering manager
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add: N/A
  - Alert thresholds: N/A
  - Success signals: Shorter PR cycle time and fewer style-only comments.

## 6) Plan-level execution strategy

- Delivery sequence:
  1. P0 reliability/safety foundations: FE-01, FE-05, FE-07.
  2. UX and consistency uplift: FE-02, FE-03, FE-04.
  3. Maintainability cleanup: FE-06, FE-08.
  4. Quality hardening and DX guardrails: FE-09, FE-10.
- Parallelization opportunities:
  - FE-02 and FE-03 can run in parallel after FE-01 starts.
  - FE-06 can run in parallel with FE-08 once FE-05 interfaces stabilize.
  - FE-09 starts as soon as FE-01..FE-04 components are merged.
- Risk register (top 3-5):
  - Large refactors (FE-05/FE-06) may introduce subtle state regressions.
  - Runtime validation (FE-07) may reject backend payload variants unexpectedly.
  - Test expansion (FE-09) may initially increase flakiness.
  - Lint tightening (FE-10) may create contributor friction if over-applied.
- Decision log:
  - Decision: Prioritize diagnosis-flow UX reliability and context refactor first.
  - Why: Highest user and developer impact with broad downstream benefits.
  - Date: 2026-05-10
  - Owner: Frontend tech lead
  - Decision: Remove command palette; sidebar is the single navigation surface.
  - Why: Duplicate navigation added complexity without MVP benefit; aligns with operator mental model.
  - Date: 2026-05-10
  - Owner: Product + Frontend

## 7) Validation gate before completion

Mark each item before closing the plan:

- [x] All tasks have explicit AC.
- [x] All tasks define validation (automated + manual).
- [x] Idempotency is documented for each task.
- [x] Domain rules and constraints are mapped to tasks.
- [ ] Observability updates are included where behavior changed (deferred: no new client metrics in phase 1).
- [x] Related docs are updated or explicitly deferred (this plan records as-built vs backlog).
- [ ] Remaining ambiguity is logged with owner and due date (open for FE-04..FE-10 sequencing).

**Plan closure:** Do **not** mark the overall plan **Done** until FE-04..FE-10 are either implemented or formally **cancelled/de-scoped** with owner sign-off. Phase 1 (FE-01..FE-03) is complete as documented in section 1b.
