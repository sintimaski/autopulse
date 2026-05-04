import type { ScatterPlotPoint, StackedAreaSeries } from "../charts";

import type { DashboardWidgetDefinition, DashboardWidgetPoint } from "../dashboardTypes";

const MOCK_DEFINITIONS: DashboardWidgetDefinition[] = [
  {
    widget_id: "showroom_card_p95",
    type: "card",
    title: "p95 latency",
    description: "Synthetic KPI card",
    order: 0,
    config: { unit: "ms", tone: "warning" },
  },
  {
    widget_id: "showroom_line_rpm",
    type: "line",
    title: "Requests per minute",
    description: "Synthetic line series",
    order: 1,
    config: { color: "#38bdf8" },
  },
  {
    widget_id: "showroom_bar_routes",
    type: "bar",
    title: "Top routes (volume)",
    description: "Synthetic labeled bars",
    order: 2,
    config: {},
  },
  {
    widget_id: "showroom_donut_status",
    type: "donut",
    title: "HTTP status mix",
    description: "Synthetic donut slices",
    order: 3,
    config: {},
  },
  {
    widget_id: "showroom_hist_latency",
    type: "histogram",
    title: "Latency distribution",
    description: "Synthetic histogram buckets",
    order: 4,
    config: {},
  },
  {
    widget_id: "showroom_scatter_services",
    type: "scatter",
    title: "Load vs error rate",
    description: "Synthetic scatter (x encoded in point label)",
    order: 5,
    config: { x_label: "RPM", y_label: "Errors / min" },
  },
  {
    widget_id: "showroom_stack_components",
    type: "stacked_area",
    title: "Traffic by component",
    description: "Synthetic stacked area",
    order: 6,
    config: {},
  },
];

const ROUTE_LABELS = ["/api/users", "/api/orders", "/health", "/metrics", "/webhooks/stripe"] as const;
const HIST_LABELS = ["<50ms", "50-100ms", "100-250ms", "250-500ms", "500-1000ms", "1s+"] as const;
const SCATTER_LABELS = [
  "42|API",
  "28|Workers",
  "55|Cron",
  "18|Webhooks",
  "33|Auth",
  "12|Cache",
] as const;
const STACK_SERIES = ["api", "workers", "cron"] as const;

function isoMinuteOffset(fromMs: number, minutesAgo: number): string {
  return new Date(fromMs - minutesAgo * 60_000).toISOString();
}

/**
 * Deterministic pseudo-random in [0, 1) from tick and salt (stable per tick).
 */
