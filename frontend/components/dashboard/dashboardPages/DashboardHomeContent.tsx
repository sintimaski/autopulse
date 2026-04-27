"use client";

import Link from "next/link";

import { MetricCard } from "../MetricCard";
import { OverviewScopeFacetBoard } from "../OverviewScopeFacetBoard";
import { SparklineMini } from "../SparklineMini";
import { StatusPill } from "../StatusPill";
import { VolumeChart } from "../VolumeChart";
import { useDashboardData } from "../DashboardDataContext";
import {
  BreakdownBarChart,
  ChartPanel,
  MultiSeriesLineChart,
  PercentileLadder,
  type MultiSeriesLineChartSeries,
} from "../charts";
import { buildScopedQuery } from "../dashboardQueryState";
import { formatTimestamp } from "../dashboardTypes";

export function DashboardHomeContent() {
  const d = useDashboardData();
  const overview = d.overview;
  const requests = d.requests;
  const overviewExtended = d.overviewExtended;
  if (!overview || !requests || !overviewExtended) {
    return null;
  }
  const derivedRequestCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.request_count || 0),
    0,
  );
  const derivedErrorCount = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.error_count || 0),
    0,
  );
  const derivedLatencyWeighted = d.sparklineSeries.reduce(
    (sum, bucket) => sum + Number(bucket.avg_latency_ms || 0) * Number(bucket.request_count || 0),
    0,
  );
  const displayRequestCount = derivedRequestCount || overview.request_count;
  const displayErrorCount = derivedRequestCount ? derivedErrorCount : overview.error_count;
  const displayErrorRate = displayRequestCount ? displayErrorCount / displayRequestCount : 0;
  const displayAvgLatencyMs = displayRequestCount
    ? derivedLatencyWeighted / displayRequestCount
    : overview.avg_latency_ms;
  const displayRequestsPerMinute = displayRequestCount / Math.max(d.windowMinutes, 1);
  const usingFilteredSeries = d.method !== "ALL" || d.statusClass !== "ALL";
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
    sqlFilterApplied: d.sqlFilterApplied,
    sqlFilterEnabled: d.sqlFilterEnabled,
  });
  const diagnosisBaseHref = `/diagnosis?${diagnosisParams.toString()}`;
  const diagnosisGroupedHref = `/diagnosis?${(() => {
    const params = new URLSearchParams(diagnosisParams.toString());
    params.set("error_group_sort", "count");
    return params.toString();
  })()}#grouped-errors`;
  const errorTrendValues = d.sparklineSeries.map((bucket) => bucket.error_count);
  const latencyTrendValues = d.sparklineSeries.map((bucket) => bucket.avg_latency_ms);
  const serviceBreakdownByVolume = [...overviewExtended.service_breakdown]
    .sort((a, b) => b.request_count - a.request_count)
    .slice(0, 10);
  const routeBreakdownByVolume = [...overviewExtended.route_breakdown]
    .sort((a, b) => b.request_count - a.request_count)
    .slice(0, 10);
  const statusClassLabels = d.sparklineSeries.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const statusClassSeries: MultiSeriesLineChartSeries[] = [
    {
      id: "2xx",
      label: "2xx",
      color: "#10b981",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_2xx || 0)),
    },
    {
      id: "3xx",
      label: "3xx",
      color: "#0ea5e9",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_3xx || 0)),
    },
    {
      id: "4xx",
      label: "4xx",
      color: "#f59e0b",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_4xx || 0)),
    },
    {
      id: "5xx",
      label: "5xx",
      color: "#f43f5e",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_5xx || 0)),
    },
  ];

  return (
    <>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Requests / min" value={displayRequestsPerMinute.toFixed(2)} />
        <MetricCard
          label="Error rate"
          value={`${(displayErrorRate * 100).toFixed(1)}%`}
          helper={usingFilteredSeries ? "Derived from current filtered request slice" : "5xx + ingested error events"}
          tone="danger"
        />
        <MetricCard
          label="Latency (p95)"
          value={`${overviewExtended.p95_latency_ms.toFixed(1)} ms`}
          helper={`p50 ${overviewExtended.p50_latency_ms.toFixed(1)} · p99 ${overviewExtended.p99_latency_ms.toFixed(1)}`}
          tone={overviewExtended.p95_latency_ms >= 300 ? "warning" : "neutral"}
        />
        <MetricCard
          label="Active incidents"
          value={String(overviewExtended.active_incident_count)}
          helper={`Error bursts (5m): ${overviewExtended.error_burst_count}`}
          tone={overviewExtended.active_incident_count > 0 ? "danger" : "neutral"}
        />
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 px-3 py-2.5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <OverviewScopeFacetBoard />
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {overviewExtended.error_burst_count > 0 ? (
              <StatusPill label="Error burst detected" tone="danger" />
            ) : (
              <StatusPill label="No active burst" tone="success" />
            )}
            <Link
              href={diagnosisGroupedHref}
              className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Grouped errors
            </Link>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Traffic graphs</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Requests (bars) and trend cards for volume, error rate, error count, and latency. Hover for values or
          click a bar to open Diagnosis for that bucket.{" "}
          <Link href={diagnosisBaseHref} className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300">
            Diagnosis
          </Link>
          .
        </p>
        <div className="mt-3">
          <VolumeChart
            series={d.sparklineSeries}
            fromTimestamp={overview.from_timestamp}
            toTimestamp={overview.to_timestamp}
            globalWindowMinutes={d.windowMinutes}
            diagnosisBaseQuery={Object.fromEntries(diagnosisParams.entries())}
          />
        </div>
        {overview.series.length === 0 && d.sparklineSeries.length > 0 && (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
            Backend minute series is empty for this range; buckets are derived from the loaded request
            page.
          </p>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <ChartPanel title="Error trend" description="Minute-level error counts in current scope.">
          <SparklineMini values={errorTrendValues} colorClass="text-rose-600 dark:text-rose-300" />
        </ChartPanel>
        <ChartPanel title="Latency trend" description="Average minute latency in milliseconds.">
          <SparklineMini values={latencyTrendValues} colorClass="text-amber-600 dark:text-amber-300" />
        </ChartPanel>
        <ChartPanel
          title="Latency shape"
          description={`Window average ${displayAvgLatencyMs.toFixed(1)} ms`}
        >
          <PercentileLadder
            p50={overviewExtended.p50_latency_ms}
            p95={overviewExtended.p95_latency_ms}
            p99={overviewExtended.p99_latency_ms}
          />
        </ChartPanel>
      </section>

      {overview.request_count === 0 ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/30">
          <h2 className="text-base font-semibold text-amber-900 dark:text-amber-200">
            No traffic in this window yet
          </h2>
          <p className="mt-1 text-sm text-amber-900/90 dark:text-amber-100/90">
            Send traffic to <code className="rounded bg-amber-100 px-1">POST /ingest</code>, then use
            refresh in the header. You can also validate grouped errors on{" "}
            <Link href={diagnosisBaseHref} className="font-medium underline underline-offset-2">
              Diagnosis
            </Link>
            .
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <ChartPanel title="Top failing routes" actionHref={diagnosisBaseHref} actionLabel="Full diagnosis">
          {d.topFailingRoutes.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-neutral-300">
              No 5xx failures in the current request sample.
            </p>
          ) : (
            <ul className="space-y-2">
              {d.topFailingRoutes.map(([path, count]) => (
                <li key={path} className="flex items-start justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-mono text-xs text-slate-800 dark:text-neutral-100">
                    {path}
                  </span>
                  <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-900/50 dark:text-rose-300">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </ChartPanel>

        <ChartPanel title="Recent errors" actionHref={diagnosisGroupedHref} actionLabel="Grouped list">
          {d.recentErrorsPreview.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-neutral-300">
              No grouped errors in this time window.
            </p>
          ) : (
            <ul className="space-y-2">
              {d.recentErrorsPreview.map((item) => (
                <li
                  key={item.group_key}
                  className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/70"
                >
                  <Link
                    href={`/diagnosis?${(() => {
                      const params = new URLSearchParams(diagnosisParams.toString());
                      params.set("error_group_sort", "count");
                      // Do not set path_contains here: narrowing to one route hides every other
                      // group and that scope persists for Diagnosis (sidebar + session).
                      return params.toString();
                    })()}#grouped-errors`}
                    className="block"
                  >
                    <p className="text-sm font-medium text-slate-900 dark:text-neutral-100">
                      {item.exception_type ?? "Error"}{" "}
                      <span className="text-slate-500 dark:text-neutral-400">on</span>{" "}
                      <span className="font-mono text-xs">{item.path}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-slate-600 dark:text-neutral-300">
                      Last seen {formatTimestamp(item.last_seen)} · Count {item.count}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </ChartPanel>

        <ChartPanel
          title="Top services by request volume"
          description="Highest traffic services in this window."
          actionHref={diagnosisBaseHref}
          actionLabel="Open diagnosis"
        >
          <BreakdownBarChart
            items={serviceBreakdownByVolume.map((item) => ({
              key: item.key,
              value: item.request_count,
              secondaryLabel: "error rate",
              secondaryValue: item.error_rate * 100,
            }))}
            valueLabel="req"
            emptyMessage="No service-level data yet."
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartPanel
          title="Responses by class"
          description="Per-minute response classes across the active scope."
          actionHref={diagnosisBaseHref}
          actionLabel="Open diagnosis"
        >
          <MultiSeriesLineChart labels={statusClassLabels} series={statusClassSeries} />
        </ChartPanel>
        <ChartPanel
          title="Top routes by request volume"
          description="Highest traffic routes in this window."
          actionHref={diagnosisBaseHref}
          actionLabel="Open diagnosis"
        >
          <BreakdownBarChart
            items={routeBreakdownByVolume.map((item) => ({
              key: item.key,
              value: item.request_count,
              secondaryLabel: "error rate",
              secondaryValue: item.error_rate * 100,
            }))}
            valueLabel="req"
            emptyMessage="No route breakdown available."
          />
        </ChartPanel>
      </section>
    </>
  );
}
