"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardAppShell } from "./AppShell";
import { ApiKeyMissing } from "./DashboardPageBoundary";
import { DashboardDataProvider, useDashboardData } from "./DashboardDataContext";
import { ServerQueryToolbar } from "./ServerQueryToolbar";

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
  errorGroupLimit: number;
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
    errorGroupLimit: 25,
    errorGroupSort: "last_seen",
  };
}

function ShellWithData({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const d = useDashboardData();
  const [isDark, setIsDark] = useState(false);
  const lastAppliedQueryRef = useRef<string>("");
  const scopedStateRef = useRef<Record<string, ScopedServerState>>({});
  const previousPathRef = useRef(pathname);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = window.localStorage.getItem("autopulse-theme");
      if (stored === "dark") {
        setIsDark(true);
        return;
      }
      if (stored === "light") {
        setIsDark(false);
        return;
      }
      setIsDark(window.matchMedia("(prefers-color-scheme: dark)").matches);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("autopulse-theme", isDark ? "dark" : "light");
  }, [isDark]);

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
      minLatencyMs: d.minLatencyMs,
      maxLatencyMs: d.maxLatencyMs,
      pathQuery: d.pathQuery,
      serverEnvironmentQuery: d.serverEnvironmentQuery,
      serverServiceQuery: d.serverServiceQuery,
      requestLimit: d.requestLimit,
      errorGroupLimit: d.errorGroupLimit,
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
      d.setErrorGroupLimit(state.errorGroupLimit);
      d.setErrorGroupSort(state.errorGroupSort);
      d.setRequestPage(0);
      d.setErrorGroupPage(0);
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
    if (pathname !== "/diagnosis") {
      return;
    }
    const search = searchParams.toString();
    if (!search) {
      return;
    }
    const queryKey = `${pathname}?${search}`;
    if (lastAppliedQueryRef.current === queryKey) {
      return;
    }

    const from = searchParams.get("from_timestamp") ?? searchParams.get("bucket_start");
    const to = searchParams.get("to_timestamp") ?? searchParams.get("bucket_end");
    if (from && to) {
      d.setAbsoluteWindow(from, to);
    }
    const method = searchParams.get("method");
    if (method) {
      d.onServerMethodChange(method);
    }
    const statusClass = searchParams.get("status_class");
    if (statusClass) {
      d.onServerStatusClassChange(statusClass);
    }
    const pathContains = searchParams.get("path_contains");
    if (pathContains !== null) {
      d.setPathQuery(pathContains);
      d.setRequestPage(0);
    }
    const minLatency = searchParams.get("min_latency_ms");
    if (minLatency !== null) {
      d.setMinLatencyMs(minLatency);
      d.setRequestPage(0);
    }
    const maxLatency = searchParams.get("max_latency_ms");
    if (maxLatency !== null) {
      d.setMaxLatencyMs(maxLatency);
      d.setRequestPage(0);
    }
    const environments = searchParams.get("environments");
    if (environments !== null) {
      d.setServerEnvironmentQuery(environments);
      d.setRequestPage(0);
    }
    const services = searchParams.get("services");
    if (services !== null) {
      d.setServerServiceQuery(services);
      d.setRequestPage(0);
    }
    const errorGroupSort = searchParams.get("error_group_sort");
    if (errorGroupSort === "count" || errorGroupSort === "last_seen") {
      d.setErrorGroupSort(errorGroupSort);
    }

    lastAppliedQueryRef.current = queryKey;
  }, [d, pathname, searchParams]);

  if (!d.hasApiKey) {
    return <ApiKeyMissing />;
  }

  const meta = PAGE_META[pathname] ?? PAGE_META["/dashboard"];
  const showServerScope = pathname === "/dashboard" || pathname === "/diagnosis" || pathname === "/logs";
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
      onToggleTheme={() => setIsDark((prev) => !prev)}
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
