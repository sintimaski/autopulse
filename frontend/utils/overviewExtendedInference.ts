import type { OverviewExtendedResponse, OverviewResponse, RequestItem, RequestsResponse } from "../components/dashboard/dashboardTypes";

function quantileSorted(sorted: number[], q: number): number {
  if (!sorted.length) {
    return 0;
  }
  if (sorted.length === 1) {
    return sorted[0]!;
  }
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  const h = pos - lo;
  return sorted[lo]! * (1 - h) + sorted[hi]! * h;
}

function apdexFromLatencies(latencies: number[]): number {
  if (!latencies.length) {
    return 1;
  }
  let sum = 0;
  for (const ms of latencies) {
    if (ms <= 300) {
      sum += 1;
    } else if (ms <= 1200) {
      sum += 0.5;
    }
  }
  return sum / latencies.length;
}

/**
 * When `/dashboard/query` omits `overview_extended` (stale snapshot) or DuckDB returns all-zero
 * percentiles despite traffic, derive p50/p95/p99, bursts, and session estimate from the loaded
 * request sample so home cards are not stuck at 0.
 */
export function resolveOverviewExtendedForHome(
  overview: OverviewResponse,
  requests: RequestsResponse | null,
  overviewExtended: OverviewExtendedResponse | null,
): OverviewExtendedResponse {
  const shell = (): OverviewExtendedResponse => ({
    server_now: overview.server_now,
    from_timestamp: overview.from_timestamp,
    to_timestamp: overview.to_timestamp,
    p50_latency_ms: overview.avg_latency_ms,
    p95_latency_ms: overview.avg_latency_ms,
    p99_latency_ms: overview.avg_latency_ms,
    apdex_score: 1,
    active_sessions_estimate: 0,
    error_burst_count: 0,
    active_incident_count: 0,
    error_type_breakdown: [],
    alerts_timeline: [],
    service_breakdown: [],
    route_breakdown: [],
  });

  const base = overviewExtended ?? shell();
  const items = requests?.items ?? [];
  const latencies = items
    .map((x) => Number(x.latency_ms))
    .filter((n) => Number.isFinite(n) && n >= 0)
    .sort((a, b) => a - b);

  const percentilesLookWrong =
    overview.request_count > 0 &&
    base.p50_latency_ms === 0 &&
    base.p95_latency_ms === 0 &&
    base.p99_latency_ms === 0;

  const shouldInferPercentiles =
    latencies.length > 0 && (!overviewExtended || percentilesLookWrong);

  const toMs = Date.parse(overview.to_timestamp);
  const burstFrom = Number.isFinite(toMs) ? toMs - 5 * 60 * 1000 : NaN;
  const errorBurstFromSample = Number.isFinite(burstFrom)
    ? items.filter(
        (r: RequestItem) =>
          r.status_code >= 500 &&
          Number.isFinite(Date.parse(r.timestamp)) &&
          Date.parse(r.timestamp) >= (burstFrom as number),
      ).length
    : items.filter((r: RequestItem) => r.status_code >= 500).length;

  const sessionKeys = new Set<string>();
  for (const r of items) {
    if (r.request_id && String(r.request_id).trim()) {
      sessionKeys.add(String(r.request_id));
    }
  }

  if (!shouldInferPercentiles && items.length === 0) {
    return base;
  }

  const mergedBursts = items.length > 0 ? Math.max(base.error_burst_count, errorBurstFromSample) : base.error_burst_count;

  return {
    ...base,
    ...(shouldInferPercentiles
      ? {
          p50_latency_ms: quantileSorted(latencies, 0.5),
          p95_latency_ms: quantileSorted(latencies, 0.95),
          p99_latency_ms: quantileSorted(latencies, 0.99),
          apdex_score: apdexFromLatencies(latencies),
        }
      : {}),
    ...(items.length > 0
      ? {
          active_sessions_estimate: Math.max(base.active_sessions_estimate, sessionKeys.size),
          error_burst_count: mergedBursts,
          active_incident_count: Math.max(base.active_incident_count, mergedBursts > 0 ? 1 : 0),
        }
      : {}),
  };
}
