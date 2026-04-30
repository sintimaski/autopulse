"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ChartData, ChartOptions } from "chart.js";

import type { OverviewBucket } from "../../utils/dashboardData";
import {
  aggregateSeriesByStep,
  maxBucketRequestCount,
  trimSeriesToLastMinutes,
} from "../../utils/dashboardData";
import { CanvasBar } from "./charts/chartCanvas";
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
  const [chartSpanMinutes, setChartSpanMinutes] = useState(0);
  const [stepMinutes, setStepMinutes] = useState<(typeof STEP_OPTIONS)[number]>(1);

  const displayed = useMemo(() => {
    const trimmed =
      chartSpanMinutes <= 0
        ? [...series].sort((a, b) => a.minute.localeCompare(b.minute))
        : trimSeriesToLastMinutes(series, chartSpanMinutes);
    return aggregateSeriesByStep(trimmed, stepMinutes);
  }, [series, chartSpanMinutes, stepMinutes]);

  const max = maxBucketRequestCount(displayed);
  const displayedRef = useRef(displayed);
  useEffect(() => {
    displayedRef.current = displayed;
  }, [displayed]);

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
        },
      ],
    };
  }, [displayed]);

  const volumeBarOptions = useMemo<ChartOptions<"bar">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: displayed.length > 80 ? 0 : 380 },
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
    [displayed, max, onBucketClick],
  );

  const barChartHeight = 120;

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

      <div className="relative mt-3">
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
              className="overflow-x-auto rounded-xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50 px-2 py-3 dark:border-neutral-700 dark:from-neutral-900 dark:to-neutral-950"
              role="img"
              aria-label="Request volume by time bucket"
            >
              <div style={{ minWidth: Math.max(320, displayed.length * 8), height: barChartHeight }}>
                <CanvasBar data={volumeBarData} options={volumeBarOptions} />
              </div>
            </div>
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
