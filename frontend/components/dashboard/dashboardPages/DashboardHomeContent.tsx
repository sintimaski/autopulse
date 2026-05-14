"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { MetricCard } from "../MetricCard";
import { DashboardScopeFacetShell } from "../DashboardScopeFacetShell";
import { CorrelationClearBar } from "../CorrelationClearBar";
import { OverviewScopeFacetBoard } from "../OverviewScopeFacetBoard";
import { SparklineMini } from "../SparklineMini";
import { VolumeChart } from "../VolumeChart";
import { useDashboardData } from "../DashboardDataContext";
import { useDashboardHomeSlice } from "../data/useDashboardSlices";
import { CardSpinner } from "../../ui/CardSpinner";
import { ChartScopeTintOverlay } from "../charts/ChartScopeTintOverlay";
import { DashboardInfrastructureSection } from "./DashboardInfrastructureSection";
import { OperatorPipelineHealthSection } from "../OperatorPipelineHealthSection";
import { RecentJobFailuresStrip } from "../RecentJobFailuresStrip";
import { resolveOverviewExtendedForHome } from "../../../utils/overviewExtendedInference";
import { buildCurrentScopedState, buildScopedQuery, type DashboardScopedQueryState } from "../dashboardQueryState";
import { DashboardDetailModal } from "../DashboardDetailModal";
import { ErrorGroupEvidenceBody } from "../ErrorGroupEvidenceBody";
import { SaveBookmarkModal } from "../SaveBookmarkModal";
import { toDashboardRoutePath } from "../dashboardRoutePath";
import { buildErrorGroupEvidenceMenuItems } from "../errorGroupEvidenceMenu";
import { RowActionsMenu } from "../RowActionsMenu";
import {
  formatTimestamp,
  type ErrorGroupItem,
} from "../dashboardTypes";

