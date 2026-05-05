"use client";

import Link from "next/link";

import type { RecentJobFailuresResponse } from "./dashboardTypes";
import { formatTimestamp } from "./dashboardTypes";

type RecentJobFailuresStripProps = {
  data: RecentJobFailuresResponse | null;
  /** Optional link shown when failures exist (e.g. scoped diagnosis URL). */
  moreHref?: string;
  moreLabel?: string;
};

export function RecentJobFailuresStrip({ data, moreHref, moreLabel }: RecentJobFailuresStripProps) {
  if (!data?.items?.length) {
    return null;
  }
  return (
    <section
      className="rounded-xl border border-amber-200/80 bg-amber-50/90 p-4 text-sm text-amber-950 shadow-sm ring-1 ring-amber-900/10 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-100 dark:ring-amber-500/10"
      aria-label="Recent background job failures"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-tight">Background jobs and cron</h3>
        {moreHref ? (
          <Link
            href={moreHref}
            className="text-xs font-medium text-amber-900 underline-offset-2 hover:underline dark:text-amber-200"
          >
            {moreLabel ?? "Open diagnosis"}
          </Link>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-amber-900/80 dark:text-amber-200/80">
        Failures from SDK <code className="rounded bg-amber-100/80 px-1 py-0.5 text-[11px] dark:bg-amber-900/60">capture_background_job</code>{" "}
        (HTTP traffic charts stay unchanged).
      </p>
      <ul className="mt-3 space-y-2">
        {data.items.map((item) => (
          <li
            key={`${item.timestamp}-${item.job_name}-${item.status_code}`}
            className="flex flex-col gap-0.5 rounded-lg border border-amber-200/60 bg-white/60 px-3 py-2 dark:border-amber-800/50 dark:bg-neutral-900/40"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-medium text-amber-950 dark:text-amber-50">{item.job_name}</span>
              <span className="text-amber-800/90 dark:text-amber-200/90">
                {item.trigger} · {item.status_code} · {item.latency_ms.toFixed(1)} ms
              </span>
            </div>
            <div className="text-[11px] text-amber-900/70 dark:text-amber-200/70">
              {formatTimestamp(item.timestamp)} · {item.service_name} / {item.environment}
              {item.correlated_request_id ? (
                <>
                  {" "}
                  · request <code className="rounded bg-amber-100/80 px-1 dark:bg-amber-900/60">{item.correlated_request_id}</code>
                </>
              ) : null}
            </div>
            {item.message ? (
              <p className="text-[11px] leading-snug text-rose-800 dark:text-rose-200">{item.message}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
