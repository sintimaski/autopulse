import { describe, expect, it } from "vitest";

import type { OverviewBucket } from "./dashboardData";
import { fractionalIndexForReleaseMarker, uniqueReleaseMarkerFractions } from "./releaseMarkersChart";

const bucket = (minute: string): OverviewBucket => ({
  minute,
  request_count: 1,
  error_count: 0,
  avg_latency_ms: 1,
});

describe("fractionalIndexForReleaseMarker", () => {
  it("maps marker inside first bucket", () => {
    const displayed = [bucket("2026-01-01T10:00:00.000Z"), bucket("2026-01-01T10:05:00.000Z")];
    const f = fractionalIndexForReleaseMarker(displayed, 5, "2026-01-01T10:02:00.000Z");
    expect(f).toBeCloseTo(0.4, 5);
  });

  it("returns null when marker is before window", () => {
    const displayed = [bucket("2026-01-01T10:00:00.000Z")];
    expect(fractionalIndexForReleaseMarker(displayed, 5, "2026-01-01T09:00:00.000Z")).toBeNull();
  });

  it("allows marker at inclusive end of last bucket", () => {
    const displayed = [bucket("2026-01-01T10:00:00.000Z"), bucket("2026-01-01T10:05:00.000Z")];
    const f = fractionalIndexForReleaseMarker(displayed, 5, "2026-01-01T10:10:00.000Z");
    expect(f).toBeCloseTo(2, 5);
  });
});

describe("uniqueReleaseMarkerFractions", () => {
  it("dedupes identical fractional positions", () => {
    const displayed = [bucket("2026-01-01T10:00:00.000Z")];
    const fr = uniqueReleaseMarkerFractions(displayed, 5, [
      { at: "2026-01-01T10:01:00.000Z" },
      { at: "2026-01-01T10:01:00.000Z" },
    ]);
    expect(fr.length).toBe(1);
  });
});