export function DashboardHomeContent() {
  const router = useRouter();
  const d = useDashboardData();
  const homeSlice = useDashboardHomeSlice();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routePath = useMemo(() => toDashboardRoutePath(pathname), [pathname]);
  const queryStringForBookmarks = searchParams.toString();
  const [errorModalItem, setErrorModalItem] = useState<ErrorGroupItem | null>(null);
  const [bookmarkDraft, setBookmarkDraft] = useState<{ title: string; hashFragment: string } | null>(null);
  const scopedState = useMemo(
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
        correlationRequestId: d.correlationRequestId,
        sqlFilterApplied: d.sqlFilterApplied,
        sqlFilterEnabled: d.sqlFilterEnabled,
      }),
    [
      d.isAbsoluteWindow,
      d.windowMinutes,
      d.windowFromTimestamp,
      d.windowToTimestamp,
      d.method,
      d.statusClass,
      d.minLatencyMs,
      d.maxLatencyMs,
      d.pathQuery,
      d.serverEnvironmentQuery,
      d.serverServiceQuery,
      d.requestLimit,
      d.requestPage,
      d.errorGroupLimit,
      d.errorGroupPage,
      d.errorGroupSort,
      d.correlationRequestId,
      d.sqlFilterApplied,
      d.sqlFilterEnabled,
    ],
  );
  const overview = homeSlice.overview;
  const requests = homeSlice.requests;
  if (!overview || !requests) {
    return (
      <section className="space-y-4">
        <DashboardScopeFacetShell className="sticky top-0 z-30">
          <OverviewScopeFacetBoard />
        </DashboardScopeFacetShell>
        <CorrelationClearBar />
        {d.loading && !d.errorMessage ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <CardSpinner size="compact" label="Overview metrics" />
              <CardSpinner size="compact" label="Traffic window" />
              <CardSpinner size="compact" label="Request sample" />
            </div>
            <CardSpinner size="section" label="Loading charts & widgets…" />
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200/90 bg-slate-50 p-4 text-sm text-slate-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300">
            {d.errorMessage ?? "No metrics for this scope yet. Adjust filters or send traffic."}
          </div>
        )}
      </section>
    );
  }
  const overviewExtended = resolveOverviewExtendedForHome(overview, requests, homeSlice.overviewExtended);
  const diagnosisParams = buildScopedQuery({
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
    correlationRequestId: d.correlationRequestId,
    sqlFilterApplied: d.sqlFilterApplied,
    sqlFilterEnabled: d.sqlFilterEnabled,
  });
  const diagnosisBaseHref = `/diagnosis?${diagnosisParams.toString()}`;
  const diagnosisGroupedHref = `/diagnosis?${(() => {
    const params = new URLSearchParams(diagnosisParams.toString());
    params.set("error_group_sort", "count");
    return params.toString();
  })()}#grouped-errors`;
  const homeErrorModals = (
    <>
      <DashboardDetailModal
        open={errorModalItem !== null}
        title={errorModalItem ? `${errorModalItem.exception_type ?? "Error"} · ${errorModalItem.path}` : ""}
        onClose={() => setErrorModalItem(null)}
      >
        {errorModalItem ? (
          <ErrorGroupEvidenceBody
            item={errorModalItem}
            scopedState={scopedState}
            headerActions={
              <RowActionsMenu
                items={buildErrorGroupEvidenceMenuItems({
                  item: errorModalItem,
                  onOpenInModal: () => undefined,
                  onSaveBookmark: () =>
                    setBookmarkDraft({
                      title: `${errorModalItem.exception_type ?? "Error"} · ${errorModalItem.path}`.slice(0, 200),
                      hashFragment: `error-group:${encodeURIComponent(errorModalItem.group_key)}`,
                    }),
                }).filter((i) => i.id !== "open-modal")}
              />
            }
          />
        ) : null}
      </DashboardDetailModal>
      <SaveBookmarkModal
        open={bookmarkDraft !== null}
        onClose={() => setBookmarkDraft(null)}
        defaultTitle={bookmarkDraft?.title ?? ""}
        pathname={routePath}
        queryString={queryStringForBookmarks}
        hashFragment={bookmarkDraft?.hashFragment ?? ""}
        shareToProjectEligible={
          d.sessionMembershipRole === "owner" || d.sessionMembershipRole === "admin"
        }
      />
    </>
  );
  // The phased-lite layout is now the only dashboard layout — the legacy chart-heavy
  // branch (previously behind NEXT_PUBLIC_LUMONOX_DASHBOARD_REWRITE_PHASED="0") was removed.
  {
    // Drill-down: headline metric cards jump into Diagnosis / Requests carrying the
    // current scope, so a worrying number on the overview is one click from its cause.
    const pushDiagnosisWithScope = (patch?: Record<string, string>, hash = "") => {
      const params = new URLSearchParams(diagnosisParams.toString());
      params.set("error_group_page", "0");
      if (patch) {
        for (const [key, value] of Object.entries(patch)) {
          params.set(key, value);
        }
      }
      router.push(`/diagnosis?${params.toString()}${hash}`);
    };
    const pushRequestsWithScope = (patch?: Record<string, string>) => {
      const params = new URLSearchParams(diagnosisParams.toString());
      params.set("request_page", "0");
      if (patch) {
        for (const [key, value] of Object.entries(patch)) {
          params.set(key, value);
        }
      }
      router.push(`/requests?${params.toString()}`);
    };
    const totalRequests = homeSlice.sparklineSeries.reduce(
      (sum, bucket) => sum + Number(bucket.request_count || 0),
      0,
    );
    const totalErrors = homeSlice.sparklineSeries.reduce(
      (sum, bucket) => sum + Number(bucket.error_count || 0),
      0,
    );
    const weightedLatency = homeSlice.sparklineSeries.reduce(
      (sum, bucket) => sum + Number(bucket.avg_latency_ms || 0) * Number(bucket.request_count || 0),
      0,
    );
    const requestCount = totalRequests || overview.request_count;
    const errorCount = totalRequests ? totalErrors : overview.error_count;
    const errorRate = requestCount > 0 ? errorCount / requestCount : 0;
    const avgLatency = requestCount > 0 ? weightedLatency / requestCount : overview.avg_latency_ms;
    const requestsPerMinute = requestCount / Math.max(homeSlice.windowMinutes, 1);
    const sparklineErrors = homeSlice.sparklineSeries.map((bucket) => Number(bucket.error_count || 0));
    const sparklineLatency = homeSlice.sparklineSeries.map((bucket) => Number(bucket.avg_latency_ms || 0));
    const routeBreakdownTop = [...overviewExtended.route_breakdown]
      .sort((a, b) => b.error_count - a.error_count)
      .slice(0, 6);
    const serviceBreakdownTop = [...overviewExtended.service_breakdown]
      .sort((a, b) => b.request_count - a.request_count)
      .slice(0, 6);
    const primaryCards = [
      {
        label: "Active incidents",
        value: String(overviewExtended.active_incident_count),
        helper: `Error bursts (5m): ${overviewExtended.error_burst_count}`,
        tone:
          overviewExtended.active_incident_count > 0 ? ("danger" as const) : ("neutral" as const),
        onClick: () => pushDiagnosisWithScope({ error_group_sort: "count" }, "#grouped-errors"),
      },
      {
        label: "Error rate",
        value: `${(errorRate * 100).toFixed(2)}%`,
        helper: "5xx + error events",
        tone: errorRate >= 0.1 ? ("danger" as const) : errorRate >= 0.03 ? ("warning" as const) : ("neutral" as const),
        onClick: () =>
          pushDiagnosisWithScope({ status_class: "5", error_group_sort: "count" }, "#grouped-errors"),
      },
      {
        label: "Latency p95",
        value: `${overviewExtended.p95_latency_ms.toFixed(1)} ms`,
        helper: `p50 ${overviewExtended.p50_latency_ms.toFixed(1)} · p99 ${overviewExtended.p99_latency_ms.toFixed(1)}`,
        tone:
          overviewExtended.p95_latency_ms >= 300
            ? ("danger" as const)
            : overviewExtended.p95_latency_ms >= 120
              ? ("warning" as const)
              : ("neutral" as const),
        onClick: () => pushRequestsWithScope(),
      },
      {
        label: "Requests / min",
        value: requestsPerMinute.toFixed(2),
        helper: `Total requests: ${requestCount}`,
        tone: "neutral" as const,
        onClick: () => pushRequestsWithScope(),
      },
    ];
    const secondaryCards = [
      { label: "Errors", value: String(errorCount), helper: "Scope total", tone: "warning" as const },
      { label: "Latency avg", value: `${avgLatency.toFixed(1)} ms`, helper: "Mean", tone: "neutral" as const },
      { label: "Latency p99", value: `${overviewExtended.p99_latency_ms.toFixed(1)} ms`, helper: "Tail", tone: "warning" as const },
      { label: "Apdex", value: overviewExtended.apdex_score.toFixed(3), helper: "<300ms target", tone: "neutral" as const },
      {
        label: "Active sessions",
        value: String(overviewExtended.active_sessions_estimate),
        helper: "Estimated",
        tone: "neutral" as const,
      },
    ];
    const chartAppliedWindowKey = `${overview.from_timestamp}|${overview.to_timestamp}`;
    return (
      <>
        <section className="space-y-6">
        <DashboardScopeFacetShell className="sticky top-0 z-30">
          <OverviewScopeFacetBoard />
        </DashboardScopeFacetShell>
        <CorrelationClearBar />
        {homeSlice.errorMessage ? (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200"
          >
            {homeSlice.errorMessage}
          </div>
        ) : null}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {primaryCards.map((card) => (
            <MetricCard
              key={card.label}
              label={card.label}
              value={card.value}
              helper={card.helper}
              tone={card.tone}
              onClick={card.onClick}
            />
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {secondaryCards.map((card) => (
            <MetricCard
              key={card.label}
              label={card.label}
              value={card.value}
              helper={card.helper}
              tone={card.tone}
            />
          ))}
        </div>
        <RecentJobFailuresStrip
          data={homeSlice.recentJobFailures}
          moreHref={diagnosisBaseHref}
          scopeForCorrelation={scopedState}
        />
        <OperatorPipelineHealthSection />
        <div className="w-full rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
          <h3 className="mb-2 text-sm font-semibold text-slate-800 dark:text-neutral-100">Traffic volume</h3>
          <p className="mb-2 text-xs text-slate-600 dark:text-neutral-400" aria-live="polite">
            Window summary: {requestCount.toLocaleString()} requests · {errorCount.toLocaleString()} errors (
            {(errorRate * 100).toFixed(2)}% rate) · avg latency {avgLatency.toFixed(1)} ms.
          </p>
          {overview.release_markers.length > 0 ? (
            <div className="mb-2 flex flex-wrap gap-1.5" aria-label="Releases seen in this window">
              {overview.release_markers.map((m) => (
                <span
                  key={`${m.at}\0${m.release}\0${m.git_sha ?? ""}`}
                  className="inline-flex max-w-full items-center gap-1 rounded-md border border-slate-200/90 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 dark:border-neutral-600 dark:bg-neutral-800/80 dark:text-neutral-200"
                  title={`${m.release}${m.git_sha ? ` · ${m.git_sha}` : ""} · ${m.at}`}
                >
                  <span className="max-w-[10rem] truncate font-medium">{m.release}</span>
                  {m.git_sha ? (
                    <span className="font-mono text-[10px] text-slate-500 dark:text-neutral-400">
                      {m.git_sha.slice(0, 7)}
                    </span>
                  ) : null}
                </span>
              ))}
            </div>
          ) : null}
          <VolumeChart
            series={homeSlice.sparklineSeries}
            fromTimestamp={homeSlice.windowFromTimestamp}
            toTimestamp={homeSlice.windowToTimestamp}
            globalWindowMinutes={homeSlice.windowMinutes}
            releaseMarkers={overview.release_markers}
            scopeAnchorKey={homeSlice.chartsScopeAnchorKey}
            chartsScopePending={homeSlice.chartsScopePending}
          />
        </div>
        <div className="space-y-6 text-slate-900 dark:text-neutral-100">
          <details className="group rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-slate-800 dark:text-neutral-100">
              <span
                aria-hidden="true"
                className="text-slate-400 transition-transform group-open:rotate-90 dark:text-neutral-500"
              >
                ▸
              </span>
              Advanced infrastructure insights
            </summary>
            <div className="mt-4">
              <DashboardInfrastructureSection
                sparklineSeries={homeSlice.sparklineSeries}
                overviewExtended={overviewExtended}
                dashboardWidgets={d.dashboardWidgets}
                globalWindowMinutes={homeSlice.windowMinutes}
                chartsScopePending={homeSlice.chartsScopePending}
                chartsScopeAnchorKey={homeSlice.chartsScopeAnchorKey}
              />
            </div>
          </details>
        </div>
        <div className="relative w-full rounded-xl border border-slate-200/90 bg-white px-3 py-2 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            Errors and latency trend
          </h3>
          <div className="relative mt-0.5 min-h-[2.5rem]">
            {homeSlice.chartsScopePending ? <ChartScopeTintOverlay className="rounded-lg" /> : null}
            <div className="relative z-0 grid grid-cols-2 gap-4">
              <div className="min-w-0">
                <div className="mb-0.5 text-[10px] text-slate-500 dark:text-neutral-500">Errors</div>
                <SparklineMini
                  key={`errs-${chartAppliedWindowKey}`}
                  interactive={false}
                  values={sparklineErrors}
                  svgClassName="h-6 w-full text-rose-500 dark:text-rose-400"
                />
              </div>
              <div className="min-w-0">
                <div className="mb-0.5 text-[10px] text-slate-500 dark:text-neutral-500">Latency</div>
                <SparklineMini
                  key={`lat-${chartAppliedWindowKey}`}
                  interactive={false}
                  values={sparklineLatency}
                  svgClassName="h-6 w-full text-orange-600 dark:text-orange-400"
                />
              </div>
            </div>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
            <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-neutral-100">Top failing routes</h3>
            <div className="space-y-2">
              {routeBreakdownTop.length ? (
                routeBreakdownTop.map((route) => (
                  <div key={route.key} className="flex items-center justify-between text-sm">
                    <span className="truncate pr-3 text-slate-700 dark:text-neutral-200">{route.key}</span>
                    <span className="text-rose-600 dark:text-rose-300">{route.error_count} errors</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 dark:text-neutral-400">
                  {homeSlice.chartsScopePending ? "Refreshing…" : "No failing routes in this window."}
                </p>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06]">
            <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-neutral-100">Top services by traffic</h3>
            <div className="space-y-2">
              {serviceBreakdownTop.length ? (
                serviceBreakdownTop.map((service) => (
                  <div key={service.key} className="flex items-center justify-between text-sm">
                    <span className="truncate pr-3 text-slate-700 dark:text-neutral-200">{service.key}</span>
                    <span className="text-orange-700 dark:text-orange-300">{service.request_count} req</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 dark:text-neutral-400">
                  {homeSlice.chartsScopePending ? "Refreshing…" : "No service traffic in this window."}
                </p>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:ring-white/[0.06] md:col-span-2 xl:col-span-1">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                Recent errors
              </h3>
              <Link
                href={diagnosisGroupedHref}
                className="shrink-0 text-[11px] font-medium text-orange-700 underline-offset-2 hover:underline dark:text-orange-300"
              >
                Open diagnosis
              </Link>
            </div>
            <p className="mb-2 text-[10px] leading-snug text-slate-500 dark:text-neutral-500">
              Tap a row for evidence, or use the row menu for copy and bookmarks.
            </p>
            <div className="divide-y divide-slate-100 dark:divide-neutral-800">
              {d.recentErrorsPreview.length ? (
                d.recentErrorsPreview.slice(0, 6).map((item) => (
                  <div key={item.group_key} className="flex items-start gap-1 py-2 first:pt-1">
                    <button
                      type="button"
                      onClick={() => setErrorModalItem(item)}
                      aria-label={`Open evidence for ${item.exception_type ?? "error"} on ${item.path}`}
                      className="min-w-0 flex-1 rounded-md px-1 py-0.5 text-left leading-tight outline-none transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:hover:bg-neutral-800/80 dark:focus-visible:ring-orange-400/35"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <span className="text-[11px] font-medium text-slate-800 dark:text-neutral-200">
                            {item.exception_type ?? "Error"}
                          </span>
                          <span className="text-[11px] text-slate-500 dark:text-neutral-500"> · </span>
                          <span className="font-mono text-[11px] text-slate-600 dark:text-neutral-300">{item.path}</span>
                        </div>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span
                            className="max-w-[6.5rem] truncate text-right text-[10px] text-slate-500 dark:text-neutral-500"
                            title={formatTimestamp(item.last_seen)}
                          >
                            {formatTimestamp(item.last_seen)}
                          </span>
                          <span
                            aria-label={`${item.count} ${item.count === 1 ? "occurrence" : "occurrences"}`}
                            className="rounded bg-rose-100 px-1.5 py-0 text-[10px] font-semibold text-rose-800 dark:bg-rose-900/40 dark:text-rose-200"
                          >
                            {item.count}×
                          </span>
                        </div>
                      </div>
                    </button>
                    <RowActionsMenu
                      items={buildErrorGroupEvidenceMenuItems({
                        item,
                        onOpenInModal: () => setErrorModalItem(item),
                        onSaveBookmark: () =>
                          setBookmarkDraft({
                            title: `${item.exception_type ?? "Error"} · ${item.path}`.slice(0, 200),
                            hashFragment: `error-group:${encodeURIComponent(item.group_key)}`,
                          }),
                      })}
                    />
                  </div>
                ))
              ) : (
                <p className="py-1 text-xs text-slate-500 dark:text-neutral-400">
                  {homeSlice.chartsScopePending ? "Refreshing…" : "No grouped errors in this window."}
                </p>
              )}
            </div>
          </div>
        </div>
      </section>
        {homeErrorModals}
      </>
    );
  }
}
