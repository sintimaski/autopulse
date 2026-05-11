"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { useDashboardData } from "./DashboardDataContext";
import {
  buildCurrentScopedState,
  buildDashboardPageHref,
  buildDiagnosisPageHref,
  buildRequestsPageHref,
} from "./dashboardQueryState";
import { toDashboardRoutePath } from "./dashboardRoutePath";

export function DiagnosisScopePivotBar() {
  const d = useDashboardData();
  const pathname = usePathname();
  const route = useMemo(() => toDashboardRoutePath(pathname), [pathname]);
  const scoped = useMemo(
    () =>
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
        correlationRequestId: d.correlationRequestId,
        sqlFilterApplied: d.sqlFilterApplied,
        sqlFilterEnabled: d.sqlFilterEnabled,
      }),
    [
      d.correlationRequestId,
      d.errorGroupLimit,
      d.errorGroupPage,
      d.errorGroupSort,
      d.isAbsoluteWindow,
      d.maxLatencyMs,
      d.method,
      d.minLatencyMs,
      d.pathQuery,
      d.requestLimit,
      d.requestPage,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.sqlFilterApplied,
      d.sqlFilterEnabled,
      d.statusClass,
      d.windowFromTimestamp,
      d.windowMinutes,
      d.windowToTimestamp,
    ],
  );
  const overviewHref = buildDashboardPageHref(scoped);
  const diagnosisHref = buildDiagnosisPageHref(scoped);
  const requestsHref = buildRequestsPageHref(scoped);
  const pill = (href: string, label: string, active: boolean) => (
    <Link
      href={href}
      className={`rounded-full px-3 py-1 text-xs font-medium ${
        active
          ? "bg-slate-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-neutral-400">
      <span className="font-medium text-slate-700 dark:text-neutral-300">Same scope</span>
      {pill(overviewHref, "Overview", route === "/dashboard")}
      {pill(diagnosisHref, "Diagnosis", route === "/diagnosis")}
      {pill(requestsHref, "Requests", route === "/requests")}
      {d.correlationRequestId.trim() ? (
        <button
          type="button"
          className="rounded-full border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
          onClick={() => d.setCorrelationRequestId("")}
        >
          Clear correlation filter
        </button>
      ) : null}
    </div>
  );
}
