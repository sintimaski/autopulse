"use client";

import { useMemo, useState } from "react";

import { trimSeriesToLastMinutes } from "../../../utils/dashboardData";
import {
  BreakdownBarChart,
  ChartPanel,
  StackedAreaChart,
  type StackedAreaSeries,
} from "../charts";
import { MetricCard } from "../MetricCard";
import type {
  DashboardWidgetDefinition,
  DashboardWidgetPoint,
  DashboardWidgetType,
  OverviewBucket,
  OverviewExtendedResponse,
  DashboardWidgetsResponse,
} from "../dashboardTypes";

type Props = {
  sparklineSeries: OverviewBucket[];
  overviewExtended: OverviewExtendedResponse;
  dashboardWidgets: DashboardWidgetsResponse | null;
};

/** Prefer UTC for zone-less API timestamps so comparisons match bucket/point ranges. */
function parseDashboardInstantMs(raw: string): number {
  const t = raw.trim();
  if (!t) return NaN;
  if (/z$|[+-]\d{2}:?\d{2}$/i.test(t)) {
    return Date.parse(t);
  }
  return Date.parse(`${t}Z`);
}

const HOST_RESOURCES_CHART_WINDOW_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 0, label: "Full loaded range" },
  { value: 15, label: "Last 15m" },
  { value: 30, label: "Last 30m" },
  { value: 60, label: "Last 60m" },
  { value: 120, label: "Last 2h" },
  { value: 240, label: "Last 4h" },
  { value: 480, label: "Last 8h" },
  { value: 1440, label: "Last 24h" },
];

/** Series used by Host resources stacked chart — pulled back into the clipped set when time bounds drop them. */
const HOST_RESOURCES_CHART_WIDGET_IDS: readonly string[] = [
  "infra_host_cpu_percent",
  "infra_process_cpu_percent",
  "infra_host_memory_percent",
  "infra_process_memory_percent",
  "infra_disk_used_percent",
  "infra_network_received_mb",
  "infra_network_sent_mb",
];

const WIDGET_DEF_TYPES = new Set<DashboardWidgetType>([
  "card",
  "line",
  "bar",
  "donut",
  "histogram",
  "scatter",
  "stacked_area",
]);

/** Cache / proxies may omit `type` and send ORM-shaped `widget_type` instead. */
function normalizeIncomingWidgetDefinitions(
  defs: DashboardWidgetsResponse["definitions"] | undefined,
): DashboardWidgetDefinition[] {
  const list = defs ?? [];
  const result: DashboardWidgetDefinition[] = [];
  for (const item of list) {
    const o = item as unknown as Record<string, unknown>;
    const wtypeRaw = o.type ?? o.widget_type;
    const id = typeof o.widget_id === "string" ? o.widget_id.trim() : "";
    const title = typeof o.title === "string" ? o.title : "";
    if (!id || typeof wtypeRaw !== "string") {
      continue;
    }
    if (!WIDGET_DEF_TYPES.has(wtypeRaw as DashboardWidgetType)) {
      continue;
    }
    const wtype = wtypeRaw as DashboardWidgetType;
    const order = typeof o.order === "number" ? o.order : Number(o.display_order ?? 0) || 0;
    const cfg = o.config;
    const config: DashboardWidgetDefinition["config"] =
      typeof cfg === "object" && cfg !== null && !Array.isArray(cfg)
        ? (cfg as DashboardWidgetDefinition["config"])
        : {};
    result.push({
      widget_id: id,
      type: wtype,
      title,
      description: typeof o.description === "string" ? o.description : null,
      order,
      config,
    });
  }
  return result;
}

function mergeMissingHostResourceWidgetPoints(
  filtered: DashboardWidgetPoint[],
  raw: DashboardWidgetPoint[],
): DashboardWidgetPoint[] {
  let out = [...filtered];
  for (const wid of HOST_RESOURCES_CHART_WIDGET_IDS) {
    if (out.some((p) => p.widget_id === wid)) {
      continue;
    }
    const salvage = raw.filter((p) => p.widget_id === wid);
    if (!salvage.length) {
      continue;
    }
    out = out.concat(salvage);
  }
  out.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  return out;
}

