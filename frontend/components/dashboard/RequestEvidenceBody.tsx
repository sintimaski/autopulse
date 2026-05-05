"use client";

import Link from "next/link";

import { buildDiagnosisPageHref, type DashboardScopedQueryState } from "./dashboardQueryState";
import type { RequestItem } from "./dashboardTypes";

export function RequestEvidenceBody({
  item,
  scopedState,
}: {
  item: RequestItem;
  scopedState: DashboardScopedQueryState;
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
    <>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2 rounded-xl border border-slate-200/80 bg-white/80 px-3 py-2.5 dark:border-neutral-700 dark:bg-neutral-950/50">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Request</p>
          <p className="mt-1 break-all font-mono text-sm font-semibold text-slate-900 dark:text-neutral-50">
            <span className="text-orange-600 dark:text-orange-400">{item.method}</span>{" "}
            <span className="text-slate-800 dark:text-neutral-100">{item.path}</span>
          </p>
          <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-neutral-300">
            <span className="tabular-nums">
              <span className="font-medium text-slate-800 dark:text-neutral-200">HTTP</span> {item.status_code}
            </span>
            <span className="tabular-nums">
              <span className="font-medium text-slate-800 dark:text-neutral-200">Latency</span>{" "}
              {item.latency_ms.toFixed(1)} ms
            </span>
            <span>
              <span className="font-medium text-slate-800 dark:text-neutral-200">Service</span> {item.service_name}
            </span>
            <span>
              <span className="font-medium text-slate-800 dark:text-neutral-200">Env</span> {item.environment}
            </span>
          </p>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Request id</dt>
          <dd className="mt-0.5 break-all font-mono text-sm text-slate-900 dark:text-neutral-100">
            {item.request_id ?? "— (not reported by SDK)"}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Timestamp (ISO)</dt>
          <dd className="mt-0.5 break-all font-mono text-sm text-slate-900 dark:text-neutral-100">{item.timestamp}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Log / error message</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900 dark:text-neutral-100">
            {item.log_message?.trim() ? item.log_message : "—"}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Status</dt>
          <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">{item.status_code}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Latency</dt>
          <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">{item.latency_ms.toFixed(3)} ms</dd>
        </div>
        {item.event_id != null && Number.isFinite(item.event_id) ? (
          <div>
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Event id</dt>
            <dd className="mt-0.5 font-mono text-sm text-slate-900 dark:text-neutral-100">{item.event_id}</dd>
          </div>
        ) : null}
        {item.received_at?.trim() ? (
          <div>
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Received at (ingest)</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-slate-900 dark:text-neutral-100">
              {item.received_at}
            </dd>
          </div>
        ) : null}
        {item.sdk_version?.trim() ? (
          <div>
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">SDK version</dt>
            <dd className="mt-0.5 font-mono text-sm text-slate-900 dark:text-neutral-100">{item.sdk_version}</dd>
          </div>
        ) : null}
        {item.event_kind?.trim() ? (
          <div>
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Event type</dt>
            <dd className="mt-0.5 font-mono text-sm text-slate-900 dark:text-neutral-100">{item.event_kind}</dd>
          </div>
        ) : null}
        {item.trace_id?.trim() ? (
          <div className="sm:col-span-2">
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Trace id</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-slate-900 dark:text-neutral-100">{item.trace_id}</dd>
          </div>
        ) : null}
        {item.span_id?.trim() ? (
          <div className="sm:col-span-2">
            <dt className="font-semibold text-slate-500 dark:text-neutral-400">Span id</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-slate-900 dark:text-neutral-100">{item.span_id}</dd>
          </div>
        ) : null}
      </dl>
      <div className="mt-4 border-t border-slate-200 pt-3 dark:border-neutral-700">
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
    </>
  );
}
