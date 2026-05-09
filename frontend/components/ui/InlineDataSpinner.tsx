"use client";

import { CardSpinner } from "./CardSpinner";

/**
 * Section-sized card spinner when a slice has no data yet (initial fetch or empty scope).
 */
export function InlineDataSpinner({
  label = "Loading…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return <CardSpinner size="section" label={label} className={className} />;
}
