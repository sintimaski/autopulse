"use client";

import { dashboardPanelP5 } from "../dashboardCardStyles";
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
import type {
  DashboardWidgetDefinition,
  DashboardWidgetPoint,
  OverviewExtendedResponse,
} from "../dashboardTypes";

const widgetSeriesPalette = ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8", "#a78bfa"];

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
  const overviewExtended: OverviewExtendedResponse = homeSlice.overviewExtended ?? {
    server_now: overview.server_now,
    from_timestamp: overview.from_timestamp,
    to_timestamp: overview.to_timestamp,
    p50_latency_ms: overview.avg_latency_ms,
    p95_latency_ms: overview.avg_latency_ms,
    p99_latency_ms: overview.avg_latency_ms,
    apdex_score: 1,
    active_sessions_estimate: 0,
    error_burst_count: 0,
    active_incident_count: 0,
    error_type_breakdown: [],
    alerts_timeline: [],
    service_breakdown: [],
    route_breakdown: [],
  };
  const routeBreakdownByVolume = [...overviewExtended.route_breakdown]
    .sort((a, b) => b.request_count - a.request_count)
    .slice(0, 10);
  const total2xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_2xx || 0), 0);
  const total3xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_3xx || 0), 0);
  const total4xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_4xx || 0), 0);
  const total5xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_5xx || 0), 0);
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
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_2xx || 0) + Number(bucket.count_3xx || 0)),
    },
    {
      id: "client",
      label: "Client errors (4xx)",
      color: "#f59e0b",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_4xx || 0)),
    },
    {
      id: "server",
      label: "Server errors (5xx)",
      color: "#f43f5e",
      values: d.sparklineSeries.map((bucket) => Number(bucket.count_5xx || 0)),
    },
  ];
  const routeRiskScatter: ScatterPlotPoint[] = [...overviewExtended.route_breakdown]
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
    });
  const latencyHistogramBuckets = (() => {
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
  })();
  const statusClassLabels = d.sparklineSeries.map((bucket) =>
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
      <div className={dashboardPanelP5}>
        <h1 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Backend widget gallery</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
          Every chart type the dashboard can render from SDK widgets, plus sample charts built from the current
          overview scope. Uses the same window and filters as the rest of the app.
        </p>
      </div>

      {widgetDefinitions.length ? (
        <section className={dashboardPanelP5}>
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

      <section className={dashboardPanelP5}>
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
