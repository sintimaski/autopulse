"use client";

import { useReducer } from "react";

const STORAGE_KEY = "lumonox.dismissedNavMigrationBanner.v1";

function readDismissedFromStorage(): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function NavIaMigrationBanner() {
  const [, rerender] = useReducer((n: number) => n + 1, 0);

  if (readDismissedFromStorage()) {
    return null;
  }

  return (
    <div
      role="status"
      className="mx-2 mb-2 rounded-lg border border-sky-500/35 bg-sky-950/40 px-2.5 py-2 text-[11px] leading-snug text-sky-100 shadow-sm dark:border-sky-400/25 dark:bg-sky-950/60"
    >
      <div className="flex items-start justify-between gap-2">
        <p>
          <span className="font-semibold text-white">Progressive disclosure:</span> the primary path stays Overview →
          Diagnosis → Requests. Query Explorer and Traces are under{" "}
          <span className="font-medium">Advanced</span> for power users only.
        </p>
        <button
          type="button"
          onClick={() => {
            try {
              window.localStorage.setItem(STORAGE_KEY, "1");
            } catch {
              /* ignore */
            }
            rerender();
          }}
          className="shrink-0 rounded-md border border-white/20 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
