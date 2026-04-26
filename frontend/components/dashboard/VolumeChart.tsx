"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import type { OverviewBucket } from "../../utils/dashboardData";
import {
  aggregateSeriesByStep,
  maxBucketRequestCount,
  trimSeriesToLastMinutes,
} from "../../utils/dashboardData";

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
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function VolumeChart({
  series,
  fromTimestamp,
  toTimestamp,
  globalWindowMinutes,
}: {
  series: OverviewBucket[];
  fromTimestamp: string;
  toTimestamp: string;
  globalWindowMinutes: number;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [chartSpanMinutes, setChartSpanMinutes] = useState(0);
  const [stepMinutes, setStepMinutes] = useState<(typeof STEP_OPTIONS)[number]>(1);
  const [tip, setTip] = useState<{
    bucket: OverviewBucket;
    left: number;
    top: number;
    errRatio: number;
    containerWidth: number;
  } | null>(null);

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

  const barWidth = 16;
  const barGap = 4;
  const chartHeight = 52;
  const plotWidth = Math.max(displayed.length * (barWidth + barGap), 160);

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <p className="text-xs text-slate-500">
          Server window {formatMinuteLabel(fromTimestamp)} → {formatMinuteLabel(toTimestamp)} (
          {globalWindowMinutes}m)
        </p>
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Chart span
            <select
              value={chartSpanMinutes}
              onChange={(e) => setChartSpanMinutes(Number(e.target.value))}
              className="min-w-[160px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-sky-500/30 focus:ring-2"
            >
              {CHART_SPAN_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            Step (minutes)
            <select
              value={stepMinutes}
              onChange={(e) => setStepMinutes(Number(e.target.value) as (typeof STEP_OPTIONS)[number])}
              className="min-w-[120px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none ring-sky-500/30 focus:ring-2"
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
          <div className="flex h-16 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500">
            No buckets in this chart range.
          </div>
        ) : max <= 0 ? (
          <div className="flex h-16 items-center rounded-xl border border-slate-200/80 bg-white/60 px-3 text-sm text-slate-500">
            No request volume in these buckets.
          </div>
        ) : (
          <>
            <div
              className="overflow-x-auto rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-2"
              role="img"
              aria-label="Request volume by time bucket"
            >
              <svg
                width={plotWidth}
                height={chartHeight}
                className="block"
                onMouseLeave={() => setTip(null)}
              >
                {displayed.map((bucket, index) => {
                  const requestCount = Number(bucket.request_count || 0);
                  const errorCount = Number(bucket.error_count || 0);
                  const errRatio = requestCount ? errorCount / requestCount : 0;
                  const barColor =
                    errRatio > 0.25 ? "#e11d48" : errRatio > 0 ? "#f59e0b" : "#0284c7";
                  const barHeight = Math.max(Math.round((requestCount / max) * chartHeight), 2);
                  const x = index * (barWidth + barGap);
                  const y = chartHeight - barHeight;
                  return (
                    <rect
                      key={`${bucket.minute}-${index}`}
                      x={x}
                      y={y}
                      width={barWidth}
                      height={barHeight}
                      rx={1}
                      fill={barColor}
                      className="cursor-crosshair"
                      onMouseEnter={(e) => onBarMove(e, bucket)}
                      onMouseMove={(e) => onBarMove(e, bucket)}
                    />
                  );
                })}
              </svg>
            </div>
            {tip && (
              <div
                className="pointer-events-none absolute z-10 min-w-[200px] max-w-[min(280px,calc(100%-8px))] -translate-x-1/2 -translate-y-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
                style={{
                  left: Math.max(80, Math.min(tip.left, tip.containerWidth - 80)),
                  top: Math.max(4, tip.top - 8),
                }}
              >
                <p className="font-semibold text-slate-900">{formatMinuteLabel(tip.bucket.minute)}</p>
                <p className="mt-1 tabular-nums text-slate-700">
                  <span className="font-medium text-slate-900">{Number(tip.bucket.request_count || 0)}</span>{" "}
                  requests
                </p>
                <p className="tabular-nums text-slate-700">
                  <span className="font-medium text-rose-700">{Number(tip.bucket.error_count || 0)}</span>{" "}
                  errors ({(tip.errRatio * 100).toFixed(1)}%)
                </p>
                <p className="mt-0.5 tabular-nums text-slate-600">
                  Avg latency{" "}
                  <span className="font-medium text-slate-900">
                    {Number(tip.bucket.avg_latency_ms || 0).toFixed(1)} ms
                  </span>
                </p>
                <p className="mt-1 text-[10px] leading-snug text-slate-500">
                  Bucket start (UTC). Color hints error share in the bucket.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
