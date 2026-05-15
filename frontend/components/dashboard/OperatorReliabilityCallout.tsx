"use client";

import Link from "next/link";

import { DismissibleCard } from "./DismissibleCard";

/** Overview hint: deep-links to Settings panels that mirror ingest / scheduler / retention health. */
export function OperatorReliabilityCallout() {
  return (
    <DismissibleCard
      storageKeyBase="lx-operator-reliability-callout"
      ariaLabel="Dismiss operator reliability hint"
    >
      <section
        className="mb-3 rounded-lg border border-slate-200/80 bg-slate-50/90 px-3 py-2.5 pr-9 text-xs text-slate-700 dark:border-neutral-700 dark:bg-neutral-900/60 dark:text-neutral-300"
        aria-label="Operator pipeline reliability"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-semibold text-slate-800 dark:text-neutral-100">Operator reliability</p>
            <p className="mt-0.5 text-[11px] leading-snug text-slate-600 dark:text-neutral-400">
              Ingest queue, scheduler, and retention freshness live in Settings.
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-1 sm:flex-row sm:items-center">
            <Link
              href="/settings#lx-settings-internal-metrics"
              className="rounded-md border border-slate-300/80 bg-white px-2 py-1 text-[11px] font-medium text-orange-800 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-orange-200 dark:hover:bg-neutral-800/80"
            >
              Internal metrics
            </Link>
            <Link
              href="/settings#lx-settings-system-diagnostics"
              className="rounded-md border border-slate-300/80 bg-white px-2 py-1 text-[11px] font-medium text-orange-800 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-orange-200 dark:hover:bg-neutral-800/80"
            >
              System diagnostics
            </Link>
          </div>
        </div>
      </section>
    </DismissibleCard>
  );
}
