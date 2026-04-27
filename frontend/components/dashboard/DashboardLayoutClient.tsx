"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardAppShell } from "./AppShell";
import { ApiKeyMissing, DashboardSessionRestoring } from "./DashboardPageBoundary";
import { DashboardDataProvider, useDashboardData } from "./DashboardDataContext";
import { ServerQueryToolbar } from "./ServerQueryToolbar";
import {
  buildScopedQuery,
  parseScopedQuery,
  scopedQueryStringsEqual,
} from "./dashboardQueryState";
import { toDashboardRoutePath } from "./dashboardRoutePath";

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Dashboard",
    subtitle: "Traffic and headline rates in the selected window.",
  },
  "/diagnosis": {
    title: "Diagnosis",
    subtitle: "Error signals and grouped failures.",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Alert heuristics, settings, and runbook shortcuts.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Project defaults, theme, and delivery channels.",
  },
  "/logs": {
    title: "Logs",
    subtitle: "Scope traffic quickly and inspect request evidence.",
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
  sqlFilterDraft: string;
  sqlFilterApplied: string;
  sqlFilterEnabled: boolean;
};

function isScopedServerRoute(pathname: string): boolean {
  return pathname === "/diagnosis" || pathname === "/logs";
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
    sqlFilterDraft: "",
    sqlFilterApplied: "",
    sqlFilterEnabled: false,
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
  const [systemPrefersDark, setSystemPrefersDark] = useState(false);
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

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setSystemPrefersDark(window.matchMedia("(prefers-color-scheme: dark)").matches);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

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
      sqlFilterDraft: d.sqlFilterDraft,
      sqlFilterApplied: d.sqlFilterApplied,
      sqlFilterEnabled: d.sqlFilterEnabled,
    });

    const applyState = (state: ScopedServerState) => {
      if (state.isAbsoluteWindow) {
        d.setAbsoluteWindow(state.windowFromTimestamp, state.windowToTimestamp);
      } else {
        d.clearAbsoluteWindow();
        d.onServerWindowChange(state.windowMinutes);
      }
      d.onServerMethodChange(state.method);
      d.onServerStatusClassChange(state.statusClass);
      d.setMinLatencyMs(state.minLatencyMs);
      d.setMaxLatencyMs(state.maxLatencyMs);
      d.setPathQuery(state.pathQuery);
      d.setServerEnvironmentQuery(state.serverEnvironmentQuery);
      d.setServerServiceQuery(state.serverServiceQuery);
      d.setRequestLimit(state.requestLimit);
      d.setRequestPage(state.requestPage);
      d.setErrorGroupLimit(state.errorGroupLimit);
      d.setErrorGroupPage(state.errorGroupPage);
      d.setSqlFilterDraft(state.sqlFilterDraft);
      d.setSqlFilterApplied(state.sqlFilterApplied);
      d.setSqlFilterEnabled(state.sqlFilterEnabled);
    };

    const previousPath = previousPathRef.current;
    if (isScopedServerRoute(previousPath)) {
      scopedStateRef.current[previousPath] = captureCurrentState();
    }
    if (isScopedServerRoute(pathname)) {
      const nextState =
        scopedStateRef.current[pathname] ?? buildDefaultScopedState(d);
      applyState(nextState);
    }

    previousPathRef.current = pathname;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intent: run only on pathname change; reads latest context inside.
  }, [pathname]);

  useLayoutEffect(() => {
    if (!isScopedServerRoute(pathname)) {
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
    if (parsed.isAbsoluteWindow) {
      d.setAbsoluteWindow(parsed.windowFromTimestamp, parsed.windowToTimestamp);
    } else {
      d.clearAbsoluteWindow();
      d.onServerWindowChange(parsed.windowMinutes);
    }
    d.onServerMethodChange(parsed.method);
    d.onServerStatusClassChange(parsed.statusClass);
    d.setPathQuery(parsed.pathQuery);
    d.setMinLatencyMs(parsed.minLatencyMs);
    d.setMaxLatencyMs(parsed.maxLatencyMs);
    d.setServerEnvironmentQuery(parsed.serverEnvironmentQuery);
    d.setServerServiceQuery(parsed.serverServiceQuery);
    d.setRequestLimit(parsed.requestLimit);
    d.setRequestPage(parsed.requestPage);
    d.setErrorGroupLimit(parsed.errorGroupLimit);
    d.setErrorGroupPage(parsed.errorGroupPage);
    d.setErrorGroupSort(parsed.errorGroupSort);
    if (sp.has("sql_filter")) {
      const f = (parsed.sqlFilterApplied ?? "").trim();
      d.setSqlFilterApplied(f);
      d.setSqlFilterDraft(f);
      d.setSqlFilterEnabled(Boolean(parsed.sqlFilterEnabled && f.length > 0));
    } else {
      d.setSqlFilterApplied("");
      d.setSqlFilterDraft("");
      d.setSqlFilterEnabled(false);
    }

    const normalized = buildScopedQuery(parsed).toString();
    if (!scopedQueryStringsEqual(normalized, search)) {
      const hash = typeof window !== "undefined" ? window.location.hash : "";
      const nextHref = normalized ? `${pathname}?${normalized}${hash}` : `${pathname}${hash}`;
      router.replace(nextHref, { scroll: false });
    }
    lastAppliedQueryRef.current = `${pathname}?${normalized}`;
    queueMicrotask(() => {
      applyingScopedQueryFromUrlRef.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync URL to context; d setters are stable
  }, [pathname, searchKey, router]);

  useEffect(() => {
    if (!isScopedServerRoute(pathname)) {
      return;
    }
    if (applyingScopedQueryFromUrlRef.current) {
      return;
    }
    const currentQuery = searchKey;
    const nextQuery = buildScopedQuery({
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
    }).toString();
    if (scopedQueryStringsEqual(nextQuery, currentQuery)) {
      return;
    }
    const hash = typeof window !== "undefined" ? window.location.hash : "";
    const nextHref = nextQuery ? `${pathname}?${nextQuery}${hash}` : `${pathname}${hash}`;
    router.replace(nextHref, { scroll: false });
  }, [
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
    d.windowMinutes,
    d.windowFromTimestamp,
    d.windowToTimestamp,
    pathname,
    router,
    searchKey,
    d.sqlFilterApplied,
    d.sqlFilterEnabled,
  ]);

  if (!d.authSessionResolved) {
    return <DashboardSessionRestoring />;
  }
  if (!d.hasApiKey) {
    return <ApiKeyMissing />;
  }

  const isDark =
    d.themePreference === "dark" || (d.themePreference === "system" && systemPrefersDark);
  const meta = PAGE_META[pathname] ?? PAGE_META["/dashboard"];
  const showServerScope = pathname === "/diagnosis" || pathname === "/logs";
  const scopedQueryString = buildScopedQuery({
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
  }).toString();
  const resetServerFilters = () => {
    d.onServerMethodChange("ALL");
    d.onServerStatusClassChange("ALL");
    d.setPathQuery("");
    d.setMinLatencyMs("");
    d.setMaxLatencyMs("");
    d.setServerEnvironmentQuery("");
    d.setServerServiceQuery("");
    d.setRequestPage(0);
    d.setErrorGroupPage(0);
    d.setSqlFilterDraft("");
    d.setSqlFilterApplied("");
    d.setSqlFilterEnabled(false);
  };

  return (
    <DashboardAppShell
      pathname={pathname}
      title={meta.title}
      subtitle={meta.subtitle}
      isDark={isDark}
      scopedQueryString={scopedQueryString}
      filterToolbarAutoCollapse={showServerScope}
      filterToolbarCompactLabel="Server scope"
      onResetServerFilters={showServerScope ? resetServerFilters : undefined}
      filterToolbar={showServerScope ? <ServerQueryToolbar /> : null}
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
