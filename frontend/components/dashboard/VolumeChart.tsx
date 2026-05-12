"use client";

/* eslint-disable react-hooks/refs --
   While `chartsScopePending`, chart inputs are read from `committedVolumeRef`, which is
   synced in `useLayoutEffect` when not pending. This avoids an intermediate paint and
   `react-hooks/set-state-in-effect` violations from mirroring the same data in state. */

import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ChartData, ChartOptions } from "chart.js";

import type { OverviewBucket } from "../../utils/dashboardData";
import {
  aggregateSeriesByStep,
  buildResponseClassStackValues,
  maxBucketRequestCount,
  trimSeriesToLastMinutes,
} from "../../utils/dashboardData";
import type { OverviewReleaseMarker } from "./dashboardTypes";
import { uniqueReleaseMarkerFractions } from "../../utils/releaseMarkersChart";
import {
  buildAlignedChartSpanOptions,
  buildVolumeStepOptions,
  defaultVolumeStepMinutes,
} from "../../utils/dashboardChartWindows";
import { CanvasBar } from "./charts/chartCanvas";
import { ChartScopeTintOverlay } from "./charts/ChartScopeTintOverlay";
import { StackedAreaChart } from "./charts/StackedAreaChart";
import type { StackedAreaSeries } from "./charts/StackedAreaChart";