function infraLineStub(widgetId: string): DashboardWidgetDefinition {
  return {
    widget_id: widgetId,
    type: "line",
    title: widgetId,
    description: null,
    order: 0,
    config: {},
  };
}

function filterWidgetPointsForTimeSpan(
  points: DashboardWidgetPoint[],
  bounds: { fromTimestamp: string; toTimestamp: string },
  lastMinutes: number,
): DashboardWidgetPoint[] {
  const toMs = parseDashboardInstantMs(bounds.toTimestamp);
  if (!Number.isFinite(toMs)) {
    return points;
  }
  const fromBoundMs = parseDashboardInstantMs(bounds.fromTimestamp);
  const startMs =
    lastMinutes > 0
      ? Math.max(Number.isFinite(fromBoundMs) ? fromBoundMs : -Infinity, toMs - lastMinutes * 60 * 1000)
      : Number.isFinite(fromBoundMs)
        ? fromBoundMs
        : -Infinity;
  return points.filter((p) => {
    const t = parseDashboardInstantMs(p.timestamp);
    if (!Number.isFinite(t)) return false;
    return t >= startMs && t <= toMs;
  });
}

function trimSparklineForHostChart(
  series: OverviewBucket[],
  bounds: { fromTimestamp: string; toTimestamp: string },
  lastMinutes: number,
): OverviewBucket[] {
  const sorted = [...series].sort((a, b) => a.minute.localeCompare(b.minute));
  if (lastMinutes > 0) {
    return trimSeriesToLastMinutes(sorted, lastMinutes);
  }
  const fromMs = parseDashboardInstantMs(bounds.fromTimestamp);
  const toMs = parseDashboardInstantMs(bounds.toTimestamp);
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) {
    return sorted;
  }
  return sorted.filter((bucket) => {
    const t = parseDashboardInstantMs(bucket.minute);
    return Number.isFinite(t) && t >= fromMs && t <= toMs;
  });
}

function trimWidgetPointsLastMinutes(
  points: DashboardWidgetPoint[],
  lastMinutes: number,
): DashboardWidgetPoint[] {
  if (lastMinutes <= 0 || !points.length) {
    return points;
  }
  const sorted = [...points].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const lastTs = parseDashboardInstantMs(sorted[sorted.length - 1]?.timestamp ?? "");
  if (!Number.isFinite(lastTs)) {
    return sorted;
  }
  const cutoff = lastTs - lastMinutes * 60 * 1000;
  return sorted.filter((p) => {
    const t = parseDashboardInstantMs(p.timestamp);
    return Number.isFinite(t) && t >= cutoff;
  });
}

function widgetPointsToTotalsTimelineFromMap(
  widget: DashboardWidgetDefinition | undefined,
  pointsByWidget: Map<string, DashboardWidgetPoint[]>,
): { timestamps: string[]; values: number[] } | null {
  if (!widget) {
    return null;
  }
  const points = [...(pointsByWidget.get(widget.widget_id) ?? [])].sort((a, b) =>
    a.timestamp.localeCompare(b.timestamp),
  );
  if (!points.length) {
    return null;
  }
  const byTime = new Map<string, number>();
  for (const p of points) {
    const t = p.timestamp;
    byTime.set(t, (byTime.get(t) ?? 0) + Math.max(0, Number(p.value)));
  }
  const timestamps = [...byTime.keys()].sort();
  const values = timestamps.map((t) => Math.max(0, byTime.get(t) ?? 0));
  return { timestamps, values };
}

function formatMegabytesAdaptive(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const v = Math.max(0, value);
  if (v < 1024) {
    return `${v.toFixed(1)} MB`;
  }
  const gb = v / 1024;
  if (gb < 1024) {
    return `${gb.toFixed(2)} GB`;
  }
  const tb = gb / 1024;
  if (tb < 1024) {
    return `${tb.toFixed(2)} TB`;
  }
  return `${(tb / 1024).toFixed(2)} PB`;
}

