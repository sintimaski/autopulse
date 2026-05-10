"use client";

import { useMemo } from "react";

import { CardSpinner } from "../../ui/CardSpinner";
import { useDashboardData } from "../DashboardDataContext";
import { GuidedTroubleshootingPanel } from "../GuidedTroubleshootingPanel";
import { DashboardChartShowcaseGrid } from "./DashboardChartShowcaseGrid";
import { DashboardCustomWidgetCharts } from "./DashboardCustomWidgetCharts";
import { WidgetsMockPreviewSection } from "./WidgetsMockPreviewSection";
import { WidgetsModalAccessibilitySample } from "./WidgetsModalAccessibilitySample";
import { useDashboardHomeSlice } from "../data/useDashboardSlices";
import type { ScatterPlotPoint, StackedAreaSeries } from "../charts";
import { resolveSparklineSeries, type OverviewBucket } from "../../../utils/dashboardData";
import { resolveOverviewExtendedForHome } from "../../../utils/overviewExtendedInference";
import type { BreakdownItem, OverviewResponse, RequestItem, RequestsResponse } from "../dashboardTypes";

function statusClassSplitTotal(series: OverviewBucket[]): number {
  return series.reduce(
    (sum, bucket) =>
      sum +
      Number(bucket.count_2xx || 0) +
      Number(bucket.count_3xx || 0) +
      Number(bucket.count_4xx || 0) +
      Number(bucket.count_5xx || 0),
    0,
  );
}

/** When `overview_extended.route_breakdown` is empty, derive routes from the loaded request sample. */
function inferRouteBreakdownFromItems(items: RequestItem[]): BreakdownItem[] {
  type Acc = { request_count: number; error_count: number; latencies: number[] };
  const map = new Map<string, Acc>();
  for (const item of items) {
    const key = String(item.path ?? "").trim() || "(unknown)";
    const acc = map.get(key) ?? { request_count: 0, error_count: 0, latencies: [] };
    acc.request_count += 1;
    if (item.status_code >= 500) {
      acc.error_count += 1;
    }
    const lat = Number(item.latency_ms);
    if (Number.isFinite(lat) && lat >= 0) {
      acc.latencies.push(lat);
    }
    map.set(key, acc);
  }
  return [...map.entries()].map(([key, acc]) => {
    const sorted = [...acc.latencies].sort((a, b) => a - b);
    const avg_latency_ms =
      sorted.length > 0 ? sorted.reduce((s, v) => s + v, 0) / sorted.length : 0;
    return {
      key,
      request_count: acc.request_count,
      error_count: acc.error_count,
      error_rate: acc.request_count ? acc.error_count / acc.request_count : 0,
      avg_latency_ms,
    };
  });
}

export function DashboardWidgetGalleryContent() {
  const d = useDashboardData();
  const homeSlice = useDashboardHomeSlice();
  const overview = homeSlice.overview;
  const requests = homeSlice.requests;

  return (
    <section className="space-y-8">
      <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h1 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Widgets</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Live charts and SDK widgets from your current overview scope, plus a timer-driven mock preview below for
          layout checks without traffic. Uses the same time window and filters as the rest of the console.
        </p>
      </div>

      <WidgetsModalAccessibilitySample />

      <GuidedTroubleshootingPanel />

      {overview && requests ? (
        <DashboardWidgetGalleryBody d={d} homeSlice={homeSlice} overview={overview} requests={requests} />
      ) : d.loading && !d.errorMessage ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <CardSpinner size="compact" label="Overview scope" />
          <CardSpinner size="compact" label="Request sample" />
        </div>
      ) : (
        <div className="rounded-xl border border-amber-500/30 bg-amber-50/90 p-4 text-sm text-amber-950 dark:border-amber-500/25 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-medium">Live gallery waiting for data</p>
          <p className="mt-1 text-amber-900/90 dark:text-amber-100/90">
            {d.errorMessage ??
              "No overview or request sample for this scope yet. Scroll down for the mock preview, which works immediately."}
          </p>
        </div>
      )}

      <WidgetsMockPreviewSection />
    </section>
  );
}

