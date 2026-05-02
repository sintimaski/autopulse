"use client";

import { DashboardScopeFacetShell } from "../DashboardScopeFacetShell";
import { OverviewScopeFacetBoard } from "../OverviewScopeFacetBoard";

/** Overview home loading / error shell (keeps scope facets visible while traffic hydrates). */
export function DashboardHomeLoadingShell({ message }: { message: string }) {
  return (
    <section className="space-y-4">
      <DashboardScopeFacetShell className="sticky top-0 z-30">
        <OverviewScopeFacetBoard />
      </DashboardScopeFacetShell>
      <div className="rounded-xl border border-slate-200/90 bg-slate-50 p-4 text-sm text-slate-600 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300">
        {message}
      </div>
    </section>
  );
}
