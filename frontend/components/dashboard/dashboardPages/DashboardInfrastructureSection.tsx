"use client";

/* eslint-disable react-hooks/refs --
   While `chartsScopePending`, infra chart inputs are read from `committedInfraRef`, which is
   synced in `useLayoutEffect` when not pending. Mirrors VolumeChart freeze-until-query UX. */

import { useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  buildAlignedChartSpanOptions,
  buildAlignedRollupBucketOptions,
} from "../../../utils/dashboardChartWindows";
import {
  ChartPanel,
  MultiSeriesLineChart,
  type MultiSeriesLineChartSeries,
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
import {
  buildHostChartAxisLabels,
  parseDashboardInstantMs,
} from "./infrastructureTimeUtils";
import { ChartScopeTintOverlay } from "../charts/ChartScopeTintOverlay";

type Props = {
  sparklineSeries: OverviewBucket[];
  overviewExtended: OverviewExtendedResponse;
  dashboardWidgets: DashboardWidgetsResponse | null;
  /** Main dashboard server query window — chart sub-windows and roll-ups must not exceed this. */
  globalWindowMinutes: number;
  chartsScopePending?: boolean;
  chartsScopeAnchorKey?: string;
};

const HOST_RESOURCES_CUMULATIVE_WIDGET_IDS = new Set<string>([
  "infra_network_received_mb",
  "infra_network_sent_mb",
  "infra_disk_io_read_mb",
]);

function isCumulativeInfraWidgetId(widgetId: string): boolean {
  return HOST_RESOURCES_CUMULATIVE_WIDGET_IDS.has(widgetId);
}

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

/**
 * Pulls in missing infra series from `raw` only when the chart would otherwise omit a layer.
 * Salvage must stay inside `salvageIncluded` so a "Last 15m" window cannot re-expand to the full load range.
 */
function mergeMissingHostResourceWidgetPoints(
  filtered: DashboardWidgetPoint[],
  raw: DashboardWidgetPoint[],
  salvageIncluded: (p: DashboardWidgetPoint) => boolean,
): DashboardWidgetPoint[] {
  let out = [...filtered];
  for (const wid of HOST_RESOURCES_CHART_WIDGET_IDS) {
    if (out.some((p) => p.widget_id === wid)) {
      continue;
    }
    const salvage = raw.filter((p) => p.widget_id === wid && salvageIncluded(p));
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

/** Same window as the host-resources chart filter / chart window selector. */
function hostChartPointInWindow(
  p: DashboardWidgetPoint,
  bounds: { fromTimestamp: string; toTimestamp: string },
  lastMinutes: number,
): boolean {
  const toMs = parseDashboardInstantMs(bounds.toTimestamp);
  if (!Number.isFinite(toMs)) {
    return true;
  }
  const t = parseDashboardInstantMs(p.timestamp);
  if (!Number.isFinite(t)) {
    return false;
  }
  const fromBoundMs = parseDashboardInstantMs(bounds.fromTimestamp);
  const startMs =
    lastMinutes > 0
      ? Math.max(Number.isFinite(fromBoundMs) ? fromBoundMs : -Infinity, toMs - lastMinutes * 60 * 1000)
      : Number.isFinite(fromBoundMs)
        ? fromBoundMs
        : -Infinity;
  return t >= startMs && t <= toMs;
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
  return points.filter((p) => hostChartPointInWindow(p, bounds, lastMinutes));
}

function rollingWindowBoundsFromPoints(
  points: DashboardWidgetPoint[],
): { fromMs: number; toMs: number } | null {
  if (!points.length) {
    return null;
  }
  const sorted = [...points].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const fromMs = parseDashboardInstantMs(sorted[0]?.timestamp ?? "");
  const toMs = parseDashboardInstantMs(sorted[sorted.length - 1]?.timestamp ?? "");
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) {
    return null;
  }
  return { fromMs, toMs };
}

function trimWidgetPointsLastMinutes(
  points: DashboardWidgetPoint[],
  lastMinutes: number,
  clipEndIso?: string,
): DashboardWidgetPoint[] {
  if (lastMinutes <= 0 || !points.length) {
    return points;
  }
  const sorted = [...points].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  let endAnchorMs = parseDashboardInstantMs(sorted[sorted.length - 1]?.timestamp ?? "");
  if (!Number.isFinite(endAnchorMs)) {
    return sorted;
  }
  if (clipEndIso?.trim()) {
    const w = parseDashboardInstantMs(clipEndIso);
    if (Number.isFinite(w)) {
      const floored = Math.floor(w / 60_000) * 60_000;
      endAnchorMs = Math.max(endAnchorMs, floored);
    }
  }
  const cutoff = endAnchorMs - lastMinutes * 60 * 1000;
  return sorted.filter((p) => {
    const t = parseDashboardInstantMs(p.timestamp);
    return Number.isFinite(t) && t >= cutoff && t <= endAnchorMs;
  });
}

/** Visible [from, to] in ms for the host chart — matches chart window + clip bounds, with start from data if unbounded. */
function resolveHostChartDisplayRangeMs(
  bounds: { fromTimestamp: string; toTimestamp: string },
  lastMinutes: number,
  filteredPoints: DashboardWidgetPoint[],
): { fromMs: number; toMs: number } | null {
  const clipToMs = parseDashboardInstantMs(bounds.toTimestamp);
  if (!Number.isFinite(clipToMs)) {
    return null;
  }
  const fromBoundMs = parseDashboardInstantMs(bounds.fromTimestamp);
  let startMs =
    lastMinutes > 0
      ? Math.max(Number.isFinite(fromBoundMs) ? fromBoundMs : -Infinity, clipToMs - lastMinutes * 60 * 1000)
      : Number.isFinite(fromBoundMs)
        ? fromBoundMs
        : -Infinity;
  if (!Number.isFinite(startMs) || startMs === -Infinity) {
    const finite = filteredPoints
      .map((p) => parseDashboardInstantMs(p.timestamp))
      .filter((n): n is number => Number.isFinite(n));
    if (!finite.length) {
      return null;
    }
    startMs = Math.min(...finite);
  }
  if (startMs > clipToMs) {
    return null;
  }
  /** When infra samples stop before the dashboard clip end, do not extend the bucket axis to "now" (avoids fake flat lines). */
  const pointTimes = filteredPoints
    .map((p) => parseDashboardInstantMs(p.timestamp))
    .filter((n): n is number => Number.isFinite(n));
  let toMs = clipToMs;
  if (pointTimes.length > 0) {
    const dataMax = Math.max(...pointTimes);
    const SLACK_MS = 2000;
    if (dataMax + SLACK_MS < clipToMs) {
      toMs = Math.max(startMs + 1, dataMax + SLACK_MS);
    }
  }
  if (startMs >= toMs) {
    return null;
  }
  return { fromMs: startMs, toMs };
}

/** One aligned bucket every `bucketMs` from `fromMs` up to `toMs` (last bucket may be shorter). */
function enumerateAlignedBucketStarts(fromMs: number, toMs: number, bucketMs: number): number[] {
  const span = toMs - fromMs;
  if (!Number.isFinite(span) || span <= 0) {
    return [fromMs];
  }
  const out: number[] = [];
  for (let b = fromMs; b < toMs - 1e-9; b += bucketMs) {
    out.push(b);
  }
  if (out.length === 0) {
    out.push(fromMs);
  }
  return out;
}

/**
 * Roll infra widget samples into a **full** bucket grid over `range` (one point per bucket per series).
 * Gauges: mean of samples in the bucket, then forward-filled across empty buckets. Cumulative: last sample
 * in the bucket, then forward-filled. Empty leading buckets use 0 so the x-axis spans the whole chart window.
 */
function bucketWidgetPointsForHostChart(
  points: DashboardWidgetPoint[],
  range: { fromMs: number; toMs: number },
  bucketMinutes: number,
): DashboardWidgetPoint[] {
  if (bucketMinutes <= 0 || !points.length) {
    return [...points].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }
  const { fromMs, toMs } = range;
  const bucketMs = bucketMinutes * 60 * 1000;
  const bucketStarts = enumerateAlignedBucketStarts(fromMs, toMs, bucketMs);
  const n = bucketStarts.length;

  const byWidget = new Map<string, DashboardWidgetPoint[]>();
  for (const p of points) {
    const list = byWidget.get(p.widget_id) ?? [];
    list.push(p);
    byWidget.set(p.widget_id, list);
  }
  for (const list of byWidget.values()) {
    list.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  const out: DashboardWidgetPoint[] = [];

  for (const [widgetId, pts] of byWidget.entries()) {
    const cumulative = isCumulativeInfraWidgetId(widgetId);
    const raw: (number | null)[] = Array.from({ length: n }, () => null);

    for (let i = 0; i < n; i++) {
      const bStart = bucketStarts[i]!;
      const isLast = i === n - 1;
      const items = pts.filter((p) => {
        const t = parseDashboardInstantMs(p.timestamp);
        if (!Number.isFinite(t) || t < bStart) {
          return false;
        }
        if (isLast) {
          return t <= toMs;
        }
        return t < bStart + bucketMs;
      });
      if (!items.length) {
        continue;
      }
      if (cumulative) {
        const last = [...items].sort((a, b) => a.timestamp.localeCompare(b.timestamp))[items.length - 1]!;
        raw[i] = Math.max(0, Number(last.value) || 0);
      } else {
        const vals = items.map((x) => Math.max(0, Number(x.value) || 0));
        raw[i] = vals.reduce((a, b) => a + b, 0) / vals.length;
      }
    }

    let firstIdx = -1;
    let lastIdx = -1;
    for (let i = 0; i < n; i++) {
      if (raw[i] !== null) {
        if (firstIdx === -1) {
          firstIdx = i;
        }
        lastIdx = i;
      }
    }

    let carry: number | null = null;
    for (let i = 0; i < n; i++) {
      if (raw[i] !== null) {
        carry = raw[i];
        continue;
      }
      if (carry === null) {
        continue;
      }
      if (cumulative) {
        raw[i] = carry;
      } else if (firstIdx !== -1 && i > firstIdx && i <= lastIdx) {
        raw[i] = carry;
      }
    }

    for (let i = 0; i < n; i++) {
      const bStart = bucketStarts[i]!;
      const bucketEnd = Math.min(bStart + bucketMs, toMs);
      const tsIso = new Date(bucketEnd).toISOString();
      const v = raw[i];
      const value = v === null || v === undefined || !Number.isFinite(v) ? NaN : v;
      out.push({
        widget_id: widgetId,
        timestamp: tsIso,
        label: null,
        value,
      });
    }
  }

  out.sort((a, b) => a.timestamp.localeCompare(b.timestamp) || a.widget_id.localeCompare(b.widget_id));
  return out;
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
    const v = Number(p.value);
    if (Number.isNaN(v)) {
      byTime.set(t, Number.NaN);
      continue;
    }
    if (!Number.isFinite(v)) {
      continue;
    }
    byTime.set(t, (byTime.get(t) ?? 0) + Math.max(0, v));
  }
  const timestamps = [...byTime.keys()].sort();
  const values = timestamps.map((t) => {
    const v = byTime.get(t);
    if (v !== undefined && Number.isNaN(v)) {
      return Number.NaN;
    }
    return Math.max(0, v ?? 0);
  });
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

type InfraChartCommitted = {
  sparklineSeries: OverviewBucket[];
  overviewExtended: OverviewExtendedResponse;
  dashboardWidgets: DashboardWidgetsResponse | null;
  globalWindowMinutes: number;
  hostChartWindowMinutes: number;
  hostChartBucketMinutes: number;
};

export function DashboardInfrastructureSection({
  sparklineSeries,
  overviewExtended,
  dashboardWidgets,
  globalWindowMinutes,
  chartsScopePending = false,
  chartsScopeAnchorKey,
}: Props) {
  const [hostChartWindowMinutes, setHostChartWindowMinutes] = useState(0);
  const [hostChartBucketMinutes, setHostChartBucketMinutes] = useState(0);

  const committedInfraRef = useRef<InfraChartCommitted>({
    sparklineSeries,
    overviewExtended,
    dashboardWidgets,
    globalWindowMinutes,
    hostChartWindowMinutes: 0,
    hostChartBucketMinutes: 0,
  });
  const prevInfraScopePendingRef = useRef(false);

  useLayoutEffect(() => {
    const wasPending = prevInfraScopePendingRef.current;
    prevInfraScopePendingRef.current = chartsScopePending;
    if (
      wasPending &&
      !chartsScopePending &&
      chartsScopeAnchorKey !== undefined
    ) {
      setHostChartWindowMinutes(0);
      setHostChartBucketMinutes(0);
      committedInfraRef.current = {
        sparklineSeries,
        overviewExtended,
        dashboardWidgets,
        globalWindowMinutes,
        hostChartWindowMinutes: 0,
        hostChartBucketMinutes: 0,
      };
      return;
    }
    if (!chartsScopePending) {
      committedInfraRef.current = {
        sparklineSeries,
        overviewExtended,
        dashboardWidgets,
        globalWindowMinutes,
        hostChartWindowMinutes,
        hostChartBucketMinutes,
      };
    }
  }, [
    chartsScopePending,
    chartsScopeAnchorKey,
    sparklineSeries,
    overviewExtended,
    dashboardWidgets,
    globalWindowMinutes,
    hostChartWindowMinutes,
    hostChartBucketMinutes,
  ]);

  const ix = chartsScopePending ? committedInfraRef.current : null;
  const ixOverview = ix?.overviewExtended ?? overviewExtended;
  const ixWidgets = ix?.dashboardWidgets ?? dashboardWidgets;
  const ixGlobalWin = ix?.globalWindowMinutes ?? globalWindowMinutes;
  const ixHostWin = ix?.hostChartWindowMinutes ?? hostChartWindowMinutes;
  const ixHostBucket = ix?.hostChartBucketMinutes ?? hostChartBucketMinutes;

  const widgetDefinitions = normalizeIncomingWidgetDefinitions(ixWidgets?.definitions);
  const widgetPointsById = new Map<string, DashboardWidgetPoint[]>();
  for (const point of ixWidgets?.points ?? []) {
    const existing = widgetPointsById.get(point.widget_id) ?? [];
    existing.push(point);
    widgetPointsById.set(point.widget_id, existing);
  }

  const hostChartWindowOptions = useMemo(
    () => buildAlignedChartSpanOptions(ixGlobalWin),
    [ixGlobalWin],
  );

  const effectiveHostChartWindowMinutes = useMemo(() => {
    const allowed = new Set(hostChartWindowOptions.map((o) => o.value));
    return allowed.has(ixHostWin) ? ixHostWin : 0;
  }, [ixHostWin, hostChartWindowOptions]);

  const rollupBucketCapMinutes = useMemo(() => {
    if (effectiveHostChartWindowMinutes > 0) {
      return Math.min(effectiveHostChartWindowMinutes, Math.max(1, ixGlobalWin));
    }
    return Math.max(1, ixGlobalWin);
  }, [effectiveHostChartWindowMinutes, ixGlobalWin]);

  const hostChartBucketOptions = useMemo(
    () => buildAlignedRollupBucketOptions(rollupBucketCapMinutes),
    [rollupBucketCapMinutes],
  );

  const effectiveHostChartBucketPick = useMemo(() => {
    const allowed = new Set(hostChartBucketOptions.map((o) => o.value));
    return allowed.has(ixHostBucket) ? ixHostBucket : 0;
  }, [ixHostBucket, hostChartBucketOptions]);

  const effectiveHostChartBucketMinutes = useMemo(() => {
    if (effectiveHostChartBucketPick <= 0) {
      return 0;
    }
    if (effectiveHostChartWindowMinutes <= 0) {
      return effectiveHostChartBucketPick;
    }
    return Math.min(effectiveHostChartBucketPick, effectiveHostChartWindowMinutes);
  }, [effectiveHostChartBucketPick, effectiveHostChartWindowMinutes]);

  /** Clip chart data to widget API window (aligned with infra probe points); fall back to overview when missing. */
  const overviewFrom = ixOverview.from_timestamp;
  const overviewTo = ixOverview.to_timestamp;
  const chartClipFrom = ixWidgets?.from_timestamp || overviewFrom;
  const chartClipTo = ixWidgets?.to_timestamp || overviewTo;

  const hostChartFilteredPoints = useMemo(() => {
    const raw = ixWidgets?.points ?? [];
    const bounds = { fromTimestamp: chartClipFrom, toTimestamp: chartClipTo };
    const windowSalvageOk = (p: DashboardWidgetPoint) =>
      hostChartPointInWindow(p, bounds, effectiveHostChartWindowMinutes);
    const clipped = filterWidgetPointsForTimeSpan(raw, bounds, effectiveHostChartWindowMinutes);
    let next = mergeMissingHostResourceWidgetPoints(clipped, raw, windowSalvageOk);
    if (next.length > 0) {
      return next;
    }
    if (raw.length === 0) {
      return raw;
    }
    if (effectiveHostChartWindowMinutes <= 0) {
      return mergeMissingHostResourceWidgetPoints(raw, raw, windowSalvageOk);
    }
    const rolling = trimWidgetPointsLastMinutes(raw, effectiveHostChartWindowMinutes, chartClipTo);
    const rb = rollingWindowBoundsFromPoints(rolling);
    const rollingSalvageOk =
      rb !== null
        ? (p: DashboardWidgetPoint) => {
            const t = parseDashboardInstantMs(p.timestamp);
            return Number.isFinite(t) && t >= rb.fromMs && t <= rb.toMs;
          }
        : (_p: DashboardWidgetPoint) => false;
    const rescued = mergeMissingHostResourceWidgetPoints(rolling, raw, rollingSalvageOk);
    return rescued.length > 0 ? rescued : mergeMissingHostResourceWidgetPoints(raw, raw, windowSalvageOk);
  }, [ixWidgets?.points, chartClipFrom, chartClipTo, effectiveHostChartWindowMinutes]);

  const hostChartDisplayRangeMs = useMemo(() => {
    return resolveHostChartDisplayRangeMs(
      { fromTimestamp: chartClipFrom, toTimestamp: chartClipTo },
      effectiveHostChartWindowMinutes,
      hostChartFilteredPoints,
    );
  }, [chartClipFrom, chartClipTo, effectiveHostChartWindowMinutes, hostChartFilteredPoints]);

  const hostChartDisplayPoints = useMemo(() => {
    if (!hostChartDisplayRangeMs) {
      return hostChartFilteredPoints;
    }
    return bucketWidgetPointsForHostChart(
      hostChartFilteredPoints,
      hostChartDisplayRangeMs,
      effectiveHostChartBucketMinutes,
    );
  }, [hostChartFilteredPoints, hostChartDisplayRangeMs, effectiveHostChartBucketMinutes]);

  const hostChartPointsByWidget = useMemo(() => {
    const grouped = new Map<string, DashboardWidgetPoint[]>();
    for (const p of hostChartDisplayPoints) {
      const bucket = grouped.get(p.widget_id) ?? [];
      bucket.push(p);
      grouped.set(p.widget_id, bucket);
    }
    return grouped;
  }, [hostChartDisplayPoints]);

  const findWidgetByKeywords = (keywords: string[]) =>
    widgetDefinitions.find((widget) => {
      const corpus = `${widget.widget_id} ${widget.title} ${widget.description ?? ""}`.toLowerCase();
      return keywords.some((keyword) => containsKeyword(corpus, keyword));
    });

  const definitionOrStubIfPoints = (widgetId: string): DashboardWidgetDefinition | undefined =>
    widgetDefinitions.find((w) => w.widget_id === widgetId) ??
    (widgetPointsById.has(widgetId) ? infraLineStub(widgetId) : undefined);

  const INFRA_COMPOSE = {
    cpu: { label: "CPU", color: "#f97316" },
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
    const labels = buildHostChartAxisLabels(sortedTs);

    const columns: Record<InfraComposeKey, number[]> = {
      cpu: [],
      memory: [],
      disk: [],
      network: [],
    };

    const gapMarkersInChart = effectiveHostChartBucketMinutes > 0;

    const columnAligned = (tl: { timestamps: string[]; values: number[] } | null) => {
      if (!tl) {
        return sortedTs.map(() => Number.NaN);
      }
      const map = new Map(tl.timestamps.map((stamp, idx) => [stamp, tl.values[idx] ?? 0]));
      return sortedTs.map((stamp) => {
        if (!map.has(stamp)) {
          return Number.NaN;
        }
        const v = map.get(stamp) as number;
        if (Number.isNaN(v)) {
          return Number.NaN;
        }
        return Math.max(0, v);
      });
    };

    /** Native mode: each infra widget timestamps differ slightly; union grid has NaN holes. Hold last value so lines render (no fake zeros). */
    const forwardFillHoldNative = (values: number[]): number[] => {
      let carry: number | null = null;
      return values.map((v) => {
        if (Number.isFinite(v) && !Number.isNaN(v)) {
          carry = v;
          return v;
        }
        return carry ?? 0;
      });
    };

    columns.cpu = columnAligned(timelines.cpu);
    columns.memory = columnAligned(timelines.memory);
    columns.disk = columnAligned(timelines.disk);
    columns.network = columnAligned(timelines.network);

    if (!gapMarkersInChart) {
      columns.cpu = forwardFillHoldNative(columns.cpu);
      columns.memory = forwardFillHoldNative(columns.memory);
      columns.disk = forwardFillHoldNative(columns.disk);
      columns.network = forwardFillHoldNative(columns.network);
    }

    const unitCpu = typeof cpuWidget?.config?.unit === "string" ? cpuWidget.config.unit : "%";
    const unitMemory = typeof memoryWidget?.config?.unit === "string" ? memoryWidget.config.unit : "%";
    const unitDisk = typeof diskWidget?.config?.unit === "string" ? diskWidget.config.unit : "%";
    const formatters: Record<InfraComposeKey, (v: number) => string> = {
      cpu: (v) => formatMetricValue(v, unitCpu),
      memory: (v) => formatMetricValue(v, unitMemory),
      disk: (v) => formatMetricValue(v, unitDisk),
      network: (v) => formatMegabytesAdaptive(v),
    };

    const netMb = columns.network;
    const finiteNet = netMb.filter((v) => Number.isFinite(v) && v >= 0);
    const netPeak = Math.max(1e-9, ...finiteNet.map((v) => Math.max(0, v)));
    const networkAsChartPercent = netMb.map((v) =>
      Number.isFinite(v) ? (Math.max(0, v) / netPeak) * 100 : Number.NaN,
    );

    const series: StackedAreaSeries[] = activeKeys.map((key) => {
      const { label, color } = INFRA_COMPOSE[key];
      const formatter = formatters[key];
      if (key === "network") {
        return {
          id: key,
          label,
          color,
          values: networkAsChartPercent,
          tooltipRawValues: netMb,
          tooltipFormat: formatter,
        };
      }
      return {
        id: key,
        label,
        color,
        values: columns[key],
        tooltipFormat: formatter,
      };
    });

    return { labels, series };
  })();

  const infraChartHasSeries = infrastructureCompositionChart.series.length > 0;

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

  const chartCaptionFrom = chartClipFrom.trim() ? chartClipFrom : ixOverview.server_now;
  const chartCaptionTo = chartClipTo.trim() ? chartClipTo : ixOverview.server_now;

  const chartWindowCaption =
    effectiveHostChartWindowMinutes > 0
      ? `Last ${effectiveHostChartWindowMinutes}m of the widget load window (ends ${new Date(chartCaptionTo).toLocaleString(undefined, {
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

  const bucketRollupCaption =
    effectiveHostChartBucketMinutes <= 0
      ? "Native: one point per sample in the chart window (no roll-up)."
      : `Roll-up: ${effectiveHostChartBucketMinutes}m buckets across the full chart window${
          effectiveHostChartBucketPick > 0 &&
          effectiveHostChartBucketMinutes !== effectiveHostChartBucketPick &&
          effectiveHostChartWindowMinutes > 0
            ? ` (bucket capped to the ${effectiveHostChartWindowMinutes}m window)`
            : ""
        }. Gauges average samples in each bucket; cumulative counters use the reading at the bucket end; empty buckets repeat the last value (0 before the first sample).`;

  return (
    <div className="flex flex-col gap-8">
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
            description="Four independent lines on one chart (0–100% axis): CPU, memory, and disk are real utilization. Network is cumulative MB scaled to 0–100% of the peak in this window so it fits the same axis—hover for actual MB. Roll-up bucket summarizes samples across the chart window."
          >
            <div className="relative min-h-[12rem]">
              {chartsScopePending ? (
                <ChartScopeTintOverlay className="rounded-xl" />
              ) : null}
              <div className="mb-3 flex flex-col gap-2">
              <div className="flex flex-wrap items-end gap-3">
                {effectiveHostChartBucketPick > 0 ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                      Chart window
                    </span>
                    <select
                      className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800 shadow-sm dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
                      value={effectiveHostChartWindowMinutes}
                      disabled={chartsScopePending}
                      onChange={(event) => setHostChartWindowMinutes(Number(event.target.value))}
                      aria-label="Host resources chart time window"
                    >
                      {hostChartWindowOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <label className="flex flex-col gap-1">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                    Roll-up bucket
                  </span>
                  <select
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800 shadow-sm dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
                    value={effectiveHostChartBucketPick}
                    disabled={chartsScopePending}
                    onChange={(event) => setHostChartBucketMinutes(Number(event.target.value))}
                    aria-label="Host resources chart roll-up bucket size"
                  >
                    {hostChartBucketOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="max-w-xl text-xs leading-snug text-slate-500 dark:text-neutral-400">{chartWindowCaption}</p>
              <p className="max-w-xl text-xs leading-snug text-slate-500 dark:text-neutral-400">{bucketRollupCaption}</p>
            </div>
            {infraChartHasSeries ? (
              <MultiSeriesLineChart
                height={196}
                labels={infrastructureCompositionChart.labels}
                series={infrastructureCompositionChart.series as MultiSeriesLineChartSeries[]}
                ySuggestedMaxCap={100}
                pointRadius={effectiveHostChartBucketMinutes <= 0 ? 2.25 : 0}
                emptyMessage="No infrastructure samples in this chart window."
                live
                chartsScopePending={chartsScopePending}
              />
            ) : hasInfraSignals ? (
              <p className="text-sm text-slate-600 dark:text-neutral-300">
                No infrastructure samples overlap this chart window. Try{' '}
                <span className="font-medium">&quot;Full loaded range&quot;</span> above or widen the dashboard time window.
              </p>
            ) : (
              <p className="text-sm text-slate-600 dark:text-neutral-300">
                No host resource samples yet. After the SDK sends infrastructure metrics (or the server records host
                samples on ingest), CPU, memory, disk, and network will appear here—this chart does not use HTTP traffic
                as a substitute.
              </p>
            )}
            </div>
          </ChartPanel>
        </div>
      </section>
    </div>
  );
}