function DashboardWidgetGalleryBody({
  d,
  homeSlice,
  overview,
  requests,
}: {
  d: ReturnType<typeof useDashboardData>;
  homeSlice: ReturnType<typeof useDashboardHomeSlice>;
  overview: OverviewResponse;
  requests: RequestsResponse;
}) {
  const overviewExtended = useMemo(
    () => resolveOverviewExtendedForHome(overview, requests, homeSlice.overviewExtended),
    [overview, requests, homeSlice.overviewExtended],
  );

  const routeBreakdownBasis = useMemo((): BreakdownItem[] => {
    if (overviewExtended.route_breakdown.length > 0) {
      return overviewExtended.route_breakdown;
    }
    return inferRouteBreakdownFromItems(d.rawItems);
  }, [overviewExtended.route_breakdown, d.rawItems]);

  const routeBreakdownByVolume = useMemo(
    () => [...routeBreakdownBasis].sort((a, b) => b.request_count - a.request_count).slice(0, 10),
    [routeBreakdownBasis],
  );

  /** Overview minute buckets often omit per-status counts; rebuild from the request sample for demos. */
  const sparklineForStatusCharts = useMemo(() => {
    if (statusClassSplitTotal(d.sparklineSeries) > 0) {
      return d.sparklineSeries;
    }
    if ((requests.items?.length ?? 0) > 0) {
      return resolveSparklineSeries(overview, requests, { preferRequests: true });
    }
    return d.sparklineSeries;
  }, [d.sparklineSeries, overview, requests]);

  const total2xx = sparklineForStatusCharts.reduce((sum, bucket) => sum + Number(bucket.count_2xx || 0), 0);
  const total3xx = sparklineForStatusCharts.reduce((sum, bucket) => sum + Number(bucket.count_3xx || 0), 0);
  const total4xx = sparklineForStatusCharts.reduce((sum, bucket) => sum + Number(bucket.count_4xx || 0), 0);
  const total5xx = sparklineForStatusCharts.reduce((sum, bucket) => sum + Number(bucket.count_5xx || 0), 0);
  const statusClassTotal = total2xx + total3xx + total4xx + total5xx;
  const statusDonutItems = [
    { id: "2xx", label: "2xx", value: total2xx, color: "#34d399" },
    { id: "3xx", label: "3xx", value: total3xx, color: "#38bdf8" },
    { id: "4xx", label: "4xx", value: total4xx, color: "#f59e0b" },
    { id: "5xx", label: "5xx", value: total5xx, color: "#f43f5e" },
  ];
  const outcomeStackedSeries: StackedAreaSeries[] = [
    {
      id: "success",
      label: "Successful (2xx+3xx)",
      color: "#34d399",
      values: sparklineForStatusCharts.map(
        (bucket) => Number(bucket.count_2xx || 0) + Number(bucket.count_3xx || 0),
      ),
    },
    {
      id: "client",
      label: "Client errors (4xx)",
      color: "#f59e0b",
      values: sparklineForStatusCharts.map((bucket) => Number(bucket.count_4xx || 0)),
    },
    {
      id: "server",
      label: "Server errors (5xx)",
      color: "#f43f5e",
      values: sparklineForStatusCharts.map((bucket) => Number(bucket.count_5xx || 0)),
    },
  ];
  const routeRiskScatter = useMemo(
    (): ScatterPlotPoint[] =>
      [...routeBreakdownBasis]
        .sort((a, b) => b.request_count - a.request_count)
        .slice(0, 20)
        .map((route) => {
          const errorRatePct = route.error_rate * 100;
          return {
            id: route.key,
            x: route.request_count,
            y: errorRatePct,
            label: `${route.key} · ${route.request_count} req · ${errorRatePct.toFixed(2)}% err`,
            tone: errorRatePct >= 10 ? "danger" : errorRatePct >= 3 ? "warning" : "neutral",
          };
        }),
    [routeBreakdownBasis],
  );
  const latencyHistogramBuckets = useMemo(() => {
    const ranges = [
      { label: "<50ms", min: 0, max: 50 },
      { label: "50-100ms", min: 50, max: 100 },
      { label: "100-250ms", min: 100, max: 250 },
      { label: "250-500ms", min: 250, max: 500 },
      { label: "500-1000ms", min: 500, max: 1000 },
      { label: "1s+", min: 1000, max: Number.POSITIVE_INFINITY },
    ];
    return ranges.map((range) => ({
      label: range.label,
      count: d.rawItems.filter((item) => item.latency_ms >= range.min && item.latency_ms < range.max).length,
    }));
  }, [d.rawItems]);
  const statusClassLabels = sparklineForStatusCharts.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const showcaseScatterPoints: ScatterPlotPoint[] = routeRiskScatter.slice(0, 8);

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-50">Live gallery</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Charts built from the current overview scope and request sample.
        </p>
      </div>

      <DashboardCustomWidgetCharts
        definitions={d.dashboardWidgets?.definitions ?? []}
        points={d.dashboardWidgets?.points ?? []}
        heading="Custom widgets"
        description="Dynamically provided by your SDK widget classes."
        emptyMessage="No SDK widget definitions returned for this project yet. Ingest traffic with dashboard widgets enabled to populate this section."
      />

      <DashboardChartShowcaseGrid
        lineLabels={d.sparklineSeries.map((bucket) =>
          new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        )}
        lineValues={d.sparklineSeries.map((bucket) => Number(bucket.error_count || 0))}
        barItems={routeBreakdownByVolume.slice(0, 6).map((item) => ({
          key: item.key,
          value: item.request_count,
        }))}
        donutItems={statusDonutItems}
        donutCenterValue={String(statusClassTotal)}
        histogramBuckets={latencyHistogramBuckets}
        scatterPoints={showcaseScatterPoints}
        stackedLabels={statusClassLabels}
        stackedSeries={outcomeStackedSeries}
      />
    </div>
  );
}
