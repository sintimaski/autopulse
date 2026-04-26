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

  return (
    <>
      <section className="grid gap-4 sm:grid-cols-3">
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Requests / min</h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900">
            {overview.requests_per_minute.toFixed(2)}
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Error rate</h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-rose-600">
            {(overview.error_rate * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">5xx + ingested error events</p>
          <Link
            href="/diagnosis#grouped-errors"
            className="mt-2 inline-block text-xs font-medium text-sky-700 underline-offset-2 hover:underline"
          >
            Open grouped errors
          </Link>
        </article>
        <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avg latency</h3>
          <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900">
            {overview.avg_latency_ms.toFixed(1)}{" "}
            <span className="text-lg font-semibold text-slate-500">ms</span>
          </p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Volume (by minute)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Hover bars for counts, error share, and average latency. Chart span and step only change how
          bars are drawn (same server window as the query bar). For errors and routes, open{" "}
          <Link href="/diagnosis" className="font-medium text-sky-700 underline-offset-2 hover:underline">
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
          />
        </div>
        {overview.series.length === 0 && d.sparklineSeries.length > 0 && (
          <p className="mt-2 text-xs text-amber-700">
            Backend minute series is empty for this range; buckets are derived from the loaded request
            page.
          </p>
        )}
      </section>

      {overview.request_count === 0 ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-amber-900">No traffic in this window yet</h2>
          <p className="mt-1 text-sm text-amber-900/90">
            Send traffic to <code className="rounded bg-amber-100 px-1">POST /ingest</code>, then use
            refresh in the header. You can also validate grouped errors on{" "}
            <Link href="/diagnosis" className="font-medium underline underline-offset-2">
              Diagnosis
            </Link>
            .
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-800">Top failing routes</h2>
            <Link href="/diagnosis" className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline">
              Full diagnosis
            </Link>
          </div>
          {d.topFailingRoutes.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600">No 5xx failures in the current request sample.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {d.topFailingRoutes.map(([path, count]) => (
                <li key={path} className="flex items-start justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-mono text-xs text-slate-800">{path}</span>
                  <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-800">Recent errors</h2>
            <Link
              href="/diagnosis#grouped-errors"
              className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline"
            >
              Grouped list
            </Link>
          </div>
          {d.recentErrorsPreview.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600">No grouped errors in this time window.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {d.recentErrorsPreview.map((item) => (
                <li key={item.group_key} className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2">
                  <p className="text-sm font-medium text-slate-900">
                    {item.exception_type ?? "Error"} <span className="text-slate-500">on</span>{" "}
                    <span className="font-mono text-xs">{item.path}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-slate-600">
                    Last seen {formatTimestamp(item.last_seen)} · Count {item.count}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </>
  );
}
