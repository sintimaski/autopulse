"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { MetricCard } from "../MetricCard";
import { OverviewScopeFacetBoard } from "../OverviewScopeFacetBoard";
import { SparklineMini } from "../SparklineMini";
import { StatusPill } from "../StatusPill";
import { VolumeChart } from "../VolumeChart";
import { GuidedTroubleshootingPanel } from "../GuidedTroubleshootingPanel";
import { useDashboardData } from "../DashboardDataContext";
import {
  BreakdownBarChart,
  ChartPanel,
  DonutChart,
  HeatmapGrid,
  HistogramChart,
  MultiSeriesLineChart,
  PercentileLadder,
  ScatterPlotChart,
  StackedAreaChart,
  TimeSeriesLineChart,
  type MultiSeriesLineChartSeries,
  type ScatterPlotPoint,
  type StackedAreaSeries,
} from "../charts";
import { buildScopedQuery } from "../dashboardQueryState";
import { formatTimestamp, type DashboardWidgetDefinition, type DashboardWidgetPoint } from "../dashboardTypes";

export function DashboardHomeContent() {
  const router = useRouter();
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
  const total2xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_2xx || 0), 0);
  const total3xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_3xx || 0), 0);
  const total4xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_4xx || 0), 0);
  const total5xx = d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_5xx || 0), 0);
  const statusClassTotal = total2xx + total3xx + total4xx + total5xx;
  const statusCoveragePct = displayRequestCount
    ? Math.min(100, (statusClassTotal / displayRequestCount) * 100)
    : 0;
  const successRatePct = displayRequestCount ? (total2xx / displayRequestCount) * 100 : 0;
  const clientErrorRatePct = displayRequestCount ? (total4xx / displayRequestCount) * 100 : 0;
  const serverErrorRatePct = displayRequestCount ? (total5xx / displayRequestCount) * 100 : 0;
  const methodCounts = d.rawItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.method] = (acc[item.method] ?? 0) + 1;
    return acc;
  }, {});
  const methodDonutItems = Object.entries(methodCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([method, count], idx) => ({
      id: method,
      label: method,
      value: count,
      color: ["#38bdf8", "#818cf8", "#f59e0b", "#f43f5e", "#34d399", "#a78bfa"][idx % 6],
    }));
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
      count: d.rawItems.filter(
        (item) => item.latency_ms >= range.min && item.latency_ms < range.max,
      ).length,
    }));
  })();
  const routeStatusHeatmap = (() => {
    const topRoutes = routeBreakdownByVolume.slice(0, 6).map((route) => route.key);
    const xLabels = ["2xx", "3xx", "4xx", "5xx"];
    const cells: Array<{ x: string; y: string; value: number }> = [];
    for (const route of topRoutes) {
      const rows = d.rawItems.filter((item) => item.path === route);
      const byClass = {
        "2xx": rows.filter((item) => item.status_code >= 200 && item.status_code < 300).length,
        "3xx": rows.filter((item) => item.status_code >= 300 && item.status_code < 400).length,
        "4xx": rows.filter((item) => item.status_code >= 400 && item.status_code < 500).length,
        "5xx": rows.filter((item) => item.status_code >= 500).length,
      };
      for (const x of xLabels) {
        cells.push({ x, y: route, value: byClass[x as keyof typeof byClass] });
      }
    }
    return { cells, xLabels, yLabels: topRoutes };
  })();
  const apdexThresholdMs = { satisfied: 300, tolerated: 1200 };
  const apdexByMinute = (() => {
    const minuteStats = new Map<string, { total: number; satisfied: number; tolerated: number }>();
    for (const item of d.rawItems) {
      const minute = new Date(item.timestamp);
      minute.setSeconds(0, 0);
      const key = minute.toISOString();
      const current = minuteStats.get(key) ?? { total: 0, satisfied: 0, tolerated: 0 };
      current.total += 1;
      if (item.latency_ms <= apdexThresholdMs.satisfied) {
        current.satisfied += 1;
      } else if (item.latency_ms <= apdexThresholdMs.tolerated) {
        current.tolerated += 1;
      }
      minuteStats.set(key, current);
    }
    return [...minuteStats.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([minute, stat]) => ({
        minute,
        score: stat.total > 0 ? (stat.satisfied + stat.tolerated / 2) / stat.total : 1,
      }));
  })();
  const apdexTrendLabels = apdexByMinute.map((point) =>
    new Date(point.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const apdexTrendValues = apdexByMinute.map((point) => Number((point.score * 100).toFixed(2)));
  const errorBreakdownBars = overviewExtended.error_type_breakdown.map((item) => ({
    key: item.error_type,
    value: item.count,
  }));
  const alertTimelineByMinute = (() => {
    const counts = new Map<string, number>();
    for (const alert of overviewExtended.alerts_timeline) {
      const minute = new Date(alert.triggered_at);
      minute.setSeconds(0, 0);
      const key = minute.toISOString();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([minute, count]) => ({
        minute,
        count,
      }));
  })();
  const alertTimelineLabels = alertTimelineByMinute.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const alertTimelineValues = alertTimelineByMinute.map((bucket) => bucket.count);
  const widgetSeriesPalette = ["#34d399", "#38bdf8", "#f59e0b", "#f43f5e", "#818cf8", "#a78bfa"];
  const showcaseHistogramBuckets = latencyHistogramBuckets;
  const showcaseScatterPoints: ScatterPlotPoint[] = routeRiskScatter.slice(0, 8);
  const showcaseStackedSeries: StackedAreaSeries[] = outcomeStackedSeries;
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
  const fullMetricRows: Array<{ label: string; value: string; helper?: string }> = [
    { label: "Requests (total)", value: String(displayRequestCount), helper: "Overview scope" },
    { label: "Errors (total)", value: String(displayErrorCount), helper: "5xx + error events" },
    { label: "Error rate", value: `${(displayErrorRate * 100).toFixed(2)}%` },
    { label: "Requests / min", value: displayRequestsPerMinute.toFixed(2) },
    { label: "Latency avg", value: `${displayAvgLatencyMs.toFixed(1)} ms` },
    { label: "Latency p50", value: `${overviewExtended.p50_latency_ms.toFixed(1)} ms` },
    { label: "Latency p95", value: `${overviewExtended.p95_latency_ms.toFixed(1)} ms` },
    { label: "Latency p99", value: `${overviewExtended.p99_latency_ms.toFixed(1)} ms` },
    { label: "Apdex", value: overviewExtended.apdex_score.toFixed(3), helper: "Satisfied <=300ms, tolerated <=1200ms" },
    { label: "Active sessions (estimate)", value: String(overviewExtended.active_sessions_estimate) },
    { label: "Active incidents", value: String(overviewExtended.active_incident_count) },
    { label: "Error bursts (5m)", value: String(overviewExtended.error_burst_count) },
    { label: "Service breakdown rows", value: String(overviewExtended.service_breakdown.length) },
    { label: "Route breakdown rows", value: String(overviewExtended.route_breakdown.length) },
    { label: "Series minute buckets", value: String(d.sparklineSeries.length) },
    { label: "Status 2xx total", value: String(total2xx) },
    { label: "Status 3xx total", value: String(total3xx) },
    { label: "Status 4xx total", value: String(total4xx) },
    { label: "Status 5xx total", value: String(total5xx) },
    { label: "Success rate (2xx)", value: `${successRatePct.toFixed(2)}%` },
    { label: "Client error rate (4xx)", value: `${clientErrorRatePct.toFixed(2)}%` },
    { label: "Server error rate (5xx)", value: `${serverErrorRatePct.toFixed(2)}%` },
    {
      label: "Status-class coverage",
      value: `${statusCoveragePct.toFixed(1)}%`,
      helper: "Status totals vs request total",
    },
  ];
  const primarySignalCards: Array<{
    label: string;
    value: string;
    helper?: string;
    tone: "neutral" | "warning" | "danger";
  }> = [
    {
      label: "Active incidents",
      value: String(overviewExtended.active_incident_count),
      helper: `Error bursts (5m): ${overviewExtended.error_burst_count}`,
      tone: overviewExtended.active_incident_count > 0 ? "danger" : "neutral",
    },
    {
      label: "Error rate",
      value: `${(displayErrorRate * 100).toFixed(2)}%`,
      helper: usingFilteredSeries
        ? "Derived from current filtered request slice"
        : "5xx + ingested error events",
      tone: displayErrorRate >= 0.1 ? "danger" : displayErrorRate >= 0.03 ? "warning" : "neutral",
    },
    {
      label: "Latency p95",
      value: `${overviewExtended.p95_latency_ms.toFixed(1)} ms`,
      helper: `p50 ${overviewExtended.p50_latency_ms.toFixed(1)} · p99 ${overviewExtended.p99_latency_ms.toFixed(1)}`,
      tone: overviewExtended.p95_latency_ms >= 300 ? "danger" : overviewExtended.p95_latency_ms >= 120 ? "warning" : "neutral",
    },
    {
      label: "Requests / min",
      value: displayRequestsPerMinute.toFixed(2),
      helper: `Total requests: ${displayRequestCount}`,
      tone: "neutral",
    },
  ];
  const secondarySignalCards: Array<{
    label: string;
    value: string;
    helper?: string;
    tone: "neutral" | "warning" | "danger";
  }> = [
    {
      label: "Errors (total)",
      value: String(displayErrorCount),
      helper: "Across selected window",
      tone: displayErrorCount > 0 ? "warning" : "neutral",
    },
    {
      label: "Latency avg",
      value: `${displayAvgLatencyMs.toFixed(1)} ms`,
      helper: `vs p95 ${overviewExtended.p95_latency_ms.toFixed(1)} ms`,
      tone: displayAvgLatencyMs >= 200 ? "warning" : "neutral",
    },
    {
      label: "Latency p99",
      value: `${overviewExtended.p99_latency_ms.toFixed(1)} ms`,
      helper: `p95 ${overviewExtended.p95_latency_ms.toFixed(1)} ms`,
      tone: overviewExtended.p99_latency_ms >= 500 ? "danger" : overviewExtended.p99_latency_ms >= 250 ? "warning" : "neutral",
    },
    {
      label: "Apdex",
      value: overviewExtended.apdex_score.toFixed(3),
      helper: "Satisfied <=300ms, tolerated <=1200ms",
      tone:
        overviewExtended.apdex_score < 0.85
          ? "danger"
          : overviewExtended.apdex_score < 0.94
            ? "warning"
            : "neutral",
    },
    {
      label: "Active sessions",
      value: String(overviewExtended.active_sessions_estimate),
      helper: "Derived from session_id/user_id/request_id",
      tone: "neutral",
    },
  ];
  const metricsByGroup: Array<{ title: string; rows: Array<{ label: string; value: string; helper?: string }> }> = [
    {
      title: "Volume and errors",
      rows: fullMetricRows.filter((row) =>
        [
          "Requests (total)",
          "Errors (total)",
          "Error rate",
          "Requests / min",
          "Error bursts (5m)",
          "Active incidents",
        ].includes(row.label),
      ),
    },
    {
      title: "Latency",
      rows: fullMetricRows.filter((row) =>
        ["Latency avg", "Latency p50", "Latency p95", "Latency p99", "Apdex"].includes(row.label),
      ),
    },
    {
      title: "Status-class and breakdown coverage",
      rows: fullMetricRows.filter((row) =>
        [
          "Status 2xx total",
          "Status 3xx total",
          "Status 4xx total",
          "Status 5xx total",
          "Success rate (2xx)",
          "Client error rate (4xx)",
          "Server error rate (5xx)",
          "Status-class coverage",
          "Active sessions (estimate)",
          "Service breakdown rows",
          "Route breakdown rows",
          "Series minute buckets",
        ].includes(row.label),
      ),
    },
  ];
  const denseInsightLayout = d.recentErrorsPreview.length > 0 && d.topFailingRoutes.length > 0;
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
  const containsKeyword = (corpus: string, keyword: string) => {
    const normalizedCorpus = corpus.toLowerCase();
    const normalizedKeyword = keyword.toLowerCase().trim();
    if (!normalizedKeyword) {
      return false;
    }
    // Multi-word or punctuated keywords are treated as exact phrases.
    if (normalizedKeyword.includes(" ") || normalizedKeyword.includes("/") || normalizedKeyword.includes("-")) {
      return normalizedCorpus.includes(normalizedKeyword);
    }
    const escaped = normalizedKeyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`\\b${escaped}\\b`, "i");
    return re.test(normalizedCorpus);
  };
  const findWidgetByKeywords = (keywords: string[]) =>
    widgetDefinitions.find((widget) => {
      const corpus = `${widget.widget_id} ${widget.title} ${widget.description ?? ""}`.toLowerCase();
      return keywords.some((keyword) => containsKeyword(corpus, keyword));
    });
  const lineWidgetToSeries = (widget: DashboardWidgetDefinition | undefined) => {
    if (!widget) {
      return { labels: [] as string[], values: [] as number[] };
    }
    const points = [...(widgetPointsById.get(widget.widget_id) ?? [])].sort((a, b) =>
      a.timestamp.localeCompare(b.timestamp),
    );
    return {
      labels: points.map((point) =>
        new Date(point.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      ),
      values: points.map((point) => Number(point.value)),
    };
  };
  const formatMetricValue = (value: number, unit: string | null | undefined) => {
    const normalized = (unit ?? "").toLowerCase();
    if (normalized === "%" || normalized === "percent") {
      return `${value.toFixed(1)}%`;
    }
    if (normalized === "mb") {
      return value >= 1024 ? `${(value / 1024).toFixed(2)} GB` : `${value.toFixed(1)} MB`;
    }
    if (normalized === "gb") {
      return `${value.toFixed(2)} GB`;
    }
    return unit ? `${value.toFixed(2)} ${unit}` : value.toFixed(2);
  };
  const latestWidgetValue = (widget: DashboardWidgetDefinition | undefined) => {
    if (!widget) {
      return null;
    }
    const points = widgetPointsById.get(widget.widget_id) ?? [];
    if (!points.length) {
      return null;
    }
    const latest = points.reduce((winner, point) =>
      winner.timestamp > point.timestamp ? winner : point,
    );
    return Number(latest.value || 0);
  };
  const toInfrastructureCard = ({
    label,
    rawValue,
    unit,
    helper,
    warningThreshold,
    dangerThreshold,
  }: {
    label: string;
    rawValue: number | null;
    unit?: string;
    helper: string;
    warningThreshold?: number;
    dangerThreshold?: number;
  }) => {
    if (rawValue === null || Number.isNaN(rawValue)) {
      return {
        label,
        value: "No data yet",
        helper: `${helper} (waiting for infrastructure samples)`,
        tone: "neutral" as const,
      };
    }
    const tone =
      typeof dangerThreshold === "number" && rawValue >= dangerThreshold
        ? ("danger" as const)
        : typeof warningThreshold === "number" && rawValue >= warningThreshold
          ? ("warning" as const)
          : ("neutral" as const);
    return {
      label,
      value: formatMetricValue(rawValue, unit),
      helper,
      tone,
    };
  };
  const latestLabeledBars = (widget: DashboardWidgetDefinition | undefined) => {
    if (!widget) {
      return [] as Array<{ key: string; value: number }>;
    }
    const points = widgetPointsById.get(widget.widget_id) ?? [];
    const latestByLabel = new Map<string, DashboardWidgetPoint>();
    for (const point of points) {
      const label = point.label ?? "value";
      const existing = latestByLabel.get(label);
      if (!existing || existing.timestamp < point.timestamp) {
        latestByLabel.set(label, point);
      }
    }
    return [...latestByLabel.entries()]
      .map(([label, point]) => ({ key: label, value: Number(point.value) }))
      .sort((a, b) => b.value - a.value);
  };
  const dependencyWidget = findWidgetByKeywords(["dependency", "service map", "upstream", "downstream"]);
  const dependencyEdges = (() => {
    if (!dependencyWidget) {
      return [] as Array<{ from: string; to: string; weight: number }>;
    }
    const points = widgetPointsById.get(dependencyWidget.widget_id) ?? [];
    const edgeMap = new Map<string, { from: string; to: string; weight: number }>();
    for (const point of points) {
      const label = String(point.label ?? "").trim();
      if (!label || !label.includes("->")) {
        continue;
      }
      const [fromRaw, toRaw] = label.split("->", 2);
      const from = fromRaw.trim();
      const to = toRaw.trim();
      if (!from || !to) {
        continue;
      }
      const key = `${from}->${to}`;
      const existing = edgeMap.get(key);
      const weight = Number(point.value || 0);
      if (!existing || weight > existing.weight) {
        edgeMap.set(key, { from, to, weight });
      }
    }
    return [...edgeMap.values()].sort((a, b) => b.weight - a.weight).slice(0, 10);
  })();
  const cpuWidget = findWidgetByKeywords(["cpu"]);
  const memoryWidget = findWidgetByKeywords(["memory", "ram"]);
  const diskWidget = findWidgetByKeywords(["disk", "i/o", "io"]);
  const networkWidget = findWidgetByKeywords(["network", "bandwidth", "bytes in", "bytes out"]);
  const dbWidget = findWidgetByKeywords(["db", "database", "query", "sql"]);
  const cacheWidget = findWidgetByKeywords(["cache", "hit", "miss", "redis"]);
  const cpuSeries = lineWidgetToSeries(cpuWidget);
  const memorySeries = lineWidgetToSeries(memoryWidget);
  const diskSeries = lineWidgetToSeries(diskWidget);
  const networkSeries = lineWidgetToSeries(networkWidget);
  const dbBars = latestLabeledBars(dbWidget);
  const cacheBars = latestLabeledBars(cacheWidget);
  const fallbackMinuteLabels = d.sparklineSeries.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const cpuFallbackValues = d.sparklineSeries.map((bucket) => Number(bucket.request_count || 0));
  const memoryFallbackValues = d.sparklineSeries.map((bucket) => Number(bucket.avg_latency_ms || 0));
  const diskFallbackValues = d.sparklineSeries.map((bucket) => Number(bucket.error_count || 0));
  const networkFallbackValues = d.sparklineSeries.map((bucket) => Number(bucket.request_count || 0));
  const dbFallbackBars = routeBreakdownByVolume.map((item) => ({
    key: item.key,
    value: Number(item.avg_latency_ms || 0),
  }));
  const cacheFallbackBars = [
    { key: "estimated_hit", value: Number(total2xx + total3xx) },
    { key: "estimated_miss", value: Number(total4xx + total5xx) },
  ];
  const dependencyFallbackEdges = serviceBreakdownByVolume.slice(0, 8).map((item) => ({
    from: "edge",
    to: item.key,
    weight: Number(item.request_count || 0),
  }));
  const widgetSearchCorpus = widgetDefinitions
    .map((widget) => `${widget.widget_id} ${widget.title} ${widget.description ?? ""}`.toLowerCase())
    .join(" ");
  const infraMetricCoverage = [
    { label: "CPU usage", keywords: ["cpu", "load", "utilization"] },
    { label: "Memory usage", keywords: ["memory", "ram", "heap"] },
    { label: "Disk I/O", keywords: ["disk i/o", "disk io", "disk throughput", "disk read", "disk write"] },
    { label: "Network traffic", keywords: ["network", "bandwidth", "bytes in", "bytes out", "ingress", "egress", "rx", "tx"] },
    { label: "DB query performance", keywords: ["db", "database", "query", "sql"] },
    { label: "Cache hit/miss", keywords: ["cache hit", "cache miss", "cache ratio", "cache", "redis"] },
    { label: "Dependency map", keywords: ["dependency", "service map", "upstream", "downstream"] },
  ].map((item) => ({
    ...item,
    ready: item.keywords.some((keyword) => containsKeyword(widgetSearchCorpus, keyword)),
  }));
  const incidentState =
    overviewExtended.active_incident_count > 0 || displayErrorRate >= 0.08
      ? "critical"
      : overviewExtended.error_burst_count > 0 || displayErrorRate >= 0.03
        ? "degraded"
        : "healthy";
  const incidentSummary =
    incidentState === "critical"
      ? "Critical: elevated error pressure detected."
      : incidentState === "degraded"
        ? "Service degraded: errors are above baseline."
        : "Healthy: no active burst detected.";
  const incidentToneClass =
    incidentState === "critical"
      ? "border-rose-300 bg-rose-50/90 text-rose-900 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-100"
      : incidentState === "degraded"
        ? "border-amber-300 bg-amber-50/90 text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/35 dark:text-amber-100"
        : "border-emerald-300 bg-emerald-50/90 text-emerald-900 dark:border-emerald-900/70 dark:bg-emerald-950/35 dark:text-emerald-100";
  const incidentBadgeClass =
    incidentState === "critical"
      ? "bg-rose-600 text-white"
      : incidentState === "degraded"
        ? "bg-amber-500 text-amber-950"
        : "bg-emerald-600 text-white";
  const infrastructureConcreteCards = [
    toInfrastructureCard({
      label: "Host CPU load",
      rawValue: latestWidgetValue(cpuWidget),
      unit: typeof cpuWidget?.config?.unit === "string" ? cpuWidget.config.unit : "%",
      helper: "Current host machine CPU usage",
      warningThreshold: 65,
      dangerThreshold: 85,
    }),
    toInfrastructureCard({
      label: "Host memory load",
      rawValue: latestWidgetValue(memoryWidget),
      unit: typeof memoryWidget?.config?.unit === "string" ? memoryWidget.config.unit : "%",
      helper: "Current host RAM usage",
      warningThreshold: 75,
      dangerThreshold: 90,
    }),
    toInfrastructureCard({
      label: "App memory share",
      rawValue: latestWidgetValue(findWidgetByKeywords(["process memory", "app memory share"])),
      unit: "%",
      helper: "Process percent of total host memory",
    }),
    toInfrastructureCard({
      label: "App RSS memory",
      rawValue: latestWidgetValue(findWidgetByKeywords(["rss memory", "app rss"])),
      unit: "MB",
      helper: "Resident set size used by app process",
    }),
    toInfrastructureCard({
      label: "Host disk used",
      rawValue: latestWidgetValue(diskWidget),
      unit: typeof diskWidget?.config?.unit === "string" ? diskWidget.config.unit : "%",
      helper: "Current host disk occupancy",
      warningThreshold: 80,
      dangerThreshold: 92,
    }),
    toInfrastructureCard({
      label: "Network received",
      rawValue: latestWidgetValue(findWidgetByKeywords(["network received"])),
      unit: "MB",
      helper: "Total bytes received by host interfaces",
    }),
    toInfrastructureCard({
      label: "Network sent",
      rawValue: latestWidgetValue(findWidgetByKeywords(["network sent"])),
      unit: "MB",
      helper: "Total bytes sent by host interfaces",
    }),
  ];

  return (
    <>
      {d.errorMessage ? (
        <section
          className="rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100"
          role="status"
        >
          Some dashboard sections may be stale: {d.errorMessage}
        </section>
      ) : null}
      <section className={`rounded-xl border px-4 py-3 shadow-sm ${incidentToneClass}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className={`rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${incidentBadgeClass}`}>
              {incidentState}
            </span>
            <p className="text-sm font-semibold">{incidentSummary}</p>
          </div>
          <p className="text-xs opacity-85">
            Window: last {d.windowMinutes}m · Error rate {(displayErrorRate * 100).toFixed(2)}% · p95{" "}
            {overviewExtended.p95_latency_ms.toFixed(1)} ms
          </p>
        </div>
      </section>
      <section className="grid auto-rows-fr gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {primarySignalCards.map((card) => (
          <div key={card.label}>
            <MetricCard
              label={card.label}
              value={card.value}
              helper={card.helper}
              tone={card.tone}
              tooltip={`Click to drill down: ${card.label}`}
              onClick={() => {
                if (card.label === "Active incidents" || card.label === "Error rate") {
                  pushDiagnosisWithScope({ error_group_sort: "count" }, "#grouped-errors");
                  return;
                }
                if (card.label === "Latency p95") {
                  pushRequestsWithScope({
                    min_latency_ms: Math.max(1, Math.round(overviewExtended.p95_latency_ms)).toString(),
                  });
                  return;
                }
                pushRequestsWithScope();
              }}
            />
          </div>
        ))}
        {secondarySignalCards.map((card) => (
          <div key={card.label}>
            <MetricCard
              label={card.label}
              value={card.value}
              helper={card.helper}
              tone={card.tone}
              tooltip={`Click to drill down: ${card.label}`}
              onClick={() => {
                if (card.label.includes("Errors")) {
                  pushDiagnosisWithScope({ status_class: "5", error_group_sort: "count" }, "#grouped-errors");
                  return;
                }
                if (card.label.includes("Latency")) {
                  pushRequestsWithScope({
                    min_latency_ms: Math.max(1, Math.round(displayAvgLatencyMs)).toString(),
                  });
                  return;
                }
                if (card.label.includes("Apdex")) {
                  pushRequestsWithScope({
                    max_latency_ms: String(apdexThresholdMs.tolerated),
                  });
                  return;
                }
                pushRequestsWithScope();
              }}
            />
          </div>
        ))}
      </section>

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
                      xLabel={
                        typeof widget.config?.x_label === "string" ? widget.config.x_label : "X axis"
                      }
                      yLabel={
                        typeof widget.config?.y_label === "string" ? widget.config.y_label : "Y axis"
                      }
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
      ) : null}

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
          Infrastructure metric coverage
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          These metrics are sourced from SDK dashboard widgets. Add matching widgets to your app to light up missing rows.
        </p>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {infraMetricCoverage.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-slate-50/70 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/70"
            >
              <p className="text-sm text-slate-800 dark:text-neutral-100">{item.label}</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  item.ready
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
                }`}
              >
                {item.ready ? "Ready" : "Missing"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <ChartPanel title="CPU usage" description="Per-instance/container CPU utilization trend.">
          {cpuSeries.values.length || cpuFallbackValues.length ? (
            <TimeSeriesLineChart
              title="CPU"
              labels={cpuSeries.values.length ? cpuSeries.labels : fallbackMinuteLabels}
              values={cpuSeries.values.length ? cpuSeries.values : cpuFallbackValues}
              color="#0ea5e9"
              formatValue={(value) => `${value.toFixed(2)}`}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No CPU widget data yet.</p>
          )}
          {!cpuSeries.values.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using traffic volume proxy until CPU widget data is available.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel title="Memory usage" description="RAM trend over time.">
          {memorySeries.values.length || memoryFallbackValues.length ? (
            <TimeSeriesLineChart
              title="Memory"
              labels={memorySeries.values.length ? memorySeries.labels : fallbackMinuteLabels}
              values={memorySeries.values.length ? memorySeries.values : memoryFallbackValues}
              color="#8b5cf6"
              formatValue={(value) => `${value.toFixed(2)}`}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No memory widget data yet.</p>
          )}
          {!memorySeries.values.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using latency proxy until memory widget data is available.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel title="Disk I/O" description="Read/write operations or throughput over time.">
          {diskSeries.values.length || diskFallbackValues.length ? (
            <TimeSeriesLineChart
              title="Disk I/O"
              labels={diskSeries.values.length ? diskSeries.labels : fallbackMinuteLabels}
              values={diskSeries.values.length ? diskSeries.values : diskFallbackValues}
              color="#f59e0b"
              formatValue={(value) => `${value.toFixed(2)}`}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No disk I/O widget data yet.</p>
          )}
          {!diskSeries.values.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using error-pressure proxy until disk I/O widget data is available.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel title="Network traffic" description="Inbound/outbound traffic trend.">
          {networkSeries.values.length || networkFallbackValues.length ? (
            <TimeSeriesLineChart
              title="Network"
              labels={networkSeries.values.length ? networkSeries.labels : fallbackMinuteLabels}
              values={networkSeries.values.length ? networkSeries.values : networkFallbackValues}
              color="#14b8a6"
              formatValue={(value) => `${value.toFixed(2)}`}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No network widget data yet.</p>
          )}
          {!networkSeries.values.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using request-volume proxy until network widget data is available.
            </p>
          ) : null}
        </ChartPanel>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Infrastructure now</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Concrete host and app load values captured across macOS, Windows, and Linux.
        </p>
        <div className="mt-4 grid auto-rows-fr gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {infrastructureConcreteCards.map((card) => (
            <MetricCard
              key={card.label}
              label={card.label}
              value={card.value}
              helper={card.helper}
              tone={card.tone}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Database query performance" description="Query durations/frequency from DB widgets.">
          <BreakdownBarChart
            items={dbBars.length ? dbBars : dbFallbackBars}
            valueLabel="value"
            emptyMessage="No DB query widget data yet."
          />
          {!dbBars.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using slow-route latency proxy until DB widget data is available.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel title="Cache hit/miss ratio" description="Cache effectiveness from cache widgets.">
          <BreakdownBarChart
            items={cacheBars.length ? cacheBars : cacheFallbackBars}
            valueLabel="value"
            emptyMessage="No cache widget data yet."
          />
          {!cacheBars.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using success/error split proxy until cache widget data is available.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel title="Service dependency map" description="Observed service-to-service edges from dependency widgets.">
          {dependencyEdges.length || dependencyFallbackEdges.length ? (
            <ul className="space-y-2">
              {(dependencyEdges.length ? dependencyEdges : dependencyFallbackEdges).map((edge) => (
                <li
                  key={`${edge.from}->${edge.to}`}
                  className="flex items-center justify-between rounded-md border border-slate-200 px-2.5 py-1.5 text-sm dark:border-neutral-700"
                >
                  <span className="font-mono text-xs text-slate-700 dark:text-neutral-200">
                    {edge.from} -&gt; {edge.to}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
                    {edge.weight.toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">
              No dependency-map widget edges yet (use labels like `serviceA-&gt;serviceB`).
            </p>
          )}
          {!dependencyEdges.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Using service-volume fallback edges until dependency widget data is available.
            </p>
          ) : null}
        </ChartPanel>
      </section>

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
            <DonutChart title="Status classes" items={statusDonutItems} centerLabel="Total" centerValue={String(statusClassTotal)} />
          </ChartPanel>
          <ChartPanel title="Histogram">
            <HistogramChart buckets={showcaseHistogramBuckets} />
          </ChartPanel>
          <ChartPanel title="Scatter plot">
            <ScatterPlotChart
              points={showcaseScatterPoints}
              xLabel="Request volume"
              yLabel="Error rate %"
            />
          </ChartPanel>
          <ChartPanel title="Stacked area">
            <StackedAreaChart labels={statusClassLabels} series={showcaseStackedSeries} />
          </ChartPanel>
        </div>
      </section>

      <GuidedTroubleshootingPanel />

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
          click a bar to open Errors &amp; Diagnosis for that bucket.{" "}
          <Link href={diagnosisBaseHref} className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300">
            Errors &amp; Diagnosis
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
            onRowClick={(label, value) => {
              const factor = label === "p99" ? 1 : label === "p95" ? 1 : 0.8;
              pushRequestsWithScope({
                min_latency_ms: Math.max(1, Math.round(value * factor)).toString(),
              });
            }}
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel
          title="Apdex trend"
          description={`Current score ${overviewExtended.apdex_score.toFixed(3)} (satisfied <=${apdexThresholdMs.satisfied}ms)`}
        >
          {apdexTrendValues.length ? (
            <TimeSeriesLineChart
              title="Apdex %"
              labels={apdexTrendLabels}
              values={apdexTrendValues}
              color="#14b8a6"
              formatValue={(value) => `${value.toFixed(2)}%`}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No request sample available for Apdex trend.</p>
          )}
        </ChartPanel>
        <ChartPanel
          title="Error breakdown"
          description="Error classes grouped by type (timeout, database, validation, network, auth, server)."
        >
          <BreakdownBarChart
            items={errorBreakdownBars}
            valueLabel="errors"
            emptyMessage="No error events in this window."
          />
        </ChartPanel>
        <ChartPanel
          title="Alerts timeline"
          description="When alerts fired during the selected time window."
        >
          {alertTimelineValues.length ? (
            <TimeSeriesLineChart
              title="Alert events"
              labels={alertTimelineLabels}
              values={alertTimelineValues}
              color="#a78bfa"
              formatValue={(value) => value.toFixed(0)}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">
              No alert dispatches recorded in this range.
            </p>
          )}
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel
          title="Response class split"
          description="Donut share of 2xx/3xx/4xx/5xx across the active scope."
        >
          <DonutChart
            title="Responses"
            items={statusDonutItems}
            centerLabel="Total"
            centerValue={String(statusClassTotal)}
            onSliceClick={(item) => {
              const statusClass = item.id.replace("xx", "");
              pushRequestsWithScope({ status_class: statusClass });
            }}
          />
        </ChartPanel>
        <ChartPanel
          title="HTTP method mix"
          description="How request volume is distributed by method."
        >
          <DonutChart
            title="Methods"
            items={methodDonutItems}
            centerLabel="Requests"
            centerValue={String(d.rawItems.length)}
            onSliceClick={(item) => {
              pushRequestsWithScope({ method: item.id });
            }}
          />
        </ChartPanel>
        <ChartPanel
          title="Latency distribution"
          description="Histogram of request latency buckets in current loaded sample."
        >
          <HistogramChart
            buckets={latencyHistogramBuckets}
            onBucketClick={(bucket) => {
              const rangeMap: Record<string, { min?: string; max?: string }> = {
                "<50ms": { max: "50" },
                "50-100ms": { min: "50", max: "100" },
                "100-250ms": { min: "100", max: "250" },
                "250-500ms": { min: "250", max: "500" },
                "500-1000ms": { min: "500", max: "1000" },
                "1s+": { min: "1000" },
              };
              const range = rangeMap[bucket.label] ?? {};
              pushRequestsWithScope({
                ...(range.min ? { min_latency_ms: range.min } : {}),
                ...(range.max ? { max_latency_ms: range.max } : {}),
              });
            }}
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <ChartPanel
          title="Outcome stack over time"
          description="How success, 4xx, and 5xx compose traffic minute-by-minute."
        >
          <StackedAreaChart
            labels={statusClassLabels}
            series={outcomeStackedSeries}
            onPointClick={(index, _label, values) => {
              const bucket = d.sparklineSeries[index];
              const dominant =
                values.server >= values.client && values.server > 0
                  ? "5"
                  : values.client > 0
                    ? "4"
                    : "ALL";
              const params: Record<string, string> = {};
              if (dominant !== "ALL") {
                params.status_class = dominant;
              }
              if (bucket?.minute) {
                const from = new Date(bucket.minute);
                const to = new Date(from.getTime() + 60_000);
                params.from_timestamp = from.toISOString();
                params.to_timestamp = to.toISOString();
              }
              pushRequestsWithScope(params);
            }}
          />
        </ChartPanel>
        <ChartPanel
          title="Route risk map"
          description="Each dot is a route: x=request volume, y=error rate (%)."
        >
          <ScatterPlotChart
            points={routeRiskScatter}
            xLabel="Higher request volume"
            yLabel="Higher error rate"
            onPointClick={(point) => {
              pushRequestsWithScope({ path_contains: point.id });
            }}
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <ChartPanel
          title="Route x status heatmap"
          description="Top routes crossed with response classes to spot concentrated failures."
          actionHref={diagnosisGroupedHref}
          actionLabel="Open grouped errors"
        >
          <HeatmapGrid
            cells={routeStatusHeatmap.cells}
            xLabels={routeStatusHeatmap.xLabels}
            yLabels={routeStatusHeatmap.yLabels}
            onCellClick={(cell) => {
              const statusClass = cell.x.replace("xx", "");
              pushRequestsWithScope({
                path_contains: cell.y,
                status_class: statusClass,
              });
            }}
          />
        </ChartPanel>
        <ChartPanel
          title="Reliability scorecard"
          description="Quick reliability split derived from status classes."
        >
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-3">
              <p className="text-[11px] uppercase tracking-wide text-emerald-300">Success rate</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-emerald-100">
                {successRatePct.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3">
              <p className="text-[11px] uppercase tracking-wide text-amber-300">4xx rate</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-amber-100">
                {clientErrorRatePct.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg border border-rose-500/25 bg-rose-500/10 p-3">
              <p className="text-[11px] uppercase tracking-wide text-rose-300">5xx rate</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-rose-100">
                {serverErrorRatePct.toFixed(2)}%
              </p>
            </div>
          </div>
        </ChartPanel>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Metrics dictionary</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Expand for complete metrics and backend-derived values.
        </p>
        <div className="mt-4 space-y-3">
          {metricsByGroup.map((group, index) => (
            <details
              key={group.title}
              open={index === 0}
              className="rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/70"
            >
              <summary className="cursor-pointer list-none text-sm font-semibold text-slate-800 dark:text-neutral-100">
                {group.title}
              </summary>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {group.rows.map((row) => (
                  <div key={row.label} className="rounded-lg bg-white/80 px-2.5 py-2 dark:bg-neutral-900/70">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                      {row.label}
                    </p>
                    <p className="mt-1 text-base font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
                      {row.value}
                    </p>
                    {row.helper ? (
                      <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">{row.helper}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
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
              Errors &amp; Diagnosis
            </Link>
            .
          </p>
        </section>
      ) : null}

      <section className={`grid gap-4 ${denseInsightLayout ? "lg:grid-cols-3" : "lg:grid-cols-2"}`}>
        <ChartPanel title="Top failing routes" actionHref={diagnosisBaseHref} actionLabel="Full diagnosis">
          {d.topFailingRoutes.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-neutral-300">
              No 5xx failures in the current request sample.
            </p>
          ) : (
            <ul className="space-y-2">
              {d.topFailingRoutes.map(([path, count]) => (
                <li key={path} className="flex items-start justify-between gap-3 text-sm">
                  <button
                    type="button"
                    title={`Open requests for ${path}`}
                    onClick={() => pushRequestsWithScope({ path_contains: path, status_class: "5" })}
                    className="min-w-0 truncate font-mono text-left text-xs text-slate-800 underline-offset-2 hover:underline dark:text-neutral-100"
                  >
                    {path}
                  </button>
                  <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-900/50 dark:text-rose-300">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </ChartPanel>

        <ChartPanel
          title="Recent errors"
          actionHref={diagnosisGroupedHref}
          actionLabel="Grouped list"
        >
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

        {denseInsightLayout ? (
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
            onItemClick={(item) => {
              pushRequestsWithScope({ services: item.key });
            }}
            />
          </ChartPanel>
        ) : null}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <ChartPanel
          title="Responses by class"
          description="Per-minute response classes across the active scope."
          actionHref={diagnosisBaseHref}
          actionLabel="Open diagnosis"
        >
          <MultiSeriesLineChart
            labels={statusClassLabels}
            series={statusClassSeries}
            onPointClick={(index, _label, values) => {
              const bucket = d.sparklineSeries[index];
              const statusPairs: Array<[string, number]> = [
                ["5", values["5xx"] ?? 0],
                ["4", values["4xx"] ?? 0],
                ["3", values["3xx"] ?? 0],
                ["2", values["2xx"] ?? 0],
              ];
              statusPairs.sort((a, b) => b[1] - a[1]);
              const topStatusClass = statusPairs[0]?.[0] ?? "ALL";
              const params: Record<string, string> = { status_class: topStatusClass };
              if (bucket?.minute) {
                const from = new Date(bucket.minute);
                const to = new Date(from.getTime() + 60_000);
                params.from_timestamp = from.toISOString();
                params.to_timestamp = to.toISOString();
              }
              pushRequestsWithScope(params);
            }}
          />
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
            onItemClick={(item) => {
              pushRequestsWithScope({ path_contains: item.key });
            }}
          />
        </ChartPanel>
      </section>
    </>
  );
}
