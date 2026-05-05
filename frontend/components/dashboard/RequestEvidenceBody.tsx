"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { buildDiagnosisPageHref, type DashboardScopedQueryState } from "./dashboardQueryState";
import type { RequestItem } from "./dashboardTypes";

export function RequestEvidenceBody({
  item,
  scopedState,
  headerActions,
}: {
  item: RequestItem;
  scopedState: DashboardScopedQueryState;
  /** Optional actions (e.g. modal header); table rows use the row-level menu instead. */
  headerActions?: ReactNode;
}) {
  const statusClassForDiagnosis = item.status_code >= 500 ? "5" : item.status_code >= 400 ? "4" : "ALL";
  const diagnosisHref = buildDiagnosisPageHref(
    scopedState,
    {
      pathQuery: item.path,
      statusClass: statusClassForDiagnosis,
    },
    "#grouped-errors",
  );

  return (
    <div className="space-y-4 text-sm text-slate-800 dark:text-neutral-200">
      {headerActions ? <div className="flex justify-end border-b border-slate-200 pb-2 dark:border-neutral-700">{headerActions}</div> : null}

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Request</p>
        <p className="mt-1 break-all font-mono text-sm leading-relaxed">
          <span className="font-semibold text-orange-600 dark:text-orange-400">{item.method}</span>{" "}
          <span className="text-slate-900 dark:text-neutral-50">{item.path}</span>
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-neutral-400">
          <span className="tabular-nums">
            <span className="font-medium text-slate-700 dark:text-neutral-300">HTTP</span> {item.status_code}
          </span>
          <span className="tabular-nums">
            <span className="font-medium text-slate-700 dark:text-neutral-300">Latency</span> {item.latency_ms.toFixed(3)} ms
          </span>
          <span>
            <span className="font-medium text-slate-700 dark:text-neutral-300">Service</span> {item.service_name}
          </span>
          <span>
            <span className="font-medium text-slate-700 dark:text-neutral-300">Env</span> {item.environment}
          </span>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="min-w-0 sm:col-span-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Log / error message</p>
          <p className="mt-1 break-words text-slate-900 dark:text-neutral-100">{item.log_message?.trim() ? item.log_message : "—"}</p>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Request id</p>
          <p className="mt-1 break-all font-mono text-xs text-slate-900 dark:text-neutral-100">{item.request_id ?? "— (not reported by SDK)"}</p>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Timestamp (ISO)</p>
          <p className="mt-1 break-all font-mono text-xs text-slate-900 dark:text-neutral-100">{item.timestamp}</p>
        </div>
        {item.event_id != null && Number.isFinite(item.event_id) ? (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Event id</p>
            <p className="mt-1 font-mono text-xs text-slate-900 dark:text-neutral-100">{item.event_id}</p>
          </div>
        ) : null}
        {item.received_at?.trim() ? (
          <div className="min-w-0 sm:col-span-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Received at (ingest)</p>
            <p className="mt-1 break-all font-mono text-xs text-slate-900 dark:text-neutral-100">{item.received_at}</p>
          </div>
        ) : null}
        {item.sdk_version?.trim() ? (
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">SDK version</p>
            <p className="mt-1 font-mono text-xs text-slate-900 dark:text-neutral-100">{item.sdk_version}</p>
          </div>
        ) : null}
        {item.event_kind?.trim() ? (
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Event type</p>
            <p className="mt-1 font-mono text-xs text-slate-900 dark:text-neutral-100">{item.event_kind}</p>
          </div>
        ) : null}
        {item.trace_id?.trim() ? (
          <div className="min-w-0 sm:col-span-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Trace id</p>
            <p className="mt-1 break-all font-mono text-xs text-slate-900 dark:text-neutral-100">{item.trace_id}</p>
          </div>
        ) : null}
        {item.span_id?.trim() ? (
          <div className="min-w-0 sm:col-span-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Span id</p>
            <p className="mt-1 break-all font-mono text-xs text-slate-900 dark:text-neutral-100">{item.span_id}</p>
          </div>
        ) : null}
      </div>

      <div className="border-t border-slate-200 pt-3 dark:border-neutral-700">
        <Link
          href={diagnosisHref}
          className="text-sm font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
        >
          {item.status_code >= 500
            ? "Open errors and diagnosis (5xx on this route)"
            : item.status_code >= 400
              ? "Open errors and diagnosis (4xx on this route)"
              : "Open errors and diagnosis for this route"}
        </Link>
      </div>
    </div>
  );
}
