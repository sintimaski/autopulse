"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardAppShell } from "./AppShell";
import { ApiKeyMissing } from "./DashboardPageBoundary";
import { DashboardDataProvider, useDashboardData } from "./DashboardDataContext";
import { ServerQueryToolbar } from "./ServerQueryToolbar";
import { buildScopedQuery, parseScopedQuery } from "./dashboardQueryState";

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Dashboard",
    subtitle: "Volume and headline rates for the selected window.",
  },
  "/diagnosis": {
    title: "Diagnosis",
    subtitle: "Error signals and grouped stack signatures.",
  },
  "/alerts": {
    title: "Alerts",
    subtitle: "Heuristic preview and backend job runbook.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Project defaults and delivery channel configuration.",
  },
  "/logs": {
    title: "Logs",
    subtitle: "Scope traffic fast, then inspect request-level evidence.",
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
    errorGroupSort: "last_seen",
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
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const d = useDashboardData();
  const [systemPrefersDark, setSystemPrefersDark] = useState(false);
  const lastAppliedQueryRef = useRef<string>("");
  const scopedStateRef = useRef<Record<string, ScopedServerState>>({});
  const previousPathRef = useRef(pathname);
  const debouncedPathQuery = useDebouncedValue(d.pathQuery, 250);
  const debouncedMinLatencyMs = useDebouncedValue(d.minLatencyMs, 250);
  const debouncedMaxLatencyMs = useDebouncedValue(d.maxLatencyMs, 250);
  const debouncedEnvironmentQuery = useDebouncedValue(d.serverEnvironmentQuery, 250);
  const debouncedServiceQuery = useDebouncedValue(d.serverServiceQuery, 250);

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
      errorGroupSort: d.errorGroupSort,
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
      d.setErrorGroupSort(state.errorGroupSort);
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
  }, [d, pathname]);

  useEffect(() => {
    if (!isScopedServerRoute(pathname)) {
      return;
    }
    const search = searchParams.toString();
    const queryKey = `${pathname}?${search}`;
    if (lastAppliedQueryRef.current === queryKey) {
      return;
    }

    const parsed = parseScopedQuery(new URLSearchParams(search));
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

    lastAppliedQueryRef.current = queryKey;
  }, [d, pathname, searchParams]);

  useEffect(() => {
    if (!isScopedServerRoute(pathname)) {
      return;
    }
    const currentQuery = searchParams.toString();
    const nextQuery = buildScopedQuery({
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
    }).toString();
    if (nextQuery === currentQuery) {
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
    debouncedEnvironmentQuery,
    debouncedMaxLatencyMs,
    debouncedMinLatencyMs,
    debouncedPathQuery,
    debouncedServiceQuery,
    d.method,
    d.requestLimit,
    d.requestPage,
    d.statusClass,
    d.windowFromTimestamp,
    d.windowMinutes,
    d.windowToTimestamp,
    pathname,
    router,
    searchParams,
  ]);

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
  };

  return (
    <DashboardAppShell
      pathname={pathname}
      title={meta.title}
      subtitle={meta.subtitle}
      isDark={isDark}
      scopedQueryString={scopedQueryString}
      onRefresh={() => d.setRefreshToken((n) => n + 1)}
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
