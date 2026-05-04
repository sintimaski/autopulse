/**
 * Pure helpers for dashboard metrics (unit-tested; no React imports).
 */

export type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
  count_2xx?: number;
  count_3xx?: number;
  count_4xx?: number;
  count_5xx?: number;
};

export type OverviewForSparkline = {
  series?: OverviewBucket[];
  /** When set with `to_timestamp`, gap-fill spans the full dashboard window (not only buckets present). */
  from_timestamp?: string;
  to_timestamp?: string;
} | null;

export type RequestItemForSparkline = {
  timestamp: string;
  status_code: number;
  latency_ms: number;
};

export type RequestsForSparkline = {
  items: RequestItemForSparkline[];
} | null;

export const M5_ALERT_DEFAULTS = {
  errorSpikeRatioThreshold: 0.4,
  errorSpikeMinRequests: 20,
  outageMinRequests: 10,
  retentionRawDays: 14,
} as const;

export type OverviewForSignals = {
  request_count: number;
  error_count: number;
  error_rate: number;
} | null;

function emptyBucket(minute: string): OverviewBucket {
  return {
    minute,
    request_count: 0,
    error_count: 0,
    avg_latency_ms: 0,
    count_2xx: 0,
    count_3xx: 0,
    count_4xx: 0,
    count_5xx: 0,
  };
}

/** Parse API instants as UTC when no zone suffix is present (matches backend UTC semantics). */
export function parseDashboardInstantUtcMs(raw: string): number {
  const t = raw.trim();
  if (!t) {
    return Number.NaN;
  }
  if (/z$|[+-]\d{2}:?\d{2}$/i.test(t)) {
    return Date.parse(t);
  }
  return Date.parse(`${t}Z`);
}

function truncateUtcToMinuteWall(ms: number): string {
  const d = new Date(ms);
  return new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes(), 0, 0),
  ).toISOString();
}

function normalizeMinuteIso(minute: string): string {
  const parsedMs = parseDashboardInstantUtcMs(minute);
  if (!Number.isFinite(parsedMs)) {
    return minute;
  }
  return truncateUtcToMinuteWall(parsedMs);
}

function parseUtcMsFlooredToMinuteWall(iso: string): number | null {
  const raw = iso.trim();
  if (!raw) {
    return null;
  }
  const ms = parseDashboardInstantUtcMs(raw);
  if (!Number.isFinite(ms)) {
    return null;
  }
  return Math.floor(ms / 60_000) * 60_000;
}

function fillMinuteBucketGaps(
  series: OverviewBucket[],
  windowFromIso?: string,
  windowToIso?: string,
): OverviewBucket[] {
  if (!series.length) {
    return [];
  }
  const normalized = series.map((bucket) => ({
    ...bucket,
    minute: normalizeMinuteIso(bucket.minute),
  }));
  const sorted = normalized.sort((a, b) => a.minute.localeCompare(b.minute));
  const byMinute = new Map(sorted.map((bucket) => [bucket.minute, bucket]));
  let startMs = parseDashboardInstantUtcMs(sorted[0].minute);
  let endMs = parseDashboardInstantUtcMs(sorted[sorted.length - 1].minute);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || startMs > endMs) {
    return sorted;
  }

  const winStart = windowFromIso ? parseUtcMsFlooredToMinuteWall(windowFromIso) : null;
  const winEnd = windowToIso ? parseUtcMsFlooredToMinuteWall(windowToIso) : null;
  if (winStart !== null) {
    startMs = winStart;
  }
  if (winEnd !== null) {
    endMs = winEnd;
  }
  if (startMs > endMs) {
    return sorted;
  }

  const out: OverviewBucket[] = [];
  for (let ts = startMs; ts <= endMs; ts += 60_000) {
    const minute = new Date(ts).toISOString();
    out.push(byMinute.get(minute) ?? emptyBucket(minute));
  }
  return out;
}

export function resolveSparklineSeries(
  overview: OverviewForSparkline,
  requests: RequestsForSparkline,
  options?: { preferRequests?: boolean },
): OverviewBucket[] {
  const preferRequests = options?.preferRequests ?? false;
  if (!preferRequests && overview?.series?.length) {
    return fillMinuteBucketGaps(
      overview.series,
      overview.from_timestamp,
      overview.to_timestamp,
    );
  }
  if (!requests?.items?.length) {
    return overview?.series?.length ? overview.series : [];
  }
  const buckets = new Map<string, OverviewBucket>();
  for (const item of requests.items) {
    const ts = parseDashboardInstantUtcMs(item.timestamp);
    if (!Number.isFinite(ts)) {
      continue;
    }
    const key = truncateUtcToMinuteWall(ts);
    const existing = buckets.get(key);
    if (existing) {
      existing.request_count += 1;
      if (item.status_code >= 500) {
        existing.error_count += 1;
      }
      const statusClass = Math.floor(Number(item.status_code || 0) / 100);
      if (statusClass === 2) {
        existing.count_2xx = Number(existing.count_2xx || 0) + 1;
      } else if (statusClass === 3) {
        existing.count_3xx = Number(existing.count_3xx || 0) + 1;
      } else if (statusClass === 4) {
        existing.count_4xx = Number(existing.count_4xx || 0) + 1;
      } else if (statusClass === 5) {
        existing.count_5xx = Number(existing.count_5xx || 0) + 1;
      }
      continue;
    }
    const statusClass = Math.floor(Number(item.status_code || 0) / 100);
    buckets.set(key, {
      minute: key,
      request_count: 1,
      error_count: item.status_code >= 500 ? 1 : 0,
      avg_latency_ms: item.latency_ms,
      count_2xx: statusClass === 2 ? 1 : 0,
      count_3xx: statusClass === 3 ? 1 : 0,
      count_4xx: statusClass === 4 ? 1 : 0,
      count_5xx: statusClass === 5 ? 1 : 0,
    });
  }
  return fillMinuteBucketGaps(
    [...buckets.values()],
    overview?.from_timestamp,
    overview?.to_timestamp,
  );
}

