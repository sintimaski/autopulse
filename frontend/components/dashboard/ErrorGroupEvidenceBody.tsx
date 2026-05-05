"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { buildRequestsPageHref, type DashboardScopedQueryState } from "./dashboardQueryState";
import { formatTimestamp, type ErrorGroupItem } from "./dashboardTypes";

export function ErrorGroupEvidenceBody({
  item,
  scopedState,
  headerActions,
}: {
  item: ErrorGroupItem;
  scopedState: DashboardScopedQueryState;
  /** Optional actions (e.g. modal header); table rows use the row-level menu instead. */
  headerActions?: ReactNode;
}) {
  return (
    <div className="space-y-4 text-sm text-slate-800 dark:text-neutral-200">
      {headerActions ? <div className="flex justify-end border-b border-slate-200 pb-2 dark:border-neutral-700">{headerActions}</div> : null}

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Exception</p>
        <p className="mt-1 text-base font-semibold text-rose-700 dark:text-rose-300">{item.exception_type ?? "(unknown)"}</p>
        <p className="mt-1 break-all font-mono text-xs leading-relaxed text-slate-900 dark:text-neutral-100">{item.path}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-neutral-400">
          <span className="tabular-nums">
            <span className="font-medium text-slate-700 dark:text-neutral-300">Count</span> {item.count}
          </span>
          <span>
            <span className="font-medium text-slate-700 dark:text-neutral-300">First</span> {formatTimestamp(item.first_seen)}
          </span>
          <span>
            <span className="font-medium text-slate-700 dark:text-neutral-300">Last</span> {formatTimestamp(item.last_seen)}
          </span>
        </div>
      </div>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Message</p>
        <p className="mt-1 break-words text-slate-900 dark:text-neutral-100">{item.message ?? "(no message)"}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Group key</p>
          <p className="mt-1 break-all font-mono text-xs text-slate-800 dark:text-neutral-200">{item.group_key}</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Request logs</p>
          <Link
            href={buildRequestsPageHref(scopedState, {
              pathQuery: item.path,
              statusClass: "ALL",
            })}
            className="mt-1 inline-block text-sm font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
          >
            Open logs for this route
          </Link>
        </div>
      </div>

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Sample stack trace</p>
        {item.sample_stack_trace ? (
          <pre className="mt-1 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-100">
            {item.sample_stack_trace}
          </pre>
        ) : (
          <p className="mt-1 text-slate-600 dark:text-neutral-400">No stack trace (event had no exception payload).</p>
        )}
      </div>
    </div>
  );
}
