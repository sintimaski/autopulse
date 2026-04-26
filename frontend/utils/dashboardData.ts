/**
 * Pure helpers for dashboard metrics (unit-tested; no React imports).
 */

export type OverviewBucket = {
  minute: string;
  request_count: number;
  error_count: number;
  avg_latency_ms: number;
};

export type OverviewForSparkline = {
  series?: OverviewBucket[];
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

export function resolveSparklineSeries(
  overview: OverviewForSparkline,
  requests: RequestsForSparkline,
): OverviewBucket[] {
  if (overview?.series?.length) {
    return overview.series;
  }
  if (!requests?.items?.length) {
    return [];
  }
  const buckets = new Map<string, OverviewBucket>();
  for (const item of requests.items) {
    const minute = new Date(item.timestamp);
    minute.setSeconds(0, 0);
    const key = minute.toISOString();
    const existing = buckets.get(key);
    if (existing) {
      existing.request_count += 1;
      if (item.status_code >= 500) {
        existing.error_count += 1;
      }
      continue;
    }
    buckets.set(key, {
      minute: key,
      request_count: 1,
      error_count: item.status_code >= 500 ? 1 : 0,
      avg_latency_ms: item.latency_ms,
    });
  }
  return [...buckets.values()].sort((a, b) => a.minute.localeCompare(b.minute));
}

export function maxBucketRequestCount(series: OverviewBucket[]): number {
  if (!series.length) {
    return 0;
  }
  return Math.max(...series.map((b) => Number(b.request_count || 0)));
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
