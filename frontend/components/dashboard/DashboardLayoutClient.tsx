"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { applyDashboardScopedQueryState } from "./applyDashboardScopedQuery";
import { DashboardAppShell } from "./AppShell";
import { ApiKeyMissing, DashboardSessionRestoring } from "./DashboardPageBoundary";
import { DashboardDataProvider, useDashboardData } from "./DashboardDataContext";
import { buildLiveDashboardSearchString, parseLogsClientSearchParams } from "./dashboardLogsViewUrl";
import {
  DEFAULT_LOGS_VIEW_CLIENT,
  readPersistedDashboardSession,
  type PersistedLogsClientSlice,
} from "./dashboardPersistentScope";
import { ServerQueryToolbar } from "./ServerQueryToolbar";
import {
  buildCurrentScopedState,
  buildScopedQuery,
  parseScopedQuery,
  scopedQueryStringsEqual,
  type DashboardScopedQueryState,
} from "./dashboardQueryState";
import { toDashboardRoutePath } from "./dashboardRoutePath";
import { resetServerScope } from "./dashboardScopeReset";
import { scheduleDashboardViewportScrollRestore } from "./dashboardViewportScroll";
import { isApiSubpathDashboard } from "./dashboardTypes";

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Overview",
    subtitle:
      "Health snapshot — Overview scope uses the same URL keys as Diagnosis and Requests; open those pages for path, latency, or advanced filters.",
  },
  "/widgets-showcase": {
    title: "Widgets",
    subtitle: "Live SDK charts from your scope plus a timer-driven mock preview.",
  },
  "/widgets-showroom": {
    title: "Widgets",
    subtitle: "This URL forwards to the unified widgets page.",
  },
  "/requests": {
    title: "Requests",
    subtitle: "Request-level evidence — same investigation scope as Overview and Diagnosis.",
  },
  "/diagnosis": {
    title: "Errors & Diagnosis",
    subtitle: "Grouped failures and signals — start here when something breaks.",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Alert heuristics, settings, and runbook shortcuts.",
  },
  "/query-explorer": {
    title: "Query Explorer",
    subtitle: "Run full SQL against project-scoped events with guardrails.",
  },
  "/traces": {
    title: "Traces (OTLP)",
    subtitle: "Search and inspect spans ingested via OTLP HTTP.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Project defaults, theme, and delivery channels.",
  },
  "/bookmarks": {
    title: "Bookmarks",
    subtitle: "Your saved deep links for this project — open, rename, or remove.",
  },
  "/logs": {
    title: "Requests",
    subtitle: "This URL forwards to Requests — bookmark /requests for clarity.",
  },
  "/onboarding": {
    title: "Onboarding",
    subtitle: ".env.autopulse, first ingest, diagnosis.",
  },
};

type ScopedServerState = {
  isAbsoluteWindow: boolean;
  windowMinutes: number;
  windowFromTimestamp: string;
  windowToTimestamp: string;
  method: string;
  statusClass: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  pathQuery: string;
  serverEnvironmentQuery: string;
  serverServiceQuery: string;
  requestLimit: number;
  requestPage: number;
  errorGroupLimit: number;
  errorGroupPage: number;
  errorGroupSort: "last_seen" | "count";
  sqlFilterDraft: string;
  sqlFilterApplied: string;
  sqlFilterEnabled: boolean;
};

function isScopedUrlSyncRoute(pathname: string): boolean {
  return (
    pathname === "/dashboard" ||
    pathname === "/diagnosis" ||
    pathname === "/logs" ||
    pathname === "/requests"
  );
}

function isScopedPathRestoreRoute(pathname: string): boolean {
  return pathname === "/diagnosis" || pathname === "/logs" || pathname === "/requests";
}

function buildDefaultScopedState(d: ReturnType<typeof useDashboardData>): ScopedServerState {
  return {
    isAbsoluteWindow: false,
    windowMinutes: 60,
    windowFromTimestamp: d.windowFromTimestamp,
    windowToTimestamp: d.windowToTimestamp,
    method: "ALL",
    statusClass: "ALL",
    minLatencyMs: "",
    maxLatencyMs: "",
    pathQuery: "",
    serverEnvironmentQuery: "",
    serverServiceQuery: "",
    requestLimit: 100,
    requestPage: 0,
    errorGroupLimit: 25,
    errorGroupPage: 0,
    errorGroupSort: "last_seen",
    sqlFilterDraft: "",
    sqlFilterApplied: "",
    sqlFilterEnabled: false,
  };
}

