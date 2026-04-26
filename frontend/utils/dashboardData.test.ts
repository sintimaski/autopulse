import { describe, expect, it } from "vitest";

import {
  computeOperationalSignals,
  M5_ALERT_DEFAULTS,
  maxBucketRequestCount,
  resolveSparklineSeries,
} from "./dashboardData";

describe("resolveSparklineSeries", () => {
  it("prefers overview.series when present", () => {
    const series = [
      { minute: "2026-04-26T10:00:00Z", request_count: 3, error_count: 0, avg_latency_ms: 10 },
    ];
    const overview = { series };
    const requests = {
      items: [{ timestamp: "2026-04-26T10:00:30Z", status_code: 200, latency_ms: 5 }],
    };
    expect(resolveSparklineSeries(overview, requests)).toEqual(series);
  });

  it("aggregates request rows by minute when overview series is empty", () => {
    const overviewEmpty = { series: [] };
    const requests = {
      items: [
        { timestamp: "2026-04-26T10:00:10Z", status_code: 200, latency_ms: 10 },
        { timestamp: "2026-04-26T10:00:40Z", status_code: 500, latency_ms: 20 },
        { timestamp: "2026-04-26T10:00:50Z", status_code: 503, latency_ms: 30 },
      ],
    };
    const result = resolveSparklineSeries(overviewEmpty, requests);
    expect(result).toHaveLength(1);
    expect(result[0].minute).toBe("2026-04-26T10:00:00.000Z");
    expect(result[0].request_count).toBe(3);
    expect(result[0].error_count).toBe(2);
  });

  it("returns empty when no overview series and no requests", () => {
    expect(resolveSparklineSeries(null, null)).toEqual([]);
    expect(resolveSparklineSeries({ series: [] }, { items: [] })).toEqual([]);
  });
});

describe("maxBucketRequestCount", () => {
  it("returns 0 for empty series", () => {
    expect(maxBucketRequestCount([])).toBe(0);
  });

  it("handles string counts defensively", () => {
    const series = [
      { minute: "a", request_count: 2 as unknown as number, error_count: 0, avg_latency_ms: 0 },
      { minute: "b", request_count: "5" as unknown as number, error_count: 0, avg_latency_ms: 0 },
    ];
    expect(maxBucketRequestCount(series)).toBe(5);
  });
});

describe("computeOperationalSignals", () => {
  const d = M5_ALERT_DEFAULTS;

  it("returns false signals when overview is null", () => {
    expect(computeOperationalSignals(null, d)).toEqual({
      errorSpikeCandidate: false,
      outageCandidate: false,
      successfulRequests: 0,
    });
  });

  it("flags error spike when volume and rate exceed thresholds", () => {
    const overview = {
      request_count: 25,
      error_count: 12,
      error_rate: 12 / 25,
    };
    const signals = computeOperationalSignals(overview, d);
    expect(signals.errorSpikeCandidate).toBe(true);
    expect(signals.successfulRequests).toBe(13);
    expect(signals.outageCandidate).toBe(false);
  });

  it("flags possible outage when enough traffic and no successes", () => {
    const overview = {
      request_count: 12,
      error_count: 12,
      error_rate: 1,
    };
    const signals = computeOperationalSignals(overview, d);
    expect(signals.outageCandidate).toBe(true);
    expect(signals.successfulRequests).toBe(0);
  });
});
