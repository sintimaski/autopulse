"use client";

import { useMemo } from "react";

import { MetricCard } from "../MetricCard";
import { useDashboardData } from "../DashboardDataContext";
import { useDashboardHomeSlice } from "../data/useDashboardSlices";
import {
  BreakdownBarChart,
  ChartPanel,
  DonutChart,
  HistogramChart,
  ScatterPlotChart,
  StackedAreaChart,
  TimeSeriesLineChart,
  type ScatterPlotPoint,
  type StackedAreaSeries,
} from "../charts";
import { resolveSparklineSeries, type OverviewBucket } from "../../../utils/dashboardData";
import { resolveOverviewExtendedForHome } from "../../../utils/overviewExtendedInference";
import type {
  BreakdownItem,
  DashboardWidgetDefinition,
  DashboardWidgetPoint,
  OverviewResponse,
  RequestItem,
  RequestsResponse,
} from "../dashboardTypes";

const widgetSeriesPalette = ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8", "#a78bfa"];

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
  if (!overview || !requests) {
    return (
      <section className="rounded-xl border border-white/10 bg-slate-950/30 p-4 text-sm text-slate-300">
        {d.errorMessage ?? "Loading widget gallery…"}
      </section>
    );
  }
  return (
    <DashboardWidgetGalleryBody d={d} homeSlice={homeSlice} overview={overview} requests={requests} />
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

  const widgetDefinitions = (d.dashboardWidgets?.definitions ?? []).filter(
    (item): item is DashboardWidgetDefinition =>
      item.type === "card" ||
      item.type === "line" ||
      item.type === "bar" ||
      item.type === "donut" ||
      item.type === "histogram" ||
      item.type === "scatter" ||
      item.type === "stacked_area",
  );
  const widgetPointsById = new Map<string, DashboardWidgetPoint[]>();
  for (const point of d.dashboardWidgets?.points ?? []) {
    const existing = widgetPointsById.get(point.widget_id) ?? [];
    existing.push(point);
    widgetPointsById.set(point.widget_id, existing);
  }

  return (
    <section className="space-y-8">
      <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h1 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Backend widget gallery</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Every chart type the dashboard can render from SDK widgets, plus sample charts built from the current
          overview scope. Uses the same window and filters as the rest of the app.
        </p>
      </div>

      {widgetDefinitions.length ? (
        <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Custom widgets</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
            Dynamically provided by your SDK widget classes.
          </p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {widgetDefinitions.map((widget) => {
              const points = (widgetPointsById.get(widget.widget_id) ?? []).sort((a, b) =>
                a.timestamp.localeCompare(b.timestamp),
              );
              if (widget.type === "card") {
                const latest = points[points.length - 1];
                const tone =
                  String(widget.config?.tone) === "danger"
                    ? "danger"
                    : String(widget.config?.tone) === "warning"
                      ? "warning"
                      : "neutral";
                const unit = typeof widget.config?.unit === "string" ? widget.config.unit : "";
                return (
                  <MetricCard
                    key={widget.widget_id}
                    label={widget.title}
                    value={`${latest?.value?.toFixed(2) ?? "0"}${unit ? ` ${unit}` : ""}`}
                    helper={widget.description ?? "Custom KPI"}
                    tone={tone}
                  />
                );
              }
              if (widget.type === "line") {
                return (
                  <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                    <TimeSeriesLineChart
                      title={widget.title}
                      labels={points.map((point) => new Date(point.timestamp).toLocaleTimeString())}
                      values={points.map((point) => point.value)}
                      color={typeof widget.config?.color === "string" ? widget.config.color : "#38bdf8"}
                      formatValue={(value) => value.toFixed(2)}
                    />
                  </ChartPanel>
                );
              }
              if (widget.type === "bar") {
                const latestByLabel = new Map<string, DashboardWidgetPoint>();
                for (const point of points) {
                  const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
                  const existing = latestByLabel.get(label);
                  if (!existing || existing.timestamp < point.timestamp) {
                    latestByLabel.set(label, point);
                  }
                }
                const collapsedBars = [...latestByLabel.entries()]
                  .map(([label, point]) => ({ key: label, value: point.value }))
                  .sort((a, b) => b.value - a.value);
                return (
                  <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                    <BreakdownBarChart items={collapsedBars} />
                  </ChartPanel>
                );
              }
              if (widget.type === "histogram") {
                const latestByLabel = new Map<string, DashboardWidgetPoint>();
                for (const point of points) {
                  const label = point.label ?? new Date(point.timestamp).toLocaleTimeString();
                  const existing = latestByLabel.get(label);
                  if (!existing || existing.timestamp < point.timestamp) {
                    latestByLabel.set(label, point);
                  }
                }
                const buckets = [...latestByLabel.entries()].map(([label, point]) => ({
                  label,
                  count: Math.max(0, Math.round(point.value)),
                }));
                return (
                  <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                    <HistogramChart buckets={buckets} />
                  </ChartPanel>
                );
              }
              if (widget.type === "scatter") {
                const scatterPoints: ScatterPlotPoint[] = points.map((point, index) => {
                  const [xValueRaw, freeLabel] = String(point.label ?? "").split("|", 2);
                  const parsedX = Number(xValueRaw);
                  const x = Number.isFinite(parsedX) ? parsedX : index + 1;
                  const y = Number(point.value || 0);
                  const label = freeLabel?.trim()
                    ? `${freeLabel} · x=${x.toFixed(2)} · y=${y.toFixed(2)}`
                    : `x=${x.toFixed(2)} · y=${y.toFixed(2)}`;
                  return {
                    id: `${widget.widget_id}-${index}`,
                    x,
                    y,
                    label,
                    tone: y >= 10 ? "danger" : y >= 3 ? "warning" : "neutral",
                  };
                });
                return (
                  <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                    <ScatterPlotChart
                      points={scatterPoints}
                      xLabel={typeof widget.config?.x_label === "string" ? widget.config.x_label : "X axis"}
                      yLabel={typeof widget.config?.y_label === "string" ? widget.config.y_label : "Y axis"}
                    />
                  </ChartPanel>
                );
              }
              if (widget.type === "stacked_area") {
                const timestampLabels = [...new Set(points.map((point) => point.timestamp))]
                  .sort((a, b) => a.localeCompare(b))
                  .map((ts) => new Date(ts).toLocaleTimeString());
                const timestampKeys = [...new Set(points.map((point) => point.timestamp))].sort((a, b) =>
                  a.localeCompare(b),
                );
                const bySeries = new Map<string, Map<string, number>>();
                for (const point of points) {
                  const seriesName = point.label ?? "series";
                  const entry = bySeries.get(seriesName) ?? new Map<string, number>();
                  entry.set(point.timestamp, point.value);
                  bySeries.set(seriesName, entry);
                }
                const stackedSeries = [...bySeries.entries()].map(([seriesName, valuesByTs], index) => ({
                  id: `${widget.widget_id}-${seriesName}`,
                  label: seriesName,
                  color: widgetSeriesPalette[index % widgetSeriesPalette.length],
                  values: timestampKeys.map((ts) => Number(valuesByTs.get(ts) ?? 0)),
                }));
                return (
                  <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                    <StackedAreaChart labels={timestampLabels} series={stackedSeries} />
                  </ChartPanel>
                );
              }
              const latestByLabel = new Map<string, DashboardWidgetPoint>();
              for (const point of points) {
                const label = point.label ?? "Value";
                const existing = latestByLabel.get(label);
                if (!existing || existing.timestamp < point.timestamp) {
                  latestByLabel.set(label, point);
                }
              }
              const collapsedSlices = [...latestByLabel.entries()]
                .map(([label, point], index) => ({
                  id: `${widget.widget_id}-${index}`,
                  label,
                  value: point.value,
                  color: ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8"][index % 5],
                }))
                .sort((a, b) => b.value - a.value);
              return (
                <ChartPanel key={widget.widget_id} title={widget.title} description={widget.description ?? undefined}>
                  <DonutChart title={widget.title} items={collapsedSlices} />
                </ChartPanel>
              );
            })}
          </div>
        </section>
      ) : (
        <p className="text-sm text-slate-600 dark:text-neutral-400">
          No SDK widget definitions returned for this project yet. Ingest traffic with dashboard widgets enabled to
          populate this section.
        </p>
      )}

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Chart options showcase</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          All available chart styles shown together: line, bars, donut, histogram, scatter, and stacked area.
        </p>
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <ChartPanel title="Line chart">
            <TimeSeriesLineChart
              title="Error trend"
              labels={d.sparklineSeries.map((bucket) =>
                new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              )}
              values={d.sparklineSeries.map((bucket) => Number(bucket.error_count || 0))}
              color="#f43f5e"
              formatValue={(value) => value.toFixed(0)}
            />
          </ChartPanel>
          <ChartPanel title="Bar chart">
            <BreakdownBarChart
              items={routeBreakdownByVolume.slice(0, 6).map((item) => ({
                key: item.key,
                value: item.request_count,
              }))}
              valueLabel="req"
            />
          </ChartPanel>
          <ChartPanel title="Donut chart">
            <DonutChart
              title="Status classes"
              items={statusDonutItems}
              centerLabel="Total"
              centerValue={String(statusClassTotal)}
            />
          </ChartPanel>
          <ChartPanel title="Histogram">
            <HistogramChart buckets={latencyHistogramBuckets} />
          </ChartPanel>
          <ChartPanel title="Scatter plot">
            <ScatterPlotChart points={showcaseScatterPoints} xLabel="Request volume" yLabel="Error rate %" />
          </ChartPanel>
          <ChartPanel title="Stacked area">
            <StackedAreaChart labels={statusClassLabels} series={outcomeStackedSeries} />
          </ChartPanel>
        </div>
      </section>
    </section>
  );
}
