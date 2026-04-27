import { describe, expect, it } from "vitest";

import {
  buildScopedQuery,
  parseScopedQuery,
  scopedQueryStringsEqual,
} from "./dashboardQueryState";

describe("dashboardQueryState", () => {
  it("builds query string with filters and pagination", () => {
    const query = buildScopedQuery({
      isAbsoluteWindow: true,
      windowMinutes: 60,
      windowFromTimestamp: "2026-04-27T10:00:00.000Z",
      windowToTimestamp: "2026-04-27T11:00:00.000Z",
      method: "GET",
      statusClass: "5",
      minLatencyMs: "120",
      maxLatencyMs: "900",
      pathQuery: "/orders",
      serverEnvironmentQuery: "prod, staging",
      serverServiceQuery: "api,worker",
      requestLimit: 200,
      requestPage: 2,
      errorGroupLimit: 50,
      errorGroupPage: 3,
      errorGroupSort: "count",
      sqlFilterApplied: "status_code >= 500",
      sqlFilterEnabled: true,
    });
    expect(query.get("from_timestamp")).toBe("2026-04-27T10:00:00.000Z");
    expect(query.get("to_timestamp")).toBe("2026-04-27T11:00:00.000Z");
    expect(query.get("method")).toBe("GET");
    expect(query.get("status_class")).toBe("5");
    expect(query.get("environments")).toBe("prod,staging");
    expect(query.get("services")).toBe("api,worker");
    expect(query.get("request_page")).toBe("2");
    expect(query.get("error_group_page")).toBe("3");
    expect(query.get("error_group_sort")).toBe("count");
    expect(query.get("sql_filter")).toBe("status_code >= 500");
  });

  it("parses scoped query and falls back to defaults", () => {
    const parsed = parseScopedQuery(
      new URLSearchParams({
        window_minutes: "15",
        method: "POST",
        status_class: "4",
        path_contains: "/search",
        min_latency_ms: "20",
        max_latency_ms: "not-a-number",
        environments: "dev",
        services: "api",
        request_limit: "999",
        request_page: "4",
        error_group_limit: "10",
        error_group_page: "-3",
        error_group_sort: "count",
        sql_filter: "method = 'GET'",
      }),
    );

    expect(parsed.isAbsoluteWindow).toBe(false);
    expect(parsed.windowMinutes).toBe(15);
    expect(parsed.method).toBe("POST");
    expect(parsed.statusClass).toBe("4");
    expect(parsed.pathQuery).toBe("/search");
    expect(parsed.minLatencyMs).toBe("20");
    expect(parsed.maxLatencyMs).toBe("not-a-number");
    expect(parsed.requestLimit).toBe(100);
    expect(parsed.requestPage).toBe(4);
    expect(parsed.errorGroupLimit).toBe(10);
    expect(parsed.errorGroupPage).toBe(0);
    expect(parsed.errorGroupSort).toBe("count");
    expect(parsed.sqlFilterApplied).toBe("method = 'GET'");
    expect(parsed.sqlFilterEnabled).toBe(true);
  });

  it("parseScopedQuery omits sql fields when absent from URL", () => {
    const parsed = parseScopedQuery(new URLSearchParams({ window_minutes: "30" }));
    expect(parsed.sqlFilterApplied).toBeUndefined();
    expect(parsed.sqlFilterEnabled).toBeUndefined();
  });

  it("scopedQueryStringsEqual ignores parameter order", () => {
    expect(scopedQueryStringsEqual("a=1&b=2", "b=2&a=1")).toBe(true);
    expect(scopedQueryStringsEqual("a=1", "a=2")).toBe(false);
  });

  it("buildScopedQuery omits sql_filter when disabled or empty", () => {
    const query = buildScopedQuery({
      isAbsoluteWindow: false,
      windowMinutes: 60,
      windowFromTimestamp: "",
      windowToTimestamp: "",
      method: "ALL",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: 100,
      requestPage: 0,
      errorGroupLimit: 25,
      errorGroupPage: 0,
      errorGroupSort: "last_seen",
      sqlFilterApplied: "status_code >= 500",
      sqlFilterEnabled: false,
    });
    expect(query.has("sql_filter")).toBe(false);
  });
});
