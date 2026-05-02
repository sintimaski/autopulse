import { describe, expect, it } from "vitest";

import {
  aggregateSeriesByStep,
  computeOperationalSignals,
  M5_ALERT_DEFAULTS,
  maxBucketRequestCount,
  parseDashboardInstantUtcMs,
  resolveSparklineSeries,
  trimSeriesToLastMinutes,
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
    expect(resolveSparklineSeries(overview, requests)).toEqual([
      { minute: "2026-04-26T10:00:00.000Z", request_count: 3, error_count: 0, avg_latency_ms: 10 },
    ]);
  });

  it("fills minute gaps when overview series is sparse", () => {
    const overview = {
      series: [
        { minute: "2026-04-26T10:00:00.000Z", request_count: 2, error_count: 0, avg_latency_ms: 10 },
        { minute: "2026-04-26T10:02:00.000Z", request_count: 1, error_count: 1, avg_latency_ms: 30 },
      ],
    };
    const out = resolveSparklineSeries(overview, null);
    expect(out).toHaveLength(3);
    expect(out[1]).toMatchObject({
      minute: "2026-04-26T10:01:00.000Z",
      request_count: 0,
      error_count: 0,
      avg_latency_ms: 0,
    });
  });

  it("treats zone-less overview minutes as UTC when filling gaps", () => {
    const overview = {
      series: [
        { minute: "2026-04-26T10:00:00", request_count: 2, error_count: 0, avg_latency_ms: 10 },
        { minute: "2026-04-26T10:02:00", request_count: 1, error_count: 1, avg_latency_ms: 30 },
      ],
    };
    const out = resolveSparklineSeries(overview, null);
    expect(out).toHaveLength(3);
    expect(out.map((b) => b.minute)).toEqual([
      "2026-04-26T10:00:00.000Z",
      "2026-04-26T10:01:00.000Z",
      "2026-04-26T10:02:00.000Z",
    ]);
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
    expect(result[0].count_2xx).toBe(1);
    expect(result[0].count_3xx).toBe(0);
    expect(result[0].count_4xx).toBe(0);
    expect(result[0].count_5xx).toBe(2);
  });

  it("aggregates zone-less request timestamps as UTC minutes", () => {
    const overviewEmpty = { series: [] };
    const requests = {
      items: [
        { timestamp: "2026-04-26T10:00:10", status_code: 200, latency_ms: 10 },
        { timestamp: "2026-04-26T10:00:40", status_code: 500, latency_ms: 20 },
      ],
    };
    const result = resolveSparklineSeries(overviewEmpty, requests);
    expect(result).toHaveLength(1);
    expect(result[0].minute).toBe("2026-04-26T10:00:00.000Z");
    expect(result[0].request_count).toBe(2);
  });

  it("uses request-derived series when preferRequests is true", () => {
    const overview = {
      series: [
        {
          minute: "2026-04-26T10:00:00Z",
          request_count: 99,
          error_count: 0,
          avg_latency_ms: 1,
        },
      ],
    };
    const requests = {
      items: [{ timestamp: "2026-04-26T10:00:30Z", status_code: 500, latency_ms: 20 }],
    };
    const result = resolveSparklineSeries(overview, requests, { preferRequests: true });
    expect(result).toHaveLength(1);
    expect(result[0].request_count).toBe(1);
    expect(result[0].error_count).toBe(1);
  });

  it("returns empty when no overview series and no requests", () => {
    expect(resolveSparklineSeries(null, null)).toEqual([]);
    expect(resolveSparklineSeries({ series: [] }, { items: [] })).toEqual([]);
  });
});

describe("parseDashboardInstantUtcMs", () => {
  it("appends Z for zone-less ISO strings", () => {
    expect(parseDashboardInstantUtcMs("2026-04-26T10:00:00")).toBe(Date.parse("2026-04-26T10:00:00Z"));
  });

  it("parses explicit Z and numeric offsets", () => {
    expect(parseDashboardInstantUtcMs("2026-04-26T10:00:00Z")).toBe(Date.parse("2026-04-26T10:00:00Z"));
    expect(parseDashboardInstantUtcMs("2026-04-26T11:00:00+01:00")).toBe(Date.parse("2026-04-26T10:00:00Z"));
  });
});

