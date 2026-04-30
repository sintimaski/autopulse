"use client";

import {
  BreakdownBarChart,
  ChartPanel,
  TimeSeriesLineChart,
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
  const cpuSeries = lineWidgetToSeries(cpuWidget);
  const memorySeries = lineWidgetToSeries(memoryWidget);
  const diskSeries = lineWidgetToSeries(diskWidget);
  const networkSeries = lineWidgetToSeries(networkWidget);
  const dbBars = latestLabeledBars(dbWidget);
  const cacheBars = latestLabeledBars(cacheWidget);
  const fallbackMinuteLabels = sparklineSeries.map((bucket) =>
    new Date(bucket.minute).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  const cpuFallbackValues = sparklineSeries.map((bucket) => Number(bucket.request_count || 0));
  const memoryFallbackValues = sparklineSeries.map((bucket) => Number(bucket.avg_latency_ms || 0));
  const diskFallbackValues = sparklineSeries.map((bucket) => Number(bucket.error_count || 0));
  const networkFallbackValues = sparklineSeries.map((bucket) => Number(bucket.request_count || 0));
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
    {
      label: "Network traffic",
      keywords: ["network", "bandwidth", "bytes in", "bytes out", "ingress", "egress", "rx", "tx"],
    },
    { label: "DB query performance", keywords: ["db", "database", "query", "sql"] },
    { label: "Cache hit/miss", keywords: ["cache hit", "cache miss", "cache ratio", "cache", "redis"] },
    { label: "Dependency map", keywords: ["dependency", "service map", "upstream", "downstream"] },
  ].map((item) => ({
    ...item,
    ready: item.keywords.some((keyword) => containsKeyword(widgetSearchCorpus, keyword)),
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
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
          Infrastructure metric coverage
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          These metrics are sourced from SDK dashboard widgets. Add matching widgets to your app to light up missing
          rows.
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

      <section className="grid w-full gap-4 xl:grid-cols-2">
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
