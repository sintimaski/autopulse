"use client";

import Link from "next/link";

import { useDashboardData } from "./DashboardDataContext";
import { buildCurrentScopedState, buildScopedQuery } from "./dashboardQueryState";
import { buildGuidedTroubleshootingHints } from "../../utils/guidedTroubleshooting";

type GuidanceItem = {
  id: string;
  title: string;
  reason: string;
  next_step: string;
  href: string;
};

export function GuidedTroubleshootingPanel() {
  const d = useDashboardData();
  const query = buildScopedQuery(
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
      requestPage: 0,
      errorGroupLimit: d.errorGroupLimit,
      errorGroupPage: 0,
      errorGroupSort: d.errorGroupSort,
      sqlFilterApplied: d.sqlFilterApplied,
      sqlFilterEnabled: d.sqlFilterEnabled,
    }),
  ).toString();

  const failedDispatch = d.recentAlertDispatches.find((dispatch) => dispatch.status === "failed");
  const hintIds = buildGuidedTroubleshootingHints({
    errorSpikeCandidate: d.operationalSignals.errorSpikeCandidate,
    outageCandidate: d.operationalSignals.outageCandidate,
    topFailingRouteCount: d.topFailingRoutes.length ? d.topFailingRoutes[0][1] : 0,
    hasFailedDispatch: Boolean(failedDispatch),
    failedDispatchReason: failedDispatch?.reason_code ?? null,
    archivalStatus: d.retentionSettings?.archival_status ?? null,
    archivalError: d.retentionSettings?.archival_last_error ?? null,
  });
  const hints: GuidanceItem[] = [];
  for (const hint of hintIds) {
    if (hint.id === "error-spike") {
      hints.push({
        id: "error-spike",
        title: "Error spike candidate",
        reason: "Current error rate and volume cross the configured spike threshold.",
        next_step: "Inspect grouped errors sorted by count and confirm shared route/exception context.",
        href: `/diagnosis?${query}#grouped-errors`,
      });
      continue;
    }
    if (hint.id === "outage") {
      hints.push({
        id: "outage",
        title: "Possible outage candidate",
        reason: "No successful requests detected in the current evaluation window.",
        next_step: "Open failing routes and verify infrastructure/downstream dependency status.",
        href: `/diagnosis?${query}`,
      });
      continue;
    }
    if (hint.id === "high-5xx-route") {
      hints.push({
        id: "high-5xx-route",
        title: "High 5xx route concentration",
        reason: `Top failing route currently reports ${d.topFailingRoutes[0][1]} server errors.`,
        next_step: "Open logs scoped to that route and compare request-id level traces.",
        href: `/requests?${query}`,
      });
      continue;
    }
    if (hint.id === "alert-delivery") {
      hints.push({
        id: "alert-delivery",
        title: "Alert delivery failure",
        reason: `Latest dispatch failed with reason "${failedDispatch?.reason_code ?? "unknown"}".`,
        next_step: "Review alert destination settings and provider credentials in Settings.",
        href: "/settings",
      });
      continue;
    }
    if (hint.id === "retention-backlog") {
      hints.push({
        id: "retention-backlog",
        title: "Retention archival needs attention",
        reason: `Archival status is failed${d.retentionSettings?.archival_last_error ? ` (${d.retentionSettings.archival_last_error})` : ""}.`,
        next_step: "Check retention settings and run retention runbook command once after fixing config.",
        href: "/settings",
      });
      continue;
    }
    hints.push({
      id: "healthy",
      title: "No urgent incident pattern detected",
      reason: "Current diagnostics are within normal thresholds for this window.",
      next_step: "Keep monitoring and validate alert policy coverage for new services.",
      href: "/alerts",
    });
  }

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Guided troubleshooting</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
        Symptom-driven next steps based on current dashboard signals.
      </p>
      <ul className="mt-3 space-y-2">
        {hints.map((hint) => (
          <li key={hint.id} className="rounded-xl border border-slate-200/90 bg-slate-50/80 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/60">
            <p className="text-sm font-semibold text-slate-900 dark:text-neutral-100">{hint.title}</p>
            <p className="mt-1 text-xs text-slate-600 dark:text-neutral-300">{hint.reason}</p>
            <p className="mt-1 text-xs text-slate-700 dark:text-neutral-200">{hint.next_step}</p>
            <Link href={hint.href} className="mt-1 inline-block text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300">
              Open
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