describe("trimSeriesToLastMinutes", () => {
  it("returns full series when lastMinutes covers span", () => {
    const series = [
      { minute: "2026-04-26T10:00:00.000Z", request_count: 1, error_count: 0, avg_latency_ms: 1 },
      { minute: "2026-04-26T10:02:00.000Z", request_count: 2, error_count: 0, avg_latency_ms: 2 },
    ];
    expect(trimSeriesToLastMinutes(series, 120)).toHaveLength(2);
  });

  it("drops older buckets outside last N minutes", () => {
    const series = [
      { minute: "2026-04-26T10:00:00.000Z", request_count: 1, error_count: 0, avg_latency_ms: 1 },
      { minute: "2026-04-26T10:10:00.000Z", request_count: 2, error_count: 0, avg_latency_ms: 2 },
    ];
    const trimmed = trimSeriesToLastMinutes(series, 5);
    expect(trimmed).toHaveLength(1);
    expect(trimmed[0].minute).toBe("2026-04-26T10:10:00.000Z");
  });

  it("uses UTC semantics for zone-less minute strings when computing cutoff", () => {
    const series = [
      { minute: "2026-04-26T08:00:00", request_count: 1, error_count: 0, avg_latency_ms: 1 },
      { minute: "2026-04-26T10:00:00", request_count: 2, error_count: 0, avg_latency_ms: 2 },
    ];
    const trimmed = trimSeriesToLastMinutes(series, 90);
    expect(trimmed).toHaveLength(1);
    expect(trimmed[0].minute).toBe("2026-04-26T10:00:00");
    expect(trimmed[0].request_count).toBe(2);
  });
});

describe("aggregateSeriesByStep", () => {
  it("returns sorted copy when step is 1", () => {
    const series = [
      { minute: "2026-04-26T10:01:00.000Z", request_count: 1, error_count: 0, avg_latency_ms: 10 },
      { minute: "2026-04-26T10:00:00.000Z", request_count: 2, error_count: 1, avg_latency_ms: 5 },
    ];
    const out = aggregateSeriesByStep(series, 1);
    expect(out.map((b) => b.minute)).toEqual([
      "2026-04-26T10:00:00.000Z",
      "2026-04-26T10:01:00.000Z",
    ]);
  });

  it("merges buckets for step > 1 with weighted latency", () => {
    const series = [
      {
        minute: "1970-01-01T00:00:00.000Z",
        request_count: 2,
        error_count: 0,
        avg_latency_ms: 10,
        count_2xx: 2,
        count_3xx: 0,
        count_4xx: 0,
        count_5xx: 0,
      },
      {
        minute: "1970-01-01T00:01:00.000Z",
        request_count: 2,
        error_count: 2,
        avg_latency_ms: 20,
        count_2xx: 0,
        count_3xx: 0,
        count_4xx: 1,
        count_5xx: 1,
      },
    ];
    const out = aggregateSeriesByStep(series, 2);
    expect(out).toHaveLength(1);
    expect(out[0].request_count).toBe(4);
    expect(out[0].error_count).toBe(2);
    expect(out[0].avg_latency_ms).toBe(15);
    expect(out[0].count_2xx).toBe(2);
    expect(out[0].count_3xx).toBe(0);
    expect(out[0].count_4xx).toBe(1);
    expect(out[0].count_5xx).toBe(1);
  });

  it("fills missing step buckets with zeros", () => {
    const series = [
      {
        minute: "1970-01-01T00:00:00.000Z",
        request_count: 2,
        error_count: 0,
        avg_latency_ms: 10,
      },
      {
        minute: "1970-01-01T00:10:00.000Z",
        request_count: 1,
        error_count: 1,
        avg_latency_ms: 30,
      },
    ];
    const out = aggregateSeriesByStep(series, 5);
    expect(out.map((b) => b.minute)).toEqual([
      "1970-01-01T00:00:00.000Z",
      "1970-01-01T00:05:00.000Z",
      "1970-01-01T00:10:00.000Z",
    ]);
    expect(out[1].request_count).toBe(0);
    expect(out[1].error_count).toBe(0);
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