function formatMinuteLabel(iso: string): string {
  try {
    return parseIsoTimestamp(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function parseIsoTimestamp(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

function clampStepToAllowed(step: number, allowed: readonly number[]): number {
  if (!allowed.length) {
    return Math.max(1, Math.floor(step));
  }
  if (allowed.includes(step)) {
    return step;
  }
  const atOrBelow = allowed.filter((s) => s <= step);
  return atOrBelow.length > 0 ? atOrBelow[atOrBelow.length - 1]! : allowed[0]!;
}

function barColorForBucket(bucket: OverviewBucket): string {
  const requestCount = Number(bucket.request_count || 0);
  const errorCount = Number(bucket.error_count || 0);
  const errRatio = requestCount ? errorCount / requestCount : 0;
  if (errRatio > 0.25) {
    return "#e11d48";
  }
  if (errRatio > 0) {
    return "#d97706";
  }
  return "#737373";
}

type VolumeCommittedInputs = {
  series: OverviewBucket[];
  fromTimestamp: string;
  toTimestamp: string;
  globalWindowMinutes: number;
  chartSpanMinutes: number;
  stepMinutesUser: number | null;
  scopeAnchorKey: string;
};

export function VolumeChart({
  series,
  fromTimestamp,
  toTimestamp,
  globalWindowMinutes,
  diagnosisBaseQuery,
  releaseMarkers,
  scopeAnchorKey,
  chartsScopePending = false,
}: {
  series: OverviewBucket[];
  fromTimestamp: string;
  toTimestamp: string;
  globalWindowMinutes: number;
  diagnosisBaseQuery?: Record<string, string>;
  /** Optional release / deploy instants (same window as overview API) drawn as vertical lines. */
  releaseMarkers?: readonly OverviewReleaseMarker[];
  /** When set, chart remount key tracks dashboard query scope (not live poll clock drift). */
  scopeAnchorKey?: string;
  chartsScopePending?: boolean;
}) {
  const router = useRouter();
  const [chartSpanMinutes, setChartSpanMinutes] = useState(0);
  /** `null` = use span-derived default step (coarser than 1m when the window allows). */
  const [stepMinutesUser, setStepMinutesUser] = useState<number | null>(null);

  const committedVolumeRef = useRef<VolumeCommittedInputs>({
    series,
    fromTimestamp,
    toTimestamp,
    globalWindowMinutes,
    chartSpanMinutes: 0,
    stepMinutesUser: null,
    scopeAnchorKey: scopeAnchorKey ?? "static",
  });
  const prevChartsScopePendingRef = useRef(false);

  useLayoutEffect(() => {
    const wasPending = prevChartsScopePendingRef.current;
    prevChartsScopePendingRef.current = chartsScopePending;
    if (wasPending && !chartsScopePending) {
      setChartSpanMinutes(0);
      setStepMinutesUser(null);
      committedVolumeRef.current = {
        series,
        fromTimestamp,
        toTimestamp,
        globalWindowMinutes,
        chartSpanMinutes: 0,
        stepMinutesUser: null,
        scopeAnchorKey: scopeAnchorKey ?? "static",
      };
      return;
    }
    if (!chartsScopePending) {
      committedVolumeRef.current = {
        series,
        fromTimestamp,
        toTimestamp,
        globalWindowMinutes,
        chartSpanMinutes,
        stepMinutesUser,
        scopeAnchorKey: scopeAnchorKey ?? "static",
      };
    }
  }, [
    chartsScopePending,
    series,
    fromTimestamp,
    toTimestamp,
    globalWindowMinutes,
    chartSpanMinutes,
    stepMinutesUser,
    scopeAnchorKey,
  ]);

  const c = chartsScopePending ? committedVolumeRef.current : null;
  const sSeries = c?.series ?? series;
  const sFrom = c?.fromTimestamp ?? fromTimestamp;
  const sTo = c?.toTimestamp ?? toTimestamp;
  const sWindow = c?.globalWindowMinutes ?? globalWindowMinutes;
  const sSpanPick = c?.chartSpanMinutes ?? chartSpanMinutes;
  const sStepPick = c?.stepMinutesUser ?? stepMinutesUser;
  const sAnchor = c?.scopeAnchorKey ?? (scopeAnchorKey ?? "static");

  const chartSpanOptions = useMemo(
    () => buildAlignedChartSpanOptions(sWindow),
    [sWindow],
  );

  const effectiveChartSpanMinutes = useMemo(() => {
    const allowed = new Set(chartSpanOptions.map((o) => o.value));
    return allowed.has(sSpanPick) ? sSpanPick : 0;
  }, [sSpanPick, chartSpanOptions]);

  const effectiveSpanMinutes =
    effectiveChartSpanMinutes > 0 ? effectiveChartSpanMinutes : Math.max(1, sWindow);

  const allowedStepMinutes = useMemo(
    () => buildVolumeStepOptions(effectiveSpanMinutes),
    [effectiveSpanMinutes],
  );

  const autoStepMinutes = useMemo(
    () => defaultVolumeStepMinutes(effectiveSpanMinutes, allowedStepMinutes),
    [allowedStepMinutes, effectiveSpanMinutes],
  );

  const effectiveStepMinutes = useMemo(() => {
    const pick = sStepPick === null ? autoStepMinutes : sStepPick;
    return clampStepToAllowed(pick, allowedStepMinutes);
  }, [allowedStepMinutes, autoStepMinutes, sStepPick]);

  const displayed = useMemo(() => {
    const trimmed =
      effectiveChartSpanMinutes <= 0
        ? [...sSeries].sort((a, b) => a.minute.localeCompare(b.minute))
        : trimSeriesToLastMinutes(sSeries, effectiveChartSpanMinutes, sTo);
    return aggregateSeriesByStep(trimmed, effectiveStepMinutes);
  }, [sSeries, effectiveChartSpanMinutes, effectiveStepMinutes, sTo]);

  const releaseMarkerFractions = useMemo(
    () => uniqueReleaseMarkerFractions(displayed, effectiveStepMinutes, releaseMarkers ?? []),
    [displayed, effectiveStepMinutes, releaseMarkers],
  );

  const max = maxBucketRequestCount(displayed);
  const displayedRef = useRef(displayed);
  useLayoutEffect(() => {
    displayedRef.current = displayed;
  }, [displayed]);

  const totalRequests = displayed.reduce((sum, bucket) => sum + Number(bucket.request_count || 0), 0);
  const totalErrors = displayed.reduce((sum, bucket) => sum + Number(bucket.error_count || 0), 0);
  const overallErrorRatePct = totalRequests > 0 ? (totalErrors / totalRequests) * 100 : 0;

  const chartLayoutKey = [
    sAnchor,
    String(sWindow),
    String(effectiveChartSpanMinutes),
    String(effectiveStepMinutes),
  ].join("|");

  const onBucketClick = useCallback(
    (bucket: OverviewBucket) => {
      const bucketStart = parseIsoTimestamp(bucket.minute).toISOString();
      const bucketEnd = new Date(
        parseIsoTimestamp(bucket.minute).getTime() + effectiveStepMinutes * 60_000,
      ).toISOString();
      const params = new URLSearchParams(diagnosisBaseQuery ?? {});
      params.set("from_timestamp", bucketStart);
      params.set("to_timestamp", bucketEnd);
      params.set("error_group_sort", "count");
      const query = params.toString();
      router.push(`/diagnosis?${query}#grouped-errors`);
    },
    [diagnosisBaseQuery, router, effectiveStepMinutes],
  );

  const volumeBarData = useMemo((): ChartData<"bar"> => {
    return {
      labels: displayed.map((b) => formatMinuteLabel(b.minute)),
      datasets: [
        {
          label: "Requests",
          data: displayed.map((b) => Number(b.request_count || 0)),
          backgroundColor: displayed.map((b) => barColorForBucket(b)),
          borderRadius: 3,
          borderSkipped: false,
          categoryPercentage: 1,
          barPercentage: 1,
          maxBarThickness: 56,
        },
      ],
    };
  }, [displayed]);

  const volumeBarOptions = useMemo<ChartOptions<"bar">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      // Hover the full time column (not only the painted bar) so sparse buckets stay easy to inspect.
      interaction: {
        mode: "index",
        intersect: false,
        axis: "x",
      },
      onHover: (event, elements, chart) => {
        const canvas = chart?.canvas;
        if (!canvas) {
          return;
        }
        if (elements.length > 0) {
          canvas.style.cursor = "pointer";
        } else {
          canvas.style.cursor = "default";
        }
      },
      onClick: (_event, elements) => {
        if (!elements.length) {
          return;
        }
        const i = elements[0].index;
        const bucket = displayedRef.current[i];
        if (bucket) {
          onBucketClick(bucket);
        }
      },
      plugins: {
        legend: { display: false },
        lumonoxReleaseMarkers: { fractions: releaseMarkerFractions },
        tooltip: {
          callbacks: {
            title: (items) => {
              const b = displayedRef.current[items[0]?.dataIndex ?? 0];
              return b ? formatMinuteLabel(b.minute) : "";
            },
            afterBody: (items) => {
              const b = displayedRef.current[items[0]?.dataIndex ?? 0];
              if (!b) {
                return [];
              }
              const rc = Number(b.request_count || 0);
              const ec = Number(b.error_count || 0);
              const errPct = rc > 0 ? ((ec / rc) * 100).toFixed(1) : "0.0";
              return [
                `${rc} requests`,
                `${ec} errors (${errPct}%)`,
                `Avg latency ${Number(b.avg_latency_ms || 0).toFixed(1)} ms`,
                "Click bar → Diagnosis for this bucket",
              ];
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxRotation: 45,
            autoSkip: true,
            maxTicksLimit: 14,
            color: "rgba(100, 116, 139, 0.9)",
            font: { size: 9 },
          },
          border: { display: false },
        },
        y: {
          beginAtZero: true,
          suggestedMax: max > 0 ? max * 1.05 : 1,
          grid: { color: "rgba(100, 116, 139, 0.12)" },
          ticks: { color: "rgba(100, 116, 139, 0.9)", font: { size: 10 } },
          border: { display: false },
        },
      },
    }),
    [max, onBucketClick, releaseMarkerFractions],
  );

  const barChartHeight = Math.round(120 * 1.25);

  const trendLabels = useMemo(() => displayed.map((bucket) => formatMinuteLabel(bucket.minute)), [displayed]);

  const responseClassStack = useMemo(() => buildResponseClassStackValues(displayed), [displayed]);

  const overlayClassTrendSeries = useMemo((): StackedAreaSeries[] => {
    return [
      { id: "2xx", label: "2xx", color: "#22c55e", values: responseClassStack.counts2xx },
      { id: "3xx", label: "3xx", color: "#38bdf8", values: responseClassStack.counts3xx },
      { id: "4xx", label: "4xx", color: "#f59e0b", values: responseClassStack.counts4xx },
      { id: "5xx", label: "5xx", color: "#f43f5e", values: responseClassStack.counts5xx },
    ];
  }, [responseClassStack]);

  const trendCardShell =
    "relative rounded-xl border border-slate-200/80 bg-gradient-to-br from-white/90 via-slate-50/80 to-indigo-50/50 p-3 dark:border-neutral-700 dark:from-neutral-900/90 dark:via-neutral-900/80 dark:to-indigo-950/20";

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <p className="text-sm text-slate-500 dark:text-neutral-400">
          Server window {formatMinuteLabel(sFrom)} → {formatMinuteLabel(sTo)} ({sWindow}m)
        </p>
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Chart span
            <select
              value={effectiveChartSpanMinutes}
              disabled={chartsScopePending}
              onChange={(e) => setChartSpanMinutes(Number(e.target.value))}
              className="min-w-[160px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
            >
              {chartSpanOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Step (minutes)
            <select
              value={effectiveStepMinutes}
              disabled={chartsScopePending}
              onChange={(e) => setStepMinutesUser(Number(e.target.value))}
              className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
            >
              {allowedStepMinutes.map((m) => (
                <option key={m} value={m}>
                  {m}m buckets
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="mt-3 space-y-3">
        {!displayed.length ? (
          <div className="relative flex min-h-[5rem] items-center overflow-hidden rounded-xl border border-slate-200/80 bg-white/60 dark:border-neutral-700 dark:bg-neutral-900/70">
            {chartsScopePending ? <ChartScopeTintOverlay className="rounded-xl" /> : null}
            <div className="relative z-0 flex h-16 w-full items-center px-3 text-sm text-slate-500 dark:text-neutral-300">
              No buckets in this chart range.
            </div>
          </div>
        ) : max <= 0 ? (
          <div className="relative flex min-h-[5rem] items-center overflow-hidden rounded-xl border border-slate-200/80 bg-white/60 dark:border-neutral-700 dark:bg-neutral-900/70">
            {chartsScopePending ? <ChartScopeTintOverlay className="rounded-xl" /> : null}
            <div className="relative z-0 flex h-16 w-full items-center px-3 text-sm text-slate-500 dark:text-neutral-300">
              No request volume in these buckets.
            </div>
          </div>
        ) : (
          <>
            <div
              className="relative w-full min-w-0 overflow-hidden rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-3 dark:border-neutral-700 dark:from-neutral-900 dark:to-neutral-950"
              role="img"
              aria-label="Request volume by time bucket"
            >
              {chartsScopePending ? <ChartScopeTintOverlay className="rounded-xl" /> : null}
              <div className="relative z-0 w-full" style={{ height: barChartHeight }}>
                <CanvasBar key={chartLayoutKey} data={volumeBarData} options={volumeBarOptions} />
              </div>
            </div>
            <div className={`${trendCardShell} mt-3`}>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-400">
                Trends — requests by class
              </h4>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-neutral-500">
                2xx / 3xx / 4xx / 5xx counts per bucket (overlay). Click a point to open Diagnosis for that bucket.
              </p>
              <div className="relative mt-2 min-h-[12rem] w-full min-w-0">
                {chartsScopePending ? <ChartScopeTintOverlay className="rounded-lg" /> : null}
                <div className="relative z-0">
                  <StackedAreaChart
                    labels={trendLabels}
                    series={overlayClassTrendSeries}
                    height={192}
                    variant="overlay"
                    live
                    releaseMarkerFractions={releaseMarkerFractions}
                    chartsScopePending={false}
                    accessibilityLabel={`Request volume by response class, plotted per bucket. Window ${totalRequests.toLocaleString()} requests, ${totalErrors.toLocaleString()} errors (${overallErrorRatePct.toFixed(1)}% avg error rate). Click a point to open diagnosis for that bucket.`}
                    onPointClick={(idx) => {
                      const bucket = displayedRef.current[idx];
                      if (bucket) {
                        onBucketClick(bucket);
                      }
                    }}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
