"use client";

import { useDashboardData } from "./DashboardDataContext";

/** Shown when a request correlation filter is active (replaces removed scope pivot bar). */
export function CorrelationClearBar() {
  const d = useDashboardData();
  if (!d.correlationRequestId.trim()) {
    return null;
  }
  return (
    <div className="mb-2 flex justify-end">
      <button
        type="button"
        className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        onClick={() => d.setCorrelationRequestId("")}
      >
        Clear correlation
      </button>
    </div>
  );
}
