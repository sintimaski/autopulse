import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildDashboardDataCacheScopeKey,
  readDashboardSnapshot,
  writeDashboardSnapshot,
} from "./dashboardSnapshotCache";

describe("dashboardSnapshotCache", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        localStorage: {
          getItem: (key: string) => store.get(key) ?? null,
          setItem: (key: string, value: string) => {
            store.set(key, value);
          },
          clear: () => {
            store.clear();
          },
        },
      },
    });
  });

  it("reads minimal critical snapshot payload", () => {
    const scopeKey = buildDashboardDataCacheScopeKey({
      windowFrom: "",
      windowTo: "",
      windowMinutes: 60,
      isAbsoluteWindow: false,
      method: "ALL",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: 25,
      requestPage: 0,
      errorGroupLimit: 10,
      errorGroupPage: 0,
      errorGroupSort: "last_seen",
      sqlFilterEnabled: false,
      sqlFilterApplied: "",
    });

    writeDashboardSnapshot(scopeKey, {
      overview: {
        server_now: new Date().toISOString(),
        from_timestamp: new Date(Date.now() - 60_000).toISOString(),
        to_timestamp: new Date().toISOString(),
        request_count: 1,
        error_count: 0,
        error_rate: 0,
        avg_latency_ms: 10,
        requests_per_minute: 1,
        series: [],
      },
      requests: {
        server_now: new Date().toISOString(),
        from_timestamp: new Date(Date.now() - 60_000).toISOString(),
        to_timestamp: new Date().toISOString(),
        total: 1,
        limit: 25,
        offset: 0,
        items: [],
      },
    });

    const restored = readDashboardSnapshot(scopeKey);
    expect(restored).not.toBeNull();
    expect(restored?.overview.request_count).toBe(1);
    expect(restored?.overviewExtended).toBeUndefined();
    expect(restored?.errorGroups).toBeUndefined();
  });

  it("uses in-memory snapshot when localStorage read is unavailable", () => {
    const scopeKey = "memory-scope";
    writeDashboardSnapshot(scopeKey, {
      overview: {
        server_now: new Date().toISOString(),
        from_timestamp: new Date(Date.now() - 60_000).toISOString(),
        to_timestamp: new Date().toISOString(),
        request_count: 5,
        error_count: 1,
        error_rate: 0.2,
        avg_latency_ms: 20,
        requests_per_minute: 1,
        series: [],
      },
      requests: {
        server_now: new Date().toISOString(),
        from_timestamp: new Date(Date.now() - 60_000).toISOString(),
        to_timestamp: new Date().toISOString(),
        total: 5,
        limit: 25,
        offset: 0,
        items: [],
      },
    });
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {},
    });
    const restored = readDashboardSnapshot(scopeKey);
    expect(restored?.overview.request_count).toBe(5);
  });

  it("expires stale snapshots after ttl", () => {
    const now = new Date("2026-01-01T00:00:00.000Z").getTime();
    const dateNowSpy = vi.spyOn(Date, "now");
    dateNowSpy.mockReturnValue(now);
    const scopeKey = "ttl-scope";
    window.localStorage.setItem(
      "autopulse.dashboard.data.v1",
      JSON.stringify({
        scopeKey,
        savedAt: new Date(now - 30_000).toISOString(),
        payload: {
          overview: {
            server_now: new Date(now).toISOString(),
            from_timestamp: new Date(now - 60_000).toISOString(),
            to_timestamp: new Date(now).toISOString(),
            request_count: 1,
            error_count: 0,
            error_rate: 0,
            avg_latency_ms: 8,
            requests_per_minute: 1,
            series: [],
          },
          requests: {
            server_now: new Date(now).toISOString(),
            from_timestamp: new Date(now - 60_000).toISOString(),
            to_timestamp: new Date(now).toISOString(),
            total: 1,
            limit: 25,
            offset: 0,
            items: [],
          },
        },
      }),
    );
    dateNowSpy.mockReturnValue(now + 30_000);
    expect(readDashboardSnapshot(scopeKey)).toBeNull();
    dateNowSpy.mockRestore();
  });
});
