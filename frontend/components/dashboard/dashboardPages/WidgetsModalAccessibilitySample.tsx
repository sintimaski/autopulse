"use client";

import { useState } from "react";

import { DashboardDetailModal } from "../DashboardDetailModal";

/** Small always-mounted demo so Playwright can verify Escape closes `DashboardDetailModal` without live traffic. */
export function WidgetsModalAccessibilitySample() {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="text-base font-semibold text-slate-900 dark:text-neutral-50">Modal keyboard (QA)</h2>
      <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
        Opens the same dialog shell used on Requests and Diagnosis. Escape and the close button should dismiss it.
      </p>
      <button type="button" className="ap-btn mt-3" onClick={() => setOpen(true)}>
        Open sample dialog
      </button>
      <DashboardDetailModal open={open} title="Sample dialog" onClose={() => setOpen(false)} size="md">
        <p className="text-sm text-slate-600 dark:text-neutral-400">
          Press <kbd className="rounded border border-slate-300 bg-slate-100 px-1 dark:border-neutral-600 dark:bg-neutral-800">Escape</kbd>{" "}
          or use the header close control.
        </p>
        <button type="button" className="ap-btn mt-4">
          Extra focus stop (tab trap)
        </button>
      </DashboardDetailModal>
    </div>
  );
}
