"use client";

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
  OverviewBucket,
  OverviewExtendedResponse,
} from "../dashboardTypes";

type Props = {
  sparklineSeries: OverviewBucket[];
  overviewExtended: OverviewExtendedResponse;
  dashboardWidgets: {
    definitions: DashboardWidgetDefinition[];
    points: DashboardWidgetPoint[];
  } | null;
};

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

export function DashboardInfrastructureSection({ sparklineSeries, overviewExtended, dashboardWidgets }: Props) {
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

  const widgetDefinitions = (dashboardWidgets?.definitions ?? []).filter(
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
  for (const point of dashboardWidgets?.points ?? []) {
    const existing = widgetPointsById.get(point.widget_id) ?? [];
    existing.push(point);
    widgetPointsById.set(point.widget_id, existing);
  }

  const findWidgetByKeywords = (keywords: string[]) =>
    widgetDefinitions.find((widget) => {
      const corpus = `${widget.widget_id} ${widget.title} ${widget.description ?? ""}`.toLowerCase();
      return keywords.some((keyword) => containsKeyword(corpus, keyword));
    });

  const formatAxisTime = (iso: string) =>
    new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  /** Pivot widget points into stacked layers (one layer per distinct `label`, or a single default series). */
  const widgetPointsToStackedSeries = (
    widget: DashboardWidgetDefinition | undefined,
    defaultSeriesLabel: string,
    colors: string[],
  ): { labels: string[]; series: StackedAreaSeries[] } => {
    if (!widget) {
      return { labels: [], series: [] };
    }
    const points = [...(widgetPointsById.get(widget.widget_id) ?? [])].sort((a, b) =>
      a.timestamp.localeCompare(b.timestamp),
    );
    if (!points.length) {
      return { labels: [], series: [] };
    }
    const byTime = new Map<string, Map<string, number>>();
    const timeOrder: string[] = [];
    for (const p of points) {
      const t = p.timestamp;
      if (!byTime.has(t)) {
        byTime.set(t, new Map());
        timeOrder.push(t);
      }
      const layer = String(p.label ?? defaultSeriesLabel).trim() || defaultSeriesLabel;
      const prev = byTime.get(t)!.get(layer) ?? 0;
      byTime.get(t)!.set(layer, prev + Number(p.value));
    }
    const labelSet = new Set<string>();
    for (const m of byTime.values()) {
      for (const k of m.keys()) {
        labelSet.add(k);
      }
    }
    const layerKeys = [...labelSet].sort();
    const labels = timeOrder.map((t) => formatAxisTime(t));
    const series: StackedAreaSeries[] = layerKeys.map((label, i) => ({
      id: label,
      label,
      color: colors[i % colors.length],
      values: timeOrder.map((t) => Math.max(0, byTime.get(t)?.get(label) ?? 0)),
    }));
    return { labels, series };
  };

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

  const INFRA_STACK_PALETTE_CPU = ["#0ea5e9", "#38bdf8", "#7dd3fc", "#bae6fd"];
  const INFRA_STACK_PALETTE_MEM = ["#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe"];
  const INFRA_STACK_PALETTE_DISK = ["#f59e0b", "#fbbf24", "#fcd34d", "#fde68a"];
  const INFRA_STACK_PALETTE_NET = ["#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4"];

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

  const statusClassFallbackStack = sparklineToStatusStack(sparklineSeries);
  const cpuStack = widgetPointsToStackedSeries(cpuWidget, "CPU", INFRA_STACK_PALETTE_CPU);
  const memoryStack = widgetPointsToStackedSeries(memoryWidget, "Memory", INFRA_STACK_PALETTE_MEM);
  const diskStack = widgetPointsToStackedSeries(diskWidget, "Disk", INFRA_STACK_PALETTE_DISK);
  const networkStack = widgetPointsToStackedSeries(networkWidget, "Network", INFRA_STACK_PALETTE_NET);

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
      <section className="grid w-full gap-4 xl:grid-cols-2">
        <ChartPanel
          title="CPU usage"
          description="Stacked trend: multiple CPU dimensions from widget labels, or HTTP status mix as a stand-in."
        >
          {cpuStack.series.length || statusClassFallbackStack.series.length ? (
            <StackedAreaChart
              height={132}
              labels={cpuStack.series.length ? cpuStack.labels : statusClassFallbackStack.labels}
              series={cpuStack.series.length ? cpuStack.series : statusClassFallbackStack.series}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No CPU widget data yet.</p>
          )}
          {!cpuStack.series.length && statusClassFallbackStack.series.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Showing request volume by HTTP status class until CPU widget samples arrive.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel
          title="Memory usage"
          description="Stacked RAM signals when labels differentiate pools; otherwise status-class traffic proxy."
        >
          {memoryStack.series.length || statusClassFallbackStack.series.length ? (
            <StackedAreaChart
              height={132}
              labels={
                memoryStack.series.length ? memoryStack.labels : statusClassFallbackStack.labels
              }
              series={
                memoryStack.series.length ? memoryStack.series : statusClassFallbackStack.series
              }
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No memory widget data yet.</p>
          )}
          {!memoryStack.series.length && statusClassFallbackStack.series.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Showing request volume by HTTP status class until memory widget samples arrive.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel
          title="Disk usage / I/O"
          description="Stacked disk or I/O series from widgets; fallback is status-class request mix."
        >
          {diskStack.series.length || statusClassFallbackStack.series.length ? (
            <StackedAreaChart
              height={132}
              labels={diskStack.series.length ? diskStack.labels : statusClassFallbackStack.labels}
              series={diskStack.series.length ? diskStack.series : statusClassFallbackStack.series}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No disk I/O widget data yet.</p>
          )}
          {!diskStack.series.length && statusClassFallbackStack.series.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Showing request volume by HTTP status class until disk widget samples arrive.
            </p>
          ) : null}
        </ChartPanel>
        <ChartPanel
          title="Network traffic"
          description="Ideal when widget exposes inbound vs outbound labels; stacked proxy uses status bands."
        >
          {networkStack.series.length || statusClassFallbackStack.series.length ? (
            <StackedAreaChart
              height={132}
              labels={
                networkStack.series.length ? networkStack.labels : statusClassFallbackStack.labels
              }
              series={
                networkStack.series.length ? networkStack.series : statusClassFallbackStack.series
              }
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-neutral-300">No network widget data yet.</p>
          )}
          {!networkStack.series.length && statusClassFallbackStack.series.length ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Showing request volume by HTTP status class until network widget samples arrive.
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