function jitter(tick: number, salt: number): number {
  const x = Math.sin(tick * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/**
 * Build synthetic widget points for showroom demos. `tick` increments on a timer so values drift like live metrics.
 */
export function buildWidgetsShowroomMockPoints(tick: number): DashboardWidgetPoint[] {
  const now = Date.now();
  const tsLatest = new Date(now).toISOString();
  const points: DashboardWidgetPoint[] = [];

  const p95 = 62 + 28 * Math.sin(tick * 0.31) + 8 * jitter(tick, 1);
  points.push({
    widget_id: "showroom_card_p95",
    timestamp: tsLatest,
    label: null,
    value: Math.max(12, p95),
  });

  const lineBuckets = 20;
  for (let i = 0; i < lineBuckets; i += 1) {
    const t = isoMinuteOffset(now, lineBuckets - 1 - i);
    const base = 120 + 55 * Math.sin(tick * 0.22 + i * 0.28) + 20 * jitter(tick, i + 10);
    points.push({
      widget_id: "showroom_line_rpm",
      timestamp: t,
      label: null,
      value: Math.max(10, base),
    });
  }

  for (let r = 0; r < ROUTE_LABELS.length; r += 1) {
    const label = ROUTE_LABELS[r];
    const v = 40 + r * 22 + 18 * Math.sin(tick * 0.19 + r) + 12 * jitter(tick, 20 + r);
    points.push({
      widget_id: "showroom_bar_routes",
      timestamp: tsLatest,
      label,
      value: Math.max(5, v),
    });
  }

  const donutBase = [820, 95, 64, 12] as const;
  const statusLabels = ["2xx", "3xx", "4xx", "5xx"] as const;
  for (let s = 0; s < donutBase.length; s += 1) {
    const drift = 1 + 0.08 * Math.sin(tick * 0.27 + s) + 0.04 * jitter(tick, 40 + s);
    points.push({
      widget_id: "showroom_donut_status",
      timestamp: tsLatest,
      label: statusLabels[s],
      value: Math.max(1, donutBase[s] * drift),
    });
  }

  for (let h = 0; h < HIST_LABELS.length; h += 1) {
    const center = h === 0 ? 120 : h === 1 ? 200 : h === 2 ? 160 : h === 3 ? 90 : h === 4 ? 40 : 25;
    const v = center + 35 * Math.sin(tick * 0.24 + h * 0.5) + 20 * jitter(tick, 50 + h);
    points.push({
      widget_id: "showroom_hist_latency",
      timestamp: tsLatest,
      label: HIST_LABELS[h],
      value: Math.max(0, v),
    });
  }

  for (let c = 0; c < SCATTER_LABELS.length; c += 1) {
    const [xPart] = SCATTER_LABELS[c].split("|", 2);
    const x0 = Number(xPart) || 1;
    const y = 1.5 + 6 * Math.sin(tick * 0.18 + c * 0.7) ** 2 + 2 * jitter(tick, 60 + c);
    points.push({
      widget_id: "showroom_scatter_services",
      timestamp: tsLatest,
      label: SCATTER_LABELS[c],
      value: Math.max(0.1, y + x0 * 0.04),
    });
  }

  const stackMinutes = 14;
  for (let m = 0; m < stackMinutes; m += 1) {
    const t = isoMinuteOffset(now, stackMinutes - 1 - m);
    for (let s = 0; s < STACK_SERIES.length; s += 1) {
      const series = STACK_SERIES[s];
      const layer =
        series === "api"
          ? 55 + 25 * Math.sin(tick * 0.21 + m * 0.25)
          : series === "workers"
            ? 32 + 18 * Math.cos(tick * 0.17 + m * 0.31)
            : 12 + 10 * Math.sin(tick * 0.35 + m * 0.4);
      points.push({
        widget_id: "showroom_stack_components",
        timestamp: t,
        label: series,
        value: Math.max(2, layer + 8 * jitter(tick, 70 + m * 4 + s)),
      });
    }
  }

  return points;
}

export function getWidgetsShowroomMockDefinitions(): DashboardWidgetDefinition[] {
  return MOCK_DEFINITIONS;
}

/** Same six panels as the backend widget gallery chart showcase; values move with `tick`. */
export type ShowroomChartShowcaseModel = {
  lineLabels: string[];
  lineValues: number[];
  barItems: { key: string; value: number }[];
  donutItems: { id: string; label: string; value: number; color: string }[];
  donutCenterValue: string;
  histogramBuckets: { label: string; count: number }[];
  scatterPoints: ScatterPlotPoint[];
  stackedLabels: string[];
  stackedSeries: StackedAreaSeries[];
};

const SHOWCASE_ROUTE_KEYS = [
  "/api/users",
  "/api/orders",
  "/health",
  "/metrics",
  "/webhooks/stripe",
  "/api/graphql",
  "/internal/jobs",
  "/v1/checkout",
] as const;

const HISTOGRAM_RANGE_LABELS = ["<50ms", "50-100ms", "100-250ms", "250-500ms", "500-1000ms", "1s+"] as const;

export function buildShowroomChartShowcaseMock(tick: number): ShowroomChartShowcaseModel {
  const bucketCount = 24;
  const now = Date.now();
  type StatusBucket = {
    minute: string;
    count_2xx: number;
    count_3xx: number;
    count_4xx: number;
    count_5xx: number;
    error_count: number;
  };
  const buckets: StatusBucket[] = Array.from({ length: bucketCount }, (_, i) => {
    const minute = new Date(now - (bucketCount - 1 - i) * 60_000).toISOString();
    const base = 60 + 35 * Math.sin(tick * 0.18 + i * 0.22);
    const count2xx = Math.max(20, Math.round(base + 20 * jitter(tick, 100 + i)));
    const count3xx = Math.max(2, Math.round(8 + 6 * Math.sin(tick * 0.25 + i)));
    const count4xx = Math.max(1, Math.round(5 + 4 * jitter(tick, 200 + i)));
    const count5xx = Math.max(0, Math.round(2 + 3 * jitter(tick, 300 + i)));
    const error_count = Math.max(
      0,
      Math.round(count4xx * 0.4 + count5xx + 3 * Math.sin(tick * 0.3 + i) + 4 * jitter(tick, 350 + i)),
    );
    return { minute, count_2xx: count2xx, count_3xx: count3xx, count_4xx: count4xx, count_5xx: count5xx, error_count };
  });

  const lineLabels = buckets.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const lineValues = buckets.map((bucket) => bucket.error_count);

  const barItems = [...SHOWCASE_ROUTE_KEYS]
    .map((key, index) => ({
      key,
      value: Math.max(
        5,
        Math.round(40 + index * 18 + 25 * Math.sin(tick * 0.2 + index * 0.4) + 15 * jitter(tick, 400 + index)),
      ),
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  const total2xx = buckets.reduce((sum, bucket) => sum + bucket.count_2xx, 0);
  const total3xx = buckets.reduce((sum, bucket) => sum + bucket.count_3xx, 0);
  const total4xx = buckets.reduce((sum, bucket) => sum + bucket.count_4xx, 0);
  const total5xx = buckets.reduce((sum, bucket) => sum + bucket.count_5xx, 0);
  const statusClassTotal = total2xx + total3xx + total4xx + total5xx;
  const donutItems = [
    { id: "2xx", label: "2xx", value: total2xx, color: "#34d399" },
    { id: "3xx", label: "3xx", value: total3xx, color: "#38bdf8" },
    { id: "4xx", label: "4xx", value: total4xx, color: "#f59e0b" },
    { id: "5xx", label: "5xx", value: total5xx, color: "#f43f5e" },
  ];

  const histogramCenters = [140, 220, 170, 85, 45, 28];
  const histogramBuckets = HISTOGRAM_RANGE_LABELS.map((label, index) => ({
    label,
    count: Math.max(
      0,
      Math.round(
        histogramCenters[index] +
          40 * Math.sin(tick * 0.23 + index * 0.55) +
          25 * jitter(tick, 500 + index),
      ),
    ),
  }));

  const scatterPoints: ScatterPlotPoint[] = SHOWCASE_ROUTE_KEYS.slice(0, 8).map((key, index) => {
    const request_count = Math.max(
      8,
      Math.round(25 + index * 14 + 20 * Math.sin(tick * 0.17 + index) + 12 * jitter(tick, 600 + index)),
    );
    const errorRatePct = Math.min(
      22,
      Math.max(0, 1.2 + 8 * Math.sin(tick * 0.19 + index * 0.6) ** 2 + 3 * jitter(tick, 700 + index)),
    );
    return {
      id: key,
      x: request_count,
      y: errorRatePct,
      label: `${key} · ${request_count} req · ${errorRatePct.toFixed(2)}% err`,
      tone: errorRatePct >= 10 ? "danger" : errorRatePct >= 3 ? "warning" : "neutral",
    };
  });

  const stackedSeries: StackedAreaSeries[] = [
    {
      id: "success",
      label: "Successful (2xx+3xx)",
      color: "#34d399",
      values: buckets.map((bucket) => bucket.count_2xx + bucket.count_3xx),
    },
    {
      id: "client",
      label: "Client errors (4xx)",
      color: "#f59e0b",
      values: buckets.map((bucket) => bucket.count_4xx),
    },
    {
      id: "server",
      label: "Server errors (5xx)",
      color: "#f43f5e",
      values: buckets.map((bucket) => bucket.count_5xx),
    },
  ];

  return {
    lineLabels,
    lineValues,
    barItems,
    donutItems,
    donutCenterValue: String(statusClassTotal),
    histogramBuckets,
    scatterPoints,
    stackedLabels: lineLabels,
    stackedSeries: stackedSeries,
  };
}
