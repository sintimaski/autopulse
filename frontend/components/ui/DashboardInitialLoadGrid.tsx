"use client";

import { CardSpinner } from "./CardSpinner";

type TrafficReady = "traffic-full" | "traffic-requests" | "traffic-alerts" | "settings-only";

/**
 * Multi-card loading layout for dashboard routes (avoids a single full-width pulse block).
 */
export function DashboardInitialLoadGrid({ dataReady }: { dataReady: TrafficReady }) {
  if (dataReady === "traffic-full") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <CardSpinner size="compact" label="Overview metrics" />
          <CardSpinner size="compact" label="Request sample" />
          <CardSpinner size="compact" label="Error groups" />
        </div>
        <CardSpinner
          size="section"
          label="Loading charts & diagnosis data…"
          description="Volume, latency, and breakdowns will appear here."
        />
      </div>
    );
  }

  if (dataReady === "traffic-alerts") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <CardSpinner size="compact" label="Traffic window" />
          <CardSpinner size="compact" label="Alert activity" />
        </div>
        <CardSpinner size="section" label="Loading alert delivery & sparkline…" />
      </div>
    );
  }

  if (dataReady === "traffic-requests") {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <CardSpinner size="compact" label="Overview & window" />
          <CardSpinner size="compact" label="Recent requests" />
        </div>
        <CardSpinner size="section" label="Loading tables & metadata…" />
      </div>
    );
  }

  // settings-only
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <CardSpinner size="compact" label="Project & retention" />
      <CardSpinner size="compact" label="Alert delivery" />
    </div>
  );
}
