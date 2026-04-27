"use client";

import Link from "next/link";

import { VolumeChart } from "../VolumeChart";
import { useDashboardData } from "../DashboardDataContext";
import { formatTimestamp } from "../dashboardTypes";

export function DashboardHomeContent() {
  const d = useDashboardData();
  const overview = d.overview;
  const requests = d.requests;
  if (!overview || !requests) {
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
  const diagnosisParams = (() => {
    const params = new URLSearchParams({
      from_timestamp: d.windowFromTimestamp,
      to_timestamp: d.windowToTimestamp,
    });
    if (d.method !== "ALL") {
      params.set("method", d.method);
    }
    if (d.statusClass !== "ALL") {
      params.set("status_class", d.statusClass);
    }
    if (d.pathQuery.trim()) {
      params.set("path_contains", d.pathQuery.trim());
    }
    if (d.minLatencyMs.trim()) {
      params.set("min_latency_ms", d.minLatencyMs.trim());
    }
    if (d.maxLatencyMs.trim()) {
      params.set("max_latency_ms", d.maxLatencyMs.trim());
    }
    const envCsv = d.serverEnvironmentQuery
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .join(",");
    if (envCsv) {
      params.set("environments", envCsv);
    }
    const serviceCsv = d.serverServiceQuery
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .join(",");
    if (serviceCsv) {
      params.set("services", serviceCsv);
    }
    return params;
  })();
  const diagnosisBaseHref = `/diagnosis?${diagnosisParams.toString()}`;
  const diagnosisGroupedHref = `/diagnosis?${(() => {
    const params = new URLSearchParams(diagnosisParams.toString());
    params.set("error_group_sort", "count");
    return params.toString();
  })()}#grouped-errors`;

  return (
    <>
      <section className="grid gap-4 sm:grid-cols-3">
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            Requests / min
          </h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900 dark:text-neutral-100">
            {displayRequestsPerMinute.toFixed(2)}
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            Error rate
          </h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-rose-600 dark:text-rose-400">
            {(displayErrorRate * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
            {usingFilteredSeries
              ? "Derived from current filtered request slice"
              : "5xx + ingested error events"}
          </p>
          <Link
            href={diagnosisGroupedHref}
            className="mt-2 inline-block text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
          >
            Open grouped errors
          </Link>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            Avg latency
          </h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900 dark:text-neutral-100">
            {displayAvgLatencyMs.toFixed(1)}{" "}
            <span className="text-lg font-semibold text-slate-500 dark:text-neutral-400">ms</span>
          </p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Traffic graphs</h2>
        <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
          Requests (bars), plus request/error rate/error count/latency trend cards. Hover bars and trend lines
          for exact values. Click a bar to jump to Diagnosis for that bucket. Chart span and step only change
          how buckets are drawn (same server window as the query bar). For errors and routes, open{" "}
          <Link href={diagnosisBaseHref} className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300">
            Diagnosis
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

      {overview.request_count === 0 ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/30">
          <h2 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
            No traffic in this window yet
          </h2>
          <p className="mt-1 text-sm text-amber-900/90 dark:text-amber-100/90">
            Send traffic to <code className="rounded bg-amber-100 px-1">POST /ingest</code>, then use
            refresh in the header. You can also validate grouped errors on{" "}
            <Link href={diagnosisBaseHref} className="font-medium underline underline-offset-2">
              Diagnosis
            </Link>
            .
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Top failing routes</h2>
            <Link href={diagnosisBaseHref} className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300">
              Full diagnosis
            </Link>
          </div>
          {d.topFailingRoutes.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">
              No 5xx failures in the current request sample.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {d.topFailingRoutes.map(([path, count]) => (
                <li key={path} className="flex items-start justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-mono text-xs text-slate-800 dark:text-neutral-100">
                    {path}
                  </span>
                  <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-900/50 dark:text-rose-300">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Recent errors</h2>
            <Link
              href={diagnosisGroupedHref}
              className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
            >
              Grouped list
            </Link>
          </div>
          {d.recentErrorsPreview.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">
              No grouped errors in this time window.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {d.recentErrorsPreview.map((item) => (
                <li
                  key={item.group_key}
                  className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-800/70"
                >
                  <Link
                    href={`/diagnosis?${(() => {
                      const params = new URLSearchParams(diagnosisParams.toString());
                      params.set("error_group_sort", "count");
                      params.set("path_contains", item.path);
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
        </article>
      </section>
    </>
  );
}