function scopedServerStateToParsed(state: ScopedServerState): DashboardScopedQueryState {
  return {
    isAbsoluteWindow: state.isAbsoluteWindow,
    windowMinutes: state.windowMinutes,
    windowFromTimestamp: state.windowFromTimestamp,
    windowToTimestamp: state.windowToTimestamp,
    method: state.method,
    statusClass: state.statusClass,
    minLatencyMs: state.minLatencyMs,
    maxLatencyMs: state.maxLatencyMs,
    pathQuery: state.pathQuery,
    serverEnvironmentQuery: state.serverEnvironmentQuery,
    serverServiceQuery: state.serverServiceQuery,
    requestLimit: state.requestLimit,
    requestPage: state.requestPage,
    errorGroupLimit: state.errorGroupLimit,
    errorGroupPage: state.errorGroupPage,
    errorGroupSort: state.errorGroupSort,
    sqlFilterApplied: state.sqlFilterApplied,
    sqlFilterEnabled: state.sqlFilterEnabled,
  };
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(value);
    }, delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, value]);
  return debounced;
}

function ShellWithData({ children }: { children: ReactNode }) {
  const rawPathname = usePathname();
  const pathname = toDashboardRoutePath(rawPathname);
  const router = useRouter();
  const searchParams = useSearchParams();
  const d = useDashboardData();
  const [systemPrefersDark, setSystemPrefersDark] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)").matches : false,
  );
  const lastAppliedQueryRef = useRef<string>("");
  const scopedStateRef = useRef<Record<string, ScopedServerState>>({});
  const previousPathRef = useRef(pathname);
  const applyingScopedQueryFromUrlRef = useRef(false);
  const debouncedPathQuery = useDebouncedValue(d.pathQuery, 250);
  const debouncedMinLatencyMs = useDebouncedValue(d.minLatencyMs, 250);
  const debouncedMaxLatencyMs = useDebouncedValue(d.maxLatencyMs, 250);
  const debouncedEnvironmentQuery = useDebouncedValue(d.serverEnvironmentQuery, 250);
  const debouncedServiceQuery = useDebouncedValue(d.serverServiceQuery, 250);
  const searchKey = searchParams.toString();

  const scopedApplyTarget = {
    setAbsoluteWindow: d.setAbsoluteWindow,
    clearAbsoluteWindow: d.clearAbsoluteWindow,
    onServerWindowChange: d.onServerWindowChange,
    onServerMethodChange: d.onServerMethodChange,
    onServerStatusClassChange: d.onServerStatusClassChange,
    setPathQuery: d.setPathQuery,
    setMinLatencyMs: d.setMinLatencyMs,
    setMaxLatencyMs: d.setMaxLatencyMs,
    setServerEnvironmentQuery: d.setServerEnvironmentQuery,
    setServerServiceQuery: d.setServerServiceQuery,
    setRequestLimit: d.setRequestLimit,
    setRequestPage: d.setRequestPage,
    setErrorGroupLimit: d.setErrorGroupLimit,
    setErrorGroupPage: d.setErrorGroupPage,
    setErrorGroupSort: d.setErrorGroupSort,
    setSqlFilterApplied: d.setSqlFilterApplied,
    setSqlFilterDraft: d.setSqlFilterDraft,
    setSqlFilterEnabled: d.setSqlFilterEnabled,
  } as const;

  const scopedServerStateForUrl = useMemo(
    (): DashboardScopedQueryState =>
      buildCurrentScopedState({
        isAbsoluteWindow: d.isAbsoluteWindow,
        windowMinutes: d.windowMinutes,
        windowFromTimestamp: d.windowFromTimestamp,
        windowToTimestamp: d.windowToTimestamp,
        method: d.method,
        statusClass: d.statusClass,
        minLatencyMs: d.minLatencyMs,
        maxLatencyMs: d.maxLatencyMs,
        pathQuery: d.pathQuery,
        serverEnvironmentQuery: d.serverEnvironmentQuery,
        serverServiceQuery: d.serverServiceQuery,
        requestLimit: d.requestLimit,
        requestPage: d.requestPage,
        errorGroupLimit: d.errorGroupLimit,
        errorGroupPage: d.errorGroupPage,
        errorGroupSort: d.errorGroupSort,
        sqlFilterApplied: d.sqlFilterApplied,
        sqlFilterEnabled: d.sqlFilterEnabled,
      }),
    [
      d.errorGroupLimit,
      d.errorGroupPage,
      d.errorGroupSort,
      d.isAbsoluteWindow,
      d.maxLatencyMs,
      d.minLatencyMs,
      d.pathQuery,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.method,
      d.requestLimit,
      d.requestPage,
      d.statusClass,
      d.sqlFilterApplied,
      d.sqlFilterEnabled,
      d.windowMinutes,
      d.windowFromTimestamp,
      d.windowToTimestamp,
    ],
  );

  const logsClientForUrl = useMemo(
    (): PersistedLogsClientSlice => ({
      groupBy: d.groupBy,
      sortKey: d.sortKey,
      sortDir: d.sortDir,
      envTags: [...d.envTags].sort(),
      serviceTags: [...d.serviceTags].sort(),
    }),
    [d.groupBy, d.sortKey, d.sortDir, d.envTags, d.serviceTags],
  );

  const diagnosisNavQueryComputed = useMemo(
    () => buildScopedQuery(scopedServerStateForUrl).toString(),
    [scopedServerStateForUrl],
  );

  const logsNavQueryComputed = useMemo(
    () =>
      buildLiveDashboardSearchString("/logs", scopedServerStateForUrl, logsClientForUrl),
    [scopedServerStateForUrl, logsClientForUrl],
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (previousPathRef.current === pathname) {
      return;
    }

    const captureCurrentState = (): ScopedServerState => ({
      isAbsoluteWindow: d.isAbsoluteWindow,
      windowMinutes: d.windowMinutes,
      windowFromTimestamp: d.windowFromTimestamp,
      windowToTimestamp: d.windowToTimestamp,
      method: d.method,
      statusClass: d.statusClass,
      minLatencyMs: debouncedMinLatencyMs,
      maxLatencyMs: debouncedMaxLatencyMs,
      pathQuery: debouncedPathQuery,
      serverEnvironmentQuery: debouncedEnvironmentQuery,
      serverServiceQuery: debouncedServiceQuery,
      requestLimit: d.requestLimit,
      requestPage: d.requestPage,
      errorGroupLimit: d.errorGroupLimit,
      errorGroupPage: d.errorGroupPage,
      errorGroupSort: d.errorGroupSort,
      sqlFilterDraft: d.sqlFilterDraft,
      sqlFilterApplied: d.sqlFilterApplied,
      sqlFilterEnabled: d.sqlFilterEnabled,
    });

    const applyState = (state: ScopedServerState) => {
      applyDashboardScopedQueryState(scopedApplyTarget, scopedServerStateToParsed(state));
      d.setSqlFilterDraft(state.sqlFilterDraft);
    };

    const previousPath = previousPathRef.current;
    if (isScopedPathRestoreRoute(previousPath)) {
      scopedStateRef.current[previousPath] = captureCurrentState();
    }
    if (isScopedPathRestoreRoute(pathname)) {
      // `useLayoutEffect` below applies `searchParams` to context before this `useEffect` runs.
      // Without this guard, `buildDefaultScopedState` resets method/status/path/env/etc. after
      // every link from `/dashboard` (or any non-scoped route) even when the href carried scope.
      if (!searchKey) {
        const fromRef = scopedStateRef.current[pathname];
        if (fromRef) {
          applyState(fromRef);
        } else {
          const persisted = readPersistedDashboardSession();
          const scoped =
            pathname === "/diagnosis"
              ? persisted?.diagnosisScoped
              : pathname === "/logs" || pathname === "/requests"
                ? persisted?.logsScoped
                : null;
          if (persisted && scoped) {
            applyDashboardScopedQueryState(scopedApplyTarget, scoped);
          } else {
            applyState(buildDefaultScopedState(d));
          }
        }
      }
    }

    previousPathRef.current = pathname;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intent: run only on pathname change; reads latest context inside.
  }, [pathname]);

  useLayoutEffect(() => {
    if (!isScopedUrlSyncRoute(pathname)) {
      return;
    }
    if (!searchKey) {
      return;
    }
    const search = searchKey;
    const prev = lastAppliedQueryRef.current;
    if (prev) {
      const qm = prev.indexOf("?");
      const prevPath = qm >= 0 ? prev.slice(0, qm) : prev;
      const prevSearch = qm >= 0 ? prev.slice(qm + 1) : "";
      if (prevPath === pathname && scopedQueryStringsEqual(prevSearch, search)) {
        return;
      }
    }

    applyingScopedQueryFromUrlRef.current = true;
    const sp = new URLSearchParams(search);
    const parsed = parseScopedQuery(sp);
    applyDashboardScopedQueryState(scopedApplyTarget, parsed);

    const logsParsed =
      pathname === "/logs" ? parseLogsClientSearchParams(sp) : DEFAULT_LOGS_VIEW_CLIENT;
    if (pathname === "/logs") {
      d.hydrateLogsViewFromUrl(logsParsed);
    }

    const normalized = buildLiveDashboardSearchString(pathname, parsed, logsParsed);
    if (!scopedQueryStringsEqual(normalized, search)) {
      const hash = typeof window !== "undefined" ? window.location.hash : "";
      const nextHref = normalized ? `${pathname}?${normalized}${hash}` : `${pathname}${hash}`;
      const scrollTop = typeof window !== "undefined" ? window.scrollY : 0;
      router.replace(nextHref, { scroll: false });
      scheduleDashboardViewportScrollRestore(scrollTop);
    }
    lastAppliedQueryRef.current = `${pathname}?${normalized}`;
    queueMicrotask(() => {
      applyingScopedQueryFromUrlRef.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync URL to context; d setters are stable
  }, [pathname, searchKey, router]);

  useEffect(() => {
    if (!isScopedUrlSyncRoute(pathname)) {
      return;
    }
    if (applyingScopedQueryFromUrlRef.current) {
      return;
    }
    const currentQuery = searchKey;
    const logsClientSlice: PersistedLogsClientSlice =
      pathname === "/logs"
        ? {
            groupBy: d.groupBy,
            sortKey: d.sortKey,
            sortDir: d.sortDir,
            envTags: [...d.envTags].sort(),
            serviceTags: [...d.serviceTags].sort(),
          }
        : DEFAULT_LOGS_VIEW_CLIENT;
    const nextQuery = buildLiveDashboardSearchString(pathname, scopedServerStateForUrl, logsClientSlice);
    if (scopedQueryStringsEqual(nextQuery, currentQuery)) {
      return;
    }
    const hash = typeof window !== "undefined" ? window.location.hash : "";
    const nextHref = nextQuery ? `${pathname}?${nextQuery}${hash}` : `${pathname}${hash}`;
    const scrollTop = typeof window !== "undefined" ? window.scrollY : 0;
    router.replace(nextHref, { scroll: false });
    scheduleDashboardViewportScrollRestore(scrollTop);
  }, [
    scopedServerStateForUrl,
    d.groupBy,
    d.sortKey,
    d.sortDir,
    d.envTags,
    d.serviceTags,
    pathname,
    router,
    searchKey,
  ]);

  const hasIssuedApiKey = useMemo(
    () =>
      Boolean(
        d.onboardingStatus?.ingest_key_ready ??
          (d.apiKeys.length > 0 || Boolean(d.lastIssuedApiKey)),
      ),
    [d.apiKeys.length, d.lastIssuedApiKey, d.onboardingStatus?.ingest_key_ready],
  );

  const hasFirstEvent = useMemo(
    () =>
      Boolean(
        d.onboardingStatus?.first_event_received ??
          ((d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0),
      ),
    [
      d.onboardingStatus?.first_event_received,
      d.overview?.request_count,
      d.requests?.total,
    ],
  );

  const onboardingStatusKnown = d.onboardingStatus !== null;
  const onboardingCompleted = Boolean(d.onboardingStatus?.onboarding_completed);

  useEffect(() => {
    if (!d.authSessionResolved || !d.hasDashboardSession) {
      return;
    }
    if (!onboardingStatusKnown) {
      return;
    }
    if (onboardingCompleted) {
      return;
    }
    if (pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [
    d.authSessionResolved,
    d.hasDashboardSession,
    onboardingCompleted,
    onboardingStatusKnown,
    pathname,
    router,
  ]);

  useEffect(() => {
    if (!d.authSessionResolved || !d.hasDashboardSession) {
      return;
    }
    if (!onboardingStatusKnown) {
      return;
    }
    if (!onboardingCompleted) {
      return;
    }
    if (pathname === "/onboarding") {
      router.replace("/dashboard");
    }
  }, [
    d.authSessionResolved,
    d.hasDashboardSession,
    onboardingCompleted,
    onboardingStatusKnown,
    pathname,
    router,
  ]);

  if (!d.authSessionResolved) {
    return <DashboardSessionRestoring />;
  }
  if (!d.hasDashboardSession) {
    return <ApiKeyMissing />;
  }

  if (!onboardingStatusKnown) {
    return (
      <DashboardSessionRestoring
        title="Loading workspace…"
        message="Checking onboarding status before opening the dashboard."
      />
    );
  }

  const isDark =
    d.themePreference === "dark" || (d.themePreference === "system" && systemPrefersDark);
  const meta = PAGE_META[pathname] ?? PAGE_META["/dashboard"];
  const showServerScope =
    pathname === "/diagnosis" || pathname === "/logs" || pathname === "/requests";
  const latestDispatch = d.recentAlertDispatches[0] ?? null;
  const alertDeliveryHealthy = latestDispatch ? latestDispatch.status !== "failed" : true;
  const subpathStaticUi = isApiSubpathDashboard();
  /** Hide the onboarding/status strip once workspace + onboarding are OK and every tile is on the success path. */
  const statusStripAllHealthy =
    d.hasDashboardSession &&
    hasIssuedApiKey &&
    hasFirstEvent &&
    alertDeliveryHealthy &&
    onboardingCompleted &&
    d.workspaceBootstrapError === null;
  const statusStrip = !statusStripAllHealthy ? (
    <div className="grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1.5 dark:border-neutral-700 dark:bg-neutral-800/70">
        <p className="font-medium text-slate-700 dark:text-neutral-200">Session access</p>
        <p className={d.hasDashboardSession ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}>
          {d.hasDashboardSession ? "Active session" : "Not signed in"}
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1.5 dark:border-neutral-700 dark:bg-neutral-800/70">
        <p className="font-medium text-slate-700 dark:text-neutral-200">
          {subpathStaticUi ? "Ingest key" : "Project ingest key"}
        </p>
        <p className={hasIssuedApiKey ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}>
          {hasIssuedApiKey
            ? subpathStaticUi
              ? "DB has a key"
              : "Ready"
            : subpathStaticUi
              ? "Issue or .env.autopulse"
              : "Issue in onboarding"}
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1.5 dark:border-neutral-700 dark:bg-neutral-800/70">
        <p className="font-medium text-slate-700 dark:text-neutral-200">
          {subpathStaticUi ? "Events" : "First event"}
        </p>
        <p className={hasFirstEvent ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}>
          {hasFirstEvent
            ? subpathStaticUi
              ? "Seen (startup ping counts)"
              : "Active"
            : subpathStaticUi
              ? "Restart / refresh"
              : "Waiting"}
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1.5 dark:border-neutral-700 dark:bg-neutral-800/70">
        <p className="font-medium text-slate-700 dark:text-neutral-200">Alert delivery</p>
        <p className={alertDeliveryHealthy ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}>
          {latestDispatch ? (alertDeliveryHealthy ? "Latest dispatch healthy" : "Latest dispatch failed") : "No dispatches yet"}
        </p>
      </div>
    </div>
  ) : null;
  const resetDiagnosisScope = () =>
    resetServerScope(
      {
        onServerMethodChange: d.onServerMethodChange,
        onServerStatusClassChange: d.onServerStatusClassChange,
        setPathQuery: d.setPathQuery,
        setMinLatencyMs: d.setMinLatencyMs,
        setMaxLatencyMs: d.setMaxLatencyMs,
        setServerEnvironmentQuery: d.setServerEnvironmentQuery,
        setServerServiceQuery: d.setServerServiceQuery,
        setRequestLimit: d.setRequestLimit,
        setRequestPage: d.setRequestPage,
        setErrorGroupLimit: d.setErrorGroupLimit,
        setErrorGroupPage: d.setErrorGroupPage,
        setErrorGroupSort: d.setErrorGroupSort,
        setSqlFilterDraft: d.setSqlFilterDraft,
        setSqlFilterApplied: d.setSqlFilterApplied,
        setSqlFilterEnabled: d.setSqlFilterEnabled,
      },
      "diagnosis",
    );
  const resetRequestLikeScope = (variant: "logs" | "requests") =>
    resetServerScope(
      {
        onServerMethodChange: d.onServerMethodChange,
        onServerStatusClassChange: d.onServerStatusClassChange,
        setPathQuery: d.setPathQuery,
        setMinLatencyMs: d.setMinLatencyMs,
        setMaxLatencyMs: d.setMaxLatencyMs,
        setServerEnvironmentQuery: d.setServerEnvironmentQuery,
        setServerServiceQuery: d.setServerServiceQuery,
        setRequestLimit: d.setRequestLimit,
        setRequestPage: d.setRequestPage,
        setErrorGroupLimit: d.setErrorGroupLimit,
        setErrorGroupPage: d.setErrorGroupPage,
        setErrorGroupSort: d.setErrorGroupSort,
        setSqlFilterDraft: d.setSqlFilterDraft,
        setSqlFilterApplied: d.setSqlFilterApplied,
        setSqlFilterEnabled: d.setSqlFilterEnabled,
      },
      variant,
    );

  const workspaceBootstrapBanner =
    d.workspaceBootstrapError !== null ? (
      <div
        role="alert"
        className="flex flex-col gap-2 rounded-lg border border-amber-500/45 bg-amber-50 px-3 py-2.5 text-sm text-amber-950 shadow-sm dark:border-amber-500/35 dark:bg-amber-950/45 dark:text-amber-50 sm:flex-row sm:items-center sm:justify-between"
      >
        <p className="min-w-0 flex-1 leading-snug">{d.workspaceBootstrapError}</p>
        <button
          type="button"
          className="ap-btn shrink-0 self-start text-xs sm:self-auto"
          onClick={() => d.retryWorkspaceBootstrap()}
        >
          Retry workspace load
        </button>
      </div>
    ) : null;

  return (
    <DashboardAppShell
      pathname={pathname}
      title={meta.title}
      subtitle={meta.subtitle}
      statusStrip={statusStrip ?? undefined}
      topBanner={workspaceBootstrapBanner}
      isDark={isDark}
      diagnosisNavQuery={diagnosisNavQueryComputed}
      logsNavQuery={logsNavQueryComputed}
      filterToolbarAutoCollapse={showServerScope}
      filterToolbarCompactLabel={
        pathname === "/diagnosis"
          ? "Diagnosis scope"
          : pathname === "/logs" || pathname === "/requests"
            ? "Requests scope"
            : "Server scope"
      }
      onResetServerFilters={
        showServerScope
          ? pathname === "/diagnosis"
            ? resetDiagnosisScope
            : pathname === "/requests"
              ? () => resetRequestLikeScope("requests")
              : () => resetRequestLikeScope("logs")
          : undefined
      }
      filterToolbar={
        showServerScope ? (
          <ServerQueryToolbar
            variant={
              pathname === "/diagnosis"
                ? "diagnosis"
                : pathname === "/requests"
                  ? "requests"
                  : "logs"
            }
          />
        ) : null
      }
    >
      {children}
    </DashboardAppShell>
  );
}

export function DashboardLayoutClient({ children }: { children: ReactNode }) {
  return (
    <DashboardDataProvider>
      <ShellWithData>{children}</ShellWithData>
    </DashboardDataProvider>
  );
}
