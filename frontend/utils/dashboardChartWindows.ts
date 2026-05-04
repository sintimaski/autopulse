/**
 * Dashboard chart selects (traffic volume, host resources) must stay within the
 * main server query window so users cannot pick a "last 24h" view when only 15m
 * of data was loaded.
 */

/** Descending preset spans shown as "Last …" (strictly less than main window). */
const CHART_SPAN_PRESETS_DESC = [
  1440, 720, 480, 360, 240, 180, 120, 90, 60, 45, 30, 15, 10, 5, 2, 1,
] as const;

/** Roll-up bucket sizes (minutes), excluding native (0). */
const ROLLUP_BUCKET_PRESETS_DESC = [60, 30, 15, 5, 1] as const;

/** Traffic volume bar chart: cap bucket count so Chart.js / DOM stay responsive. */
export const VOLUME_CHART_TARGET_MAX_BUCKETS = 144;

/**
 * Minute step sizes for traffic volume aggregation (ascending).
 * Kept dense at the low end for short windows; wider gaps at the high end for multi-hour spans.
 */
export const VOLUME_STEP_CANDIDATES: readonly number[] = [
  1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 480, 720, 1440,
];

/**
 * Allowed step (minutes) for volume charts: fits the effective span and keeps
 * `span / step` roughly under {@link VOLUME_CHART_TARGET_MAX_BUCKETS}.
 */
export function buildVolumeStepOptions(effectiveSpanMinutes: number): number[] {
  const span = Math.max(1, Math.floor(Number(effectiveSpanMinutes) || 1));
  const minStep = Math.max(1, Math.ceil(span / VOLUME_CHART_TARGET_MAX_BUCKETS));
  const allowed = VOLUME_STEP_CANDIDATES.filter((s) => s <= span && s >= minStep);
  if (!allowed.length) {
    return [span];
  }
  return allowed;
}

/** Aim for ~24 bars by default (coarser than 1m when the span allows it). */
const DEFAULT_VOLUME_STEP_TARGET_BUCKETS = 24;

/**
 * Default "Step (minutes)" for traffic volume: first allowed step that keeps the
 * bucket count roughly under {@link DEFAULT_VOLUME_STEP_TARGET_BUCKETS}, when possible.
 */
export function defaultVolumeStepMinutes(effectiveSpanMinutes: number, allowedSteps: readonly number[]): number {
  if (!allowedSteps.length) {
    return 1;
  }
  const span = Math.max(1, Math.floor(Number(effectiveSpanMinutes) || 1));
  const ideal = Math.max(2, Math.ceil(span / DEFAULT_VOLUME_STEP_TARGET_BUCKETS));
  const atOrAbove = allowedSteps.filter((s) => s >= ideal);
  if (atOrAbove.length > 0) {
    return atOrAbove[0]!;
  }
  return allowedSteps[allowedSteps.length - 1]!;
}

export function formatMinutesForUi(minutes: number): string {
  const m = Math.max(1, Math.floor(Number(minutes) || 1));
  if (m % 1440 === 0) {
    const d = m / 1440;
    return d === 1 ? "24h" : `${d}d`;
  }
  if (m % 60 === 0) {
    const h = m / 60;
    return h === 1 ? "1h" : `${h}h`;
  }
  return `${m}m`;
}

export function buildAlignedChartSpanOptions(mainWindowMinutes: number): { value: number; label: string }[] {
  const cap = Math.max(1, Math.floor(Number(mainWindowMinutes) || 1));
  const full = {
    value: 0,
    label: `Full loaded range (${formatMinutesForUi(cap)})`,
  };
  const subsAsc = CHART_SPAN_PRESETS_DESC.filter((n) => n < cap).sort((a, b) => a - b);
  const subs = subsAsc.map((n) => ({
    value: n,
    label: `Last ${formatMinutesForUi(n)}`,
  }));
  return [...subs, full];
}

export function rollupBucketLabel(minutes: number): string {
  if (minutes === 60) {
    return "1 hour";
  }
  if (minutes === 1) {
    return "1 minute";
  }
  return `${minutes} minutes`;
}

export function buildAlignedRollupBucketOptions(maxMinutes: number): { value: number; label: string }[] {
  const cap = Math.max(1, Math.floor(Number(maxMinutes) || 1));
  const native = { value: 0, label: "Native (per sample)" };
  const bucketsAsc = ROLLUP_BUCKET_PRESETS_DESC.filter((n) => n <= cap).sort((a, b) => a - b);
  const buckets = bucketsAsc.map((n) => ({
    value: n,
    label: rollupBucketLabel(n),
  }));
  return [native, ...buckets];
}