export function maxBucketRequestCount(series: OverviewBucket[]): number {
  if (!series.length) {
    return 0;
  }
  return Math.max(...series.map((b) => Number(b.request_count || 0)));
}

/**
 * Keep buckets in the last `lastMinutes` **ending** at the latest minute in `series`,
 * or — when `clipEndIso` is set — ending at that instant (floored to UTC minute), whichever is later.
 * Aligns sub-charts with the dashboard API window when sparse points would otherwise anchor on last traffic only.
 */
export function trimSeriesToLastMinutes(
  series: OverviewBucket[],
  lastMinutes: number,
  clipEndIso?: string,
): OverviewBucket[] {
  if (!series.length || lastMinutes <= 0) {
    return series;
  }
  const sorted = [...series].sort((a, b) => a.minute.localeCompare(b.minute));
  let endAnchorMs = parseDashboardInstantUtcMs(sorted[sorted.length - 1].minute);
  if (!Number.isFinite(endAnchorMs)) {
    return sorted;
  }
  const clipFloor = clipEndIso?.trim() ? parseUtcMsFlooredToMinuteWall(clipEndIso) : null;
  if (clipFloor !== null) {
    endAnchorMs = Math.max(endAnchorMs, clipFloor);
  }
  const cutoff = endAnchorMs - lastMinutes * 60 * 1000;
  return sorted.filter((b) => {
    const t = parseDashboardInstantUtcMs(b.minute);
    return Number.isFinite(t) && t >= cutoff && t <= endAnchorMs;
  });
}

/**
 * Merge consecutive minute buckets into wider buckets of `stepMinutes` length
 * (UTC epoch-aligned). Latency is a request-count-weighted average per bucket.
 */
export function aggregateSeriesByStep(
  series: OverviewBucket[],
  stepMinutes: number,
): OverviewBucket[] {
  if (!series.length) {
    return [];
  }
  const normalized = fillMinuteBucketGaps(series);
  const step = Math.max(1, Math.floor(stepMinutes));
  if (step === 1) {
    return normalized;
  }
  const sorted = normalized;
  const spanMs = step * 60 * 1000;
  type Acc = {
    rc: number;
    ec: number;
    latWeighted: number;
    c2xx: number;
    c3xx: number;
    c4xx: number;
    c5xx: number;
  };
  const map = new Map<string, Acc>();
  for (const b of sorted) {
    const t = parseDashboardInstantUtcMs(b.minute);
    if (!Number.isFinite(t)) {
      continue;
    }
    const bucketStart = Math.floor(t / spanMs) * spanMs;
    const key = new Date(bucketStart).toISOString();
    const rc = Number(b.request_count || 0);
    const ec = Number(b.error_count || 0);
    const lat = Number(b.avg_latency_ms || 0);
    const c2xx = Number(b.count_2xx || 0);
    const c3xx = Number(b.count_3xx || 0);
    const c4xx = Number(b.count_4xx || 0);
    const c5xx = Number(b.count_5xx || 0);
    const existing = map.get(key);
    if (existing) {
      existing.rc += rc;
      existing.ec += ec;
      existing.latWeighted += lat * rc;
      existing.c2xx += c2xx;
      existing.c3xx += c3xx;
      existing.c4xx += c4xx;
      existing.c5xx += c5xx;
    } else {
      map.set(key, { rc, ec, latWeighted: lat * rc, c2xx, c3xx, c4xx, c5xx });
    }
  }
  const grouped = [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([minute, acc]) => ({
      minute,
      request_count: acc.rc,
      error_count: acc.ec,
      avg_latency_ms: acc.rc > 0 ? acc.latWeighted / acc.rc : 0,
      count_2xx: acc.c2xx,
      count_3xx: acc.c3xx,
      count_4xx: acc.c4xx,
      count_5xx: acc.c5xx,
    }));
  if (!grouped.length) {
    return [];
  }
  const groupedByMinute = new Map(grouped.map((bucket) => [bucket.minute, bucket]));
  const start = parseDashboardInstantUtcMs(grouped[0].minute);
  const end = parseDashboardInstantUtcMs(grouped[grouped.length - 1].minute);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
    return grouped;
  }
  const out: OverviewBucket[] = [];
  for (let ts = start; ts <= end; ts += spanMs) {
    const minute = new Date(ts).toISOString();
    out.push(groupedByMinute.get(minute) ?? emptyBucket(minute));
  }
  return out;
}

export function computeOperationalSignals(
  overview: OverviewForSignals,
  defaults: {
    errorSpikeRatioThreshold: number;
    errorSpikeMinRequests: number;
    outageMinRequests: number;
  },
): {
  errorSpikeCandidate: boolean;
  outageCandidate: boolean;
  successfulRequests: number;
} {
  if (!overview) {
    return {
      errorSpikeCandidate: false,
      outageCandidate: false,
      successfulRequests: 0,
    };
  }
  const successfulRequests = Math.max(overview.request_count - overview.error_count, 0);
  const errorSpikeCandidate =
    overview.request_count >= defaults.errorSpikeMinRequests &&
    overview.error_rate >= defaults.errorSpikeRatioThreshold;
  const outageCandidate =
    overview.request_count >= defaults.outageMinRequests && successfulRequests === 0;
  return { errorSpikeCandidate, outageCandidate, successfulRequests };
}