function containsKeyword(corpus: string, keyword: string): boolean {
  const normalizedCorpus = corpus.toLowerCase();
  const normalizedKeyword = keyword.toLowerCase().trim();
  if (!normalizedKeyword) {
    return false;
  }
  if (normalizedKeyword.includes(" ") || normalizedKeyword.includes("/") || normalizedKeyword.includes("-")) {
    return normalizedCorpus.includes(normalizedKeyword);
  }
  const escaped = normalizedKeyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`\\b${escaped}\\b`, "i");
  return re.test(normalizedCorpus);
}

export function DashboardInfrastructureSection({
  sparklineSeries,
  overviewExtended,
  dashboardWidgets,
}: Props) {
  const routeBreakdownByVolume = [...overviewExtended.route_breakdown]
    .sort((a, b) => b.request_count - a.request_count)
    .slice(0, 10);
  const serviceBreakdownByVolume = [...overviewExtended.service_breakdown]
    .sort((a, b) => b.request_count - a.request_count)
    .slice(0, 10);

  const total2xx = sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_2xx || 0), 0);
  const total3xx = sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_3xx || 0), 0);
  const total4xx = sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_4xx || 0), 0);
  const total5xx = sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.count_5xx || 0), 0);

  const widgetDefinitions = normalizeIncomingWidgetDefinitions(dashboardWidgets?.definitions);
  const widgetPointsById = new Map<string, DashboardWidgetPoint[]>();
  for (const point of dashboardWidgets?.points ?? []) {
    const existing = widgetPointsById.get(point.widget_id) ?? [];
    existing.push(point);
    widgetPointsById.set(point.widget_id, existing);
  }

  const [hostChartWindowMinutes, setHostChartWindowMinutes] = useState(0);

  /** Clip chart data to widget API window (aligned with embedded points); fall back to overview when missing. */
  const overviewFrom = overviewExtended.from_timestamp;
  const overviewTo = overviewExtended.to_timestamp;
  const chartClipFrom = dashboardWidgets?.from_timestamp || overviewFrom;
  const chartClipTo = dashboardWidgets?.to_timestamp || overviewTo;

  const hostChartFilteredPoints = useMemo(() => {
    const raw = dashboardWidgets?.points ?? [];
    const bounds = { fromTimestamp: chartClipFrom, toTimestamp: chartClipTo };
    const clipped = filterWidgetPointsForTimeSpan(raw, bounds, hostChartWindowMinutes);
    let next = mergeMissingHostResourceWidgetPoints(clipped, raw);
    if (next.length > 0) {
      return next;
    }
    if (raw.length === 0) {
      return raw;
    }
    if (hostChartWindowMinutes <= 0) {
      return mergeMissingHostResourceWidgetPoints(raw, raw);
    }
    const rolling = trimWidgetPointsLastMinutes(raw, hostChartWindowMinutes);
    const rescued = mergeMissingHostResourceWidgetPoints(rolling, raw);
    return rescued.length > 0 ? rescued : mergeMissingHostResourceWidgetPoints(raw, raw);
  }, [dashboardWidgets?.points, chartClipFrom, chartClipTo, hostChartWindowMinutes]);

  const hostChartPointsByWidget = useMemo(() => {
    const grouped = new Map<string, DashboardWidgetPoint[]>();
    for (const p of hostChartFilteredPoints) {
      const bucket = grouped.get(p.widget_id) ?? [];
      bucket.push(p);
      grouped.set(p.widget_id, bucket);
    }
    return grouped;
  }, [hostChartFilteredPoints]);

  const sparklineForHostChart = useMemo(
    () =>
      trimSparklineForHostChart(
        sparklineSeries,
        { fromTimestamp: chartClipFrom, toTimestamp: chartClipTo },
        hostChartWindowMinutes,
      ),
    [sparklineSeries, chartClipFrom, chartClipTo, hostChartWindowMinutes],
  );

  const findWidgetByKeywords = (keywords: string[]) =>
    widgetDefinitions.find((widget) => {
      const corpus = `${widget.widget_id} ${widget.title} ${widget.description ?? ""}`.toLowerCase();
      return keywords.some((keyword) => containsKeyword(corpus, keyword));
    });

  const definitionOrStubIfPoints = (widgetId: string): DashboardWidgetDefinition | undefined =>
    widgetDefinitions.find((w) => w.widget_id === widgetId) ??
    (widgetPointsById.has(widgetId) ? infraLineStub(widgetId) : undefined);

  const formatAxisTime = (iso: string) =>
    new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  /** When infrastructure widgets are absent, show request mix by status class (honest traffic proxy). */
  const sparklineToStatusStack = (buckets: OverviewBucket[]): { labels: string[]; series: StackedAreaSeries[] } => ({
    labels: buckets.map((b) => formatAxisTime(b.minute)),
    series: [
      {
        id: "2xx",
        label: "2xx",
        color: "#10b981",
        values: buckets.map((b) => Number(b.count_2xx || 0)),
      },
      {
        id: "3xx",
        label: "3xx",
        color: "#0ea5e9",
        values: buckets.map((b) => Number(b.count_3xx || 0)),
      },
      {
        id: "4xx",
        label: "4xx",
        color: "#f59e0b",
        values: buckets.map((b) => Number(b.count_4xx || 0)),
      },
      {
        id: "5xx",
        label: "5xx",
        color: "#f43f5e",
        values: buckets.map((b) => Number(b.count_5xx || 0)),
      },
    ],
  });

  const INFRA_COMPOSE = {
    cpu: { label: "CPU", color: "#0ea5e9" },
    memory: { label: "Memory", color: "#8b5cf6" },
    disk: { label: "Disk / I/O", color: "#f59e0b" },
    network: { label: "Network", color: "#14b8a6" },
  } as const;

  const formatMetricValue = (value: number, unit: string | null | undefined) => {
    const normalized = (unit ?? "").toLowerCase();
    if (normalized === "%" || normalized === "percent") {
      return `${value.toFixed(1)}%`;
    }
    if (normalized === "mb") {
      return formatMegabytesAdaptive(value);
    }
    if (normalized === "gb") {
      return formatMegabytesAdaptive(value * 1024);
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
    const latest = points.reduce((winner, point) => (winner.timestamp > point.timestamp ? winner : point));
    return Number(latest.value || 0);
  };

  const toInfrastructureCard = ({
    label,
    rawValue,
    unit,
    helper,
    warningThreshold,
    dangerThreshold,
    formatValue,
  }: {
    label: string;
    rawValue: number | null;
    unit?: string;
    helper: string;
    warningThreshold?: number;
    dangerThreshold?: number;
    /** When set, raw values are formatted with this (e.g. host network counters always in MB from the agent). */
    formatValue?: (value: number) => string;
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
      value: formatValue ? formatValue(rawValue) : formatMetricValue(rawValue, unit),
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

  const cpuWidget =
    definitionOrStubIfPoints("infra_host_cpu_percent") ??
    definitionOrStubIfPoints("infra_process_cpu_percent") ??
    findWidgetByKeywords(["cpu"]);
  const memoryWidget =
    definitionOrStubIfPoints("infra_host_memory_percent") ?? findWidgetByKeywords(["memory", "ram"]);
  const diskWidget =
    definitionOrStubIfPoints("infra_disk_used_percent") ?? findWidgetByKeywords(["disk", "i/o", "io"]);
  const networkWidget =
    definitionOrStubIfPoints("infra_network_received_mb") ??
    definitionOrStubIfPoints("infra_network_sent_mb") ??
    findWidgetByKeywords(["network", "bandwidth", "bytes in", "bytes out"]);
  const processCpuWidget =
    definitionOrStubIfPoints("infra_process_cpu_percent") ?? findWidgetByKeywords(["app cpu"]);
  const diskIoReadWidget =
    definitionOrStubIfPoints("infra_disk_io_read_mb") ?? findWidgetByKeywords(["disk i/o read", "disk io read"]);
  const dbWidget = findWidgetByKeywords(["db", "database", "query", "sql"]);
  const cacheWidget = findWidgetByKeywords(["cache", "hit", "miss", "redis"]);

  const statusClassFallbackStack = sparklineToStatusStack(sparklineForHostChart);

  const infraCpuTimeline = widgetPointsToTotalsTimelineFromMap(cpuWidget, hostChartPointsByWidget);
  const infraMemoryTimeline = widgetPointsToTotalsTimelineFromMap(memoryWidget, hostChartPointsByWidget);
  const infraDiskTimeline = widgetPointsToTotalsTimelineFromMap(diskWidget, hostChartPointsByWidget);
  const infraNetworkTimeline = widgetPointsToTotalsTimelineFromMap(networkWidget, hostChartPointsByWidget);

  type InfraComposeKey = keyof typeof INFRA_COMPOSE;

  const hasInfraSignals =
    widgetDefinitions.some((w) => w.widget_id.startsWith("infra_")) ||
    [...widgetPointsById.keys()].some((id) => id.startsWith("infra_"));

  const infrastructureCompositionChart = (() => {
    const timelines: Record<InfraComposeKey, { timestamps: string[]; values: number[] } | null> = {
      cpu: infraCpuTimeline,
      memory: infraMemoryTimeline,
      disk: infraDiskTimeline,
      network: infraNetworkTimeline,
    };
    const activeKeys = (Object.keys(INFRA_COMPOSE) as InfraComposeKey[]).filter((k) => timelines[k]);

    if (!activeKeys.length) {
      return { labels: [] as string[], series: [] as StackedAreaSeries[] };
    }

    const allTs = new Set<string>();
    for (const key of activeKeys) {
      const tl = timelines[key];
      if (tl) {
        for (const t of tl.timestamps) {
          allTs.add(t);
        }
      }
    }
    const sortedTs = [...allTs].sort();
    const labels = sortedTs.map((t) => formatAxisTime(t));

    const columns: Record<InfraComposeKey, number[]> = {
      cpu: [],
      memory: [],
      disk: [],
      network: [],
    };

    const columnAligned = (tl: { timestamps: string[]; values: number[] } | null) => {
      if (!tl) {
        return sortedTs.map(() => 0);
      }
      const map = new Map(tl.timestamps.map((stamp, idx) => [stamp, tl.values[idx] ?? 0]));
      return sortedTs.map((stamp) => Math.max(0, map.get(stamp) ?? 0));
    };

    columns.cpu = columnAligned(timelines.cpu);
    columns.memory = columnAligned(timelines.memory);
    columns.disk = columnAligned(timelines.disk);
    columns.network = columnAligned(timelines.network);

    const maxByKey = activeKeys.reduce<Record<InfraComposeKey, number>>(
      (acc, key) => {
        const peak = Math.max(1e-9, ...columns[key].map((v) => Math.max(0, v)));
        acc[key] = peak;
        return acc;
      },
      { cpu: 1e-9, memory: 1e-9, disk: 1e-9, network: 1e-9 },
    );

    const unitCpu = typeof cpuWidget?.config?.unit === "string" ? cpuWidget.config.unit : "%";
    const unitMemory = typeof memoryWidget?.config?.unit === "string" ? memoryWidget.config.unit : "%";
    const unitDisk = typeof diskWidget?.config?.unit === "string" ? diskWidget.config.unit : "%";
    const formatters: Record<InfraComposeKey, (v: number) => string> = {
      cpu: (v) => formatMetricValue(v, unitCpu),
      memory: (v) => formatMetricValue(v, unitMemory),
      disk: (v) => formatMetricValue(v, unitDisk),
      network: (v) => formatMegabytesAdaptive(v),
    };

    const normalized = {} as Record<InfraComposeKey, number[]>;
    for (const key of activeKeys) {
      const cap = maxByKey[key];
      normalized[key] = columns[key].map((v) => Math.max(0, v) / cap);
    }

    const series: StackedAreaSeries[] = activeKeys.map((key) => {
      const { label, color } = INFRA_COMPOSE[key];
      const formatter = formatters[key];
      const tooltipRawValues = columns[key];

      const values = sortedTs.map((_, idx) => {
        let denom = 0;
        for (const k of activeKeys) {
          denom += normalized[k][idx] ?? 0;
        }
        const numer = normalized[key][idx] ?? 0;
        return denom > 0 ? (numer / denom) * 100 : 0;
      });

      return {
        id: key,
        label,
        color,
        values,
        tooltipRawValues,
        tooltipFormat: formatter,
      };
    });

    return { labels, series };
  })();

  const infraChartHasSeries = infrastructureCompositionChart.series.length > 0;

  const dbBars = latestLabeledBars(dbWidget);
  const cacheBars = latestLabeledBars(cacheWidget);
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
      helper: "Cumulative traffic since boot (shown as TB/GB when large; agent sends MB)",
      formatValue: formatMegabytesAdaptive,
    }),
    toInfrastructureCard({
      label: "Network sent",
      rawValue: latestWidgetValue(findWidgetByKeywords(["network sent"])),
      unit: "MB",
      helper: "Cumulative traffic since boot (shown as TB/GB when large; agent sends MB)",
      formatValue: formatMegabytesAdaptive,
    }),
    toInfrastructureCard({
      label: "App CPU load",
      rawValue: latestWidgetValue(processCpuWidget),
      unit: typeof processCpuWidget?.config?.unit === "string" ? processCpuWidget.config.unit : "%",
      helper: "CPU usage of the instrumented application process",
      warningThreshold: 65,
      dangerThreshold: 85,
    }),
    toInfrastructureCard({
      label: "Disk I/O read",
      rawValue: latestWidgetValue(diskIoReadWidget),
      unit: "MB",
      helper: "Cumulative disk read volume since boot (host counter; agent sends MB)",
      formatValue: formatMegabytesAdaptive,
    }),
  ];

  const chartCaptionFrom = chartClipFrom.trim() ? chartClipFrom : overviewExtended.server_now;
  const chartCaptionTo = chartClipTo.trim() ? chartClipTo : overviewExtended.server_now;

  const chartWindowCaption =
    hostChartWindowMinutes > 0
      ? `Last ${hostChartWindowMinutes}m of the widget load window (ends ${new Date(chartCaptionTo).toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })})`
      : `Widget load window (${new Date(chartCaptionFrom).toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })} → ${new Date(chartCaptionTo).toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })})`;

  return (
    <>
      <section className="grid w-full gap-4 xl:grid-cols-2 xl:items-stretch">
        <div className="min-w-0">
          <div className="flex h-full flex-col rounded-2xl border border-slate-200/90 bg-white p-5 shadow-sm ring-1 ring-slate-900/[0.04] dark:border-neutral-700 dark:bg-neutral-900 dark:shadow-md dark:shadow-black/30 dark:ring-white/[0.06]">
            <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Infrastructure now</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
              Concrete host and app load values captured across macOS, Windows, and Linux.
            </p>
            <div className="mt-4 grid auto-rows-fr gap-4 sm:grid-cols-3">
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
          </div>
        </div>
        <div className="min-w-0">
          <ChartPanel
            className="h-full"
            title="Host resources over time"
            description="Stacked area shows each resource’s share of relative load: each series is scaled to its own peak in this chart window, then normalized so layers sum to 100%. Tooltips list real units. This is a trend comparison (not additive usage)."
          >
            <div className="mb-3 flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                  Chart window
                </span>
                <select
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800 shadow-sm dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
                  value={hostChartWindowMinutes}
                  onChange={(event) => setHostChartWindowMinutes(Number(event.target.value))}
                  aria-label="Host resources chart time window"
                >
                  {HOST_RESOURCES_CHART_WINDOW_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="max-w-md text-xs leading-snug text-slate-500 dark:text-neutral-400">{chartWindowCaption}</p>
            </div>
            {infraChartHasSeries ? (
              <StackedAreaChart
                height={196}
                labels={infrastructureCompositionChart.labels}
                series={infrastructureCompositionChart.series}
              />
            ) : hasInfraSignals ? (
              <p className="text-sm text-slate-600 dark:text-neutral-300">
                No infrastructure samples overlap this chart window. Try{' '}
                <span className="font-medium">&quot;Full loaded range&quot;</span> above or widen the dashboard time window.
              </p>
            ) : statusClassFallbackStack.series.length ? (
              <>
                <StackedAreaChart
                  height={196}
                  labels={statusClassFallbackStack.labels}
                  series={statusClassFallbackStack.series}
                />
                <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
                  Showing request volume by HTTP status class until infrastructure widget samples arrive.
                </p>
              </>
            ) : (
              <p className="text-sm text-slate-600 dark:text-neutral-300">No infrastructure trend data yet.</p>
            )}
          </ChartPanel>
        </div>
      </section>

      <section className="grid w-full gap-4 xl:grid-cols-3">
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
    </>
  );
}
