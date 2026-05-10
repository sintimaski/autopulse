"use client";

import { CardSpinner } from "../../ui/CardSpinner";
import { useDashboardData } from "../DashboardDataContext";
import { DashboardHomeOverviewWidgets } from "./DashboardHomeOverviewWidgets";

type Props = {
  /** When set, only widgets for this backend `page_id` are shown. */
  lockedPageId?: string;
};

export function DashboardBackendWidgetGalleryContent({ lockedPageId }: Props) {
  const d = useDashboardData();
  const widgetResponse = d.dashboardWidgets;

  return (
    <section className="space-y-6">
      {lockedPageId ? (
        <p className="text-sm text-slate-600 dark:text-neutral-400">
          Uses the same server scope as the rest of the console; chart data below follows the selected time window.
        </p>
      ) : (
        <div className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h1 className="text-lg font-semibold text-slate-900 dark:text-neutral-50">Widgets gallery</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-neutral-400">
            Backend-driven widget pages and layout. Define widgets and placement in backend/SDK; this view renders what
            the backend sends.
          </p>
        </div>
      )}

      {widgetResponse ? (
        <DashboardHomeOverviewWidgets
          dashboardWidgets={widgetResponse}
          chartsScopePending={d.chartsScopePending}
          lockedPageId={lockedPageId}
        />
      ) : d.loading && !d.errorMessage ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <CardSpinner size="compact" label="Loading widgets" />
          <CardSpinner size="compact" label="Loading layout" />
        </div>
      ) : (
        <div className="rounded-xl border border-amber-500/30 bg-amber-50/90 p-4 text-sm text-amber-950 dark:border-amber-500/25 dark:bg-amber-950/30 dark:text-amber-100">
          {d.errorMessage ?? "No widget payload returned for this scope yet."}
        </div>
      )}
    </section>
  );
}
