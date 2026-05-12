import type { OverviewBucket } from "./dashboardData";
import { parseDashboardInstantUtcMs } from "./dashboardData";

export type ReleaseMarkerTime = { at: string };

/**
 * Map a release marker instant to a fractional index along `displayed` buckets
 * (same layout as {@link aggregateSeriesByStep} output: each bucket spans `stepMinutes`
 * from its `minute` ISO start).
 */
export function fractionalIndexForReleaseMarker(
  displayed: OverviewBucket[],
  stepMinutes: number,
  markerAtIso: string,
): number | null {
  if (!displayed.length) {
    return null;
  }
  const T = parseDashboardInstantUtcMs(markerAtIso);
  if (!Number.isFinite(T)) {
    return null;
  }
  const step = Math.max(1, Math.floor(stepMinutes));
  const spanMs = step * 60_000;

  for (let i = 0; i < displayed.length; i++) {
    const start = parseDashboardInstantUtcMs(displayed[i].minute);
    if (!Number.isFinite(start)) {
      continue;
    }
    const end = start + spanMs;
    const last = i === displayed.length - 1;
    const inBucket = last ? T >= start && T <= end : T >= start && T < end;
    if (inBucket) {
      const fracAlong = (T - start) / spanMs;
      return i + Math.min(1, Math.max(0, fracAlong));
    }
  }
  return null;
}

/** Stable dedupe so many markers in one bucket draw a single line. */
export function uniqueReleaseMarkerFractions(
  displayed: OverviewBucket[],
  stepMinutes: number,
  markers: readonly ReleaseMarkerTime[],
): number[] {
  const raw: number[] = [];
  for (const m of markers) {
    const f = fractionalIndexForReleaseMarker(displayed, stepMinutes, m.at);
    if (f !== null) {
      raw.push(f);
    }
  }
  const rounded = raw.map((f) => Math.round(f * 2000) / 2000);
  return [...new Set(rounded)].sort((a, b) => a - b);
}
