"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { OverviewBucket } from "../../utils/dashboardData";
import {
  aggregateSeriesByStep,
  maxBucketRequestCount,
  trimSeriesToLastMinutes,
} from "../../utils/dashboardData";
import { TimeSeriesLineChart } from "./charts/TimeSeriesLineChart";

const CHART_SPAN_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: "Full loaded range" },
  { value: 15, label: "Last 15m" },
  { value: 30, label: "Last 30m" },
  { value: 60, label: "Last 60m" },
  { value: 120, label: "Last 2h" },
  { value: 240, label: "Last 4h" },
  { value: 480, label: "Last 8h" },
  { value: 1440, label: "Last 24h" },
];

const STEP_OPTIONS = [1, 2, 5, 15, 30, 60] as const;

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


export function VolumeChart({
  series,
  fromTimestamp,
  toTimestamp,
  globalWindowMinutes,
  diagnosisBaseQuery,
}: {
  series: OverviewBucket[];
  fromTimestamp: string;
  toTimestamp: string;
  globalWindowMinutes: number;
  diagnosisBaseQuery?: Record<string, string>;
}) {
  const router = useRouter();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [chartSpanMinutes, setChartSpanMinutes] = useState(0);
  const [stepMinutes, setStepMinutes] = useState<(typeof STEP_OPTIONS)[number]>(1);
  const [chartContainerWidth, setChartContainerWidth] = useState(0);
  const [tip, setTip] = useState<{
    bucket: OverviewBucket;
    left: number;
    top: number;
    errRatio: number;
    containerWidth: number;
  } | null>(null);
  const [hoveredColumnIndex, setHoveredColumnIndex] = useState<number | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const displayed = useMemo(() => {
    const trimmed =
      chartSpanMinutes <= 0
        ? [...series].sort((a, b) => a.minute.localeCompare(b.minute))
        : trimSeriesToLastMinutes(series, chartSpanMinutes);
    return aggregateSeriesByStep(trimmed, stepMinutes);
  }, [series, chartSpanMinutes, stepMinutes]);

  const max = maxBucketRequestCount(displayed);

  const onBarMove = useCallback((e: React.MouseEvent<SVGRectElement>, bucket: OverviewBucket) => {
      const el = wrapRef.current;
      if (!el) {
        return;
      }
      const rect = el.getBoundingClientRect();
      const rc = Number(bucket.request_count || 0);
      const ec = Number(bucket.error_count || 0);
      const errRatio = rc ? ec / rc : 0;
      setTip({
        bucket,
        left: e.clientX - rect.left,
        top: e.clientY - rect.top,
        errRatio,
        containerWidth: rect.width,
      });
  }, []);

  const liveTip = useMemo(() => {
    if (!tip) {
      return null;
    }
    const updatedBucket = displayed.find((bucket) => bucket.minute === tip.bucket.minute);
    if (!updatedBucket) {
      return null;
    }
    const requestCount = Number(updatedBucket.request_count || 0);
    const errorCount = Number(updatedBucket.error_count || 0);
    return {
      ...tip,
      bucket: updatedBucket,
      errRatio: requestCount > 0 ? errorCount / requestCount : 0,
    };
  }, [displayed, tip]);

  const activeHoveredColumnIndex =
    hoveredColumnIndex !== null && hoveredColumnIndex < displayed.length ? hoveredColumnIndex : null;

  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el) {
      return;
    }
    const updateWidth = () => {
      setChartContainerWidth(Math.max(0, el.clientWidth));
    };
    updateWidth();
    const observer = new ResizeObserver(() => updateWidth());
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const barGap = 3.5;
  const outerHorizontalPadding = 16;
  const availablePlotWidth = Math.max(0, chartContainerWidth - outerHorizontalPadding);
  const fitBarWidth =
    displayed.length > 0
      ? Math.max(
          2,
          Math.min(32, (availablePlotWidth - barGap * Math.max(0, displayed.length - 1)) / displayed.length),
        )
      : 2;
  const barWidth = Number.isFinite(fitBarWidth) ? fitBarWidth : 2;
  const chartHeight = 52 * 1.5;
  const computedPlotWidth = displayed.length * barWidth + Math.max(0, displayed.length - 1) * barGap;
  const plotWidth = Math.max(160, computedPlotWidth);
  const totalRequests = displayed.reduce((sum, bucket) => sum + Number(bucket.request_count || 0), 0);
  const totalErrors = displayed.reduce((sum, bucket) => sum + Number(bucket.error_count || 0), 0);
  const overallErrorRatePct = totalRequests > 0 ? (totalErrors / totalRequests) * 100 : 0;
  const onBucketClick = useCallback(
    (bucket: OverviewBucket) => {
      const bucketStart = parseIsoTimestamp(bucket.minute).toISOString();
      const bucketEnd = new Date(parseIsoTimestamp(bucket.minute).getTime() + stepMinutes * 60_000).toISOString();
      const params = new URLSearchParams(diagnosisBaseQuery ?? {});
      params.set("from_timestamp", bucketStart);
      params.set("to_timestamp", bucketEnd);
      params.set("error_group_sort", "count");
      const query = params.toString();
      router.push(`/diagnosis?${query}#grouped-errors`);
    },
    [diagnosisBaseQuery, router, stepMinutes],
  );

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <p className="text-sm text-slate-500 dark:text-neutral-400">
          Server window {formatMinuteLabel(fromTimestamp)} → {formatMinuteLabel(toTimestamp)} (
          {globalWindowMinutes}m)
        </p>
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Chart span
            <select
              value={chartSpanMinutes}
              onChange={(e) => setChartSpanMinutes(Number(e.target.value))}
              className="min-w-[160px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
            >
              {CHART_SPAN_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-neutral-300">
            Step (minutes)
            <select
              value={stepMinutes}
              onChange={(e) => setStepMinutes(Number(e.target.value) as (typeof STEP_OPTIONS)[number])}
              className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/40 dark:focus:ring-neutral-500/50"
            >
              {STEP_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {m}m buckets
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div ref={wrapRef} className="relative mt-3">
        {!displayed.length ? (
          <div className="flex h-16 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500 dark:border-neutral-700 dark:bg-neutral-900/70 dark:text-neutral-300">
            No buckets in this chart range.
          </div>
        ) : max <= 0 ? (
          <div className="flex h-16 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500 dark:border-neutral-700 dark:bg-neutral-900/70 dark:text-neutral-300">
            No request volume in these buckets.
          </div>
        ) : (
          <>
            <div
              ref={chartContainerRef}
              className="overflow-x-auto rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-3 dark:border-neutral-700 dark:from-neutral-900 dark:to-neutral-950"
              role="img"
              aria-label="Request volume by time bucket"
            >
              <svg
                width={plotWidth}
                height={chartHeight}
                className="block"
                onMouseLeave={() => {
                  setTip(null);
                  setHoveredColumnIndex(null);
                }}
              >
                {displayed.map((bucket, index) => {
                  const requestCount = Number(bucket.request_count || 0);
                  const errorCount = Number(bucket.error_count || 0);
                  const errRatio = requestCount ? errorCount / requestCount : 0;
                  const barColor =
                    errRatio > 0.25 ? "#e11d48" : errRatio > 0 ? "#d97706" : "#737373";
                  const barHeight = Math.max(Math.round((requestCount / max) * chartHeight), 2);
                  const x = index * (barWidth + barGap);
                  const y = chartHeight - barHeight;
                  return (
                    <g key={`${bucket.minute}-${index}`}>
                      {activeHoveredColumnIndex === index ? (
                        <rect
                          x={x - 1}
                          y={0}
                          width={barWidth + 2}
                          height={chartHeight}
                          rx={2}
                          fill="rgba(56, 189, 248, 0.14)"
                          pointerEvents="none"
                        />
                      ) : null}
                      <rect
                        x={x}
                        y={y}
                        width={barWidth}
                        height={barHeight}
                        rx={1}
                        fill={barColor}
                        pointerEvents="none"
                      />
                      <rect
                        x={x}
                        y={0}
                        width={barWidth}
                        height={chartHeight}
                        fill="transparent"
                        className="cursor-pointer"
                        onMouseEnter={(e) => {
                          setHoveredColumnIndex(index);
                          onBarMove(e, bucket);
                        }}
                        onMouseMove={(e) => {
                          setHoveredColumnIndex(index);
                          onBarMove(e, bucket);
                        }}
                        onClick={() => onBucketClick(bucket)}
                      />
                    </g>
                  );
                })}
              </svg>
            </div>
            {liveTip && (
              <div
                className="pointer-events-none absolute z-10 min-w-[200px] max-w-[min(280px,calc(100%-8px))] -translate-x-1/2 -translate-y-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
                style={{
                  left: Math.max(80, Math.min(liveTip.left, liveTip.containerWidth - 80)),
                  top: Math.max(4, liveTip.top - 8),
                }}
              >
                <p className="font-semibold text-slate-900 dark:text-neutral-100">
                  {formatMinuteLabel(liveTip.bucket.minute)}
                </p>
                <p className="mt-1 tabular-nums text-slate-700 dark:text-neutral-300">
                  <span className="font-medium text-slate-900 dark:text-neutral-100">
                    {Number(liveTip.bucket.request_count || 0)}
                  </span>{" "}
                  requests
                </p>
                <p className="tabular-nums text-slate-700 dark:text-neutral-300">
                  <span className="font-medium text-rose-700 dark:text-rose-400">
                    {Number(liveTip.bucket.error_count || 0)}
                  </span>{" "}
                  errors ({(liveTip.errRatio * 100).toFixed(1)}%)
                </p>
                <p className="mt-0.5 tabular-nums text-slate-600 dark:text-neutral-400">
                  Avg latency{" "}
                  <span className="font-medium text-slate-900 dark:text-neutral-100">
                    {Number(liveTip.bucket.avg_latency_ms || 0).toFixed(1)} ms
                  </span>
                </p>
                <p className="mt-1 text-xs leading-snug text-slate-500 dark:text-neutral-400">
                  Bucket start (your local time). Click a bar to open Diagnosis for this bucket.
                </p>
              </div>
            )}
            <div className="mt-3 grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
              <TimeSeriesLineChart
                title="Request Volume Trend"
                values={displayed.map((bucket) => Number(bucket.request_count || 0))}
                labels={displayed.map((bucket) => formatMinuteLabel(bucket.minute))}
                color="#64748b"
                formatValue={(value) => `${Math.round(value)}`}
                summaryLabel="Total"
                summaryValue={totalRequests}
              />
              <TimeSeriesLineChart
                title="Error Rate Trend"
                values={displayed.map((bucket) => {
                  const req = Number(bucket.request_count || 0);
                  const err = Number(bucket.error_count || 0);
                  return req > 0 ? (err / req) * 100 : 0;
                })}
                labels={displayed.map((bucket) => formatMinuteLabel(bucket.minute))}
                color="#f43f5e"
                formatValue={(value) => `${value.toFixed(1)}%`}
                summaryLabel="Window avg"
                summaryValue={overallErrorRatePct}
              />
              <TimeSeriesLineChart
                title="Error Count Trend"
                values={displayed.map((bucket) => Number(bucket.error_count || 0))}
                labels={displayed.map((bucket) => formatMinuteLabel(bucket.minute))}
                color="#d97706"
                formatValue={(value) => `${Math.round(value)}`}
                summaryLabel="Total"
                summaryValue={totalErrors}
              />
              <TimeSeriesLineChart
                title="Latency Trend"
                values={displayed.map((bucket) => Number(bucket.avg_latency_ms || 0))}
                labels={displayed.map((bucket) => formatMinuteLabel(bucket.minute))}
                color="#a3a3a3"
                formatValue={(value) => `${value.toFixed(1)} ms`}
                summaryLabel="Latest"
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
