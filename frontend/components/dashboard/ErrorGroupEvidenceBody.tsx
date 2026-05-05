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
  headerActions?: ReactNode;
}) {
  return (
    <>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="relative sm:col-span-2 rounded-xl border border-slate-200/80 bg-white/80 px-3 py-2.5 pr-11 dark:border-neutral-700 dark:bg-neutral-950/50">
          {headerActions ? (
            <div className="absolute right-2 top-2 z-10 flex items-start justify-end">{headerActions}</div>
          ) : null}
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-500">Error group</p>
          <p className="mt-1 text-base font-semibold text-rose-700 dark:text-rose-300">{item.exception_type ?? "(unknown)"}</p>
          <p className="mt-1 break-all font-mono text-sm text-slate-800 dark:text-neutral-100">{item.path}</p>
          <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-neutral-300">
            <span className="tabular-nums">
              <span className="font-medium text-slate-800 dark:text-neutral-200">Count</span> {item.count}
            </span>
            <span className="text-xs sm:text-sm">Last seen: {formatTimestamp(item.last_seen)}</span>
          </p>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Request logs</dt>
          <dd className="mt-1">
            <Link
              href={buildRequestsPageHref(scopedState, {
                pathQuery: item.path,
                statusClass: "ALL",
              })}
              className="text-sm font-medium text-orange-600 underline-offset-2 hover:underline dark:text-orange-400"
            >
              Open logs for this route
            </Link>
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Group key</dt>
          <dd className="mt-0.5 break-all font-mono text-sm text-slate-800 dark:text-neutral-200">{item.group_key}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Count</dt>
          <dd className="mt-0.5 tabular-nums text-slate-900 dark:text-neutral-100">{item.count}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">First seen</dt>
          <dd className="mt-0.5 text-sm text-slate-700 dark:text-neutral-200">{formatTimestamp(item.first_seen)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Exception message</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900 dark:text-neutral-100">{item.message ?? "(no message)"}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-semibold text-slate-500 dark:text-neutral-400">Sample stack trace</dt>
          {item.sample_stack_trace ? (
            <pre className="mt-1 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-sm leading-6 text-slate-100">
              {item.sample_stack_trace}
            </pre>
          ) : (
            <dd className="mt-0.5 text-sm text-slate-600 dark:text-neutral-300">No stack trace (event had no exception payload).</dd>
          )}
        </div>
      </dl>
    </>
  );
}
