"use client";

import { dashboardSpinnerRingClassName } from "../../ui/CardSpinner";

/**
 * In-chart loading layer: light tint + centered spinner (not a modal).
 * Parent should be `position: relative` with bounded height.
 */
export function ChartScopeTintOverlay({ className = "" }: { className?: string }) {
  return (
    <div
      className={`pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-[inherit] bg-white/35 dark:bg-black/25 ${className}`}
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">Updating chart</span>
      <div className={`h-6 w-6 shrink-0 ${dashboardSpinnerRingClassName}`} aria-hidden />
    </div>
  );
}
