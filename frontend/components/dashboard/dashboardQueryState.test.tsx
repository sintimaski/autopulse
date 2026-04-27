import { describe, expect, it } from "vitest";

import { buildScopedQuery, parseScopedQuery } from "./dashboardQueryState";

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
      sqlQueryText: "SELECT * FROM events",
      sqlQueryCursor: "cursor-123",
      liveQueryEnabled: false,
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
    expect(query.get("sql_query")).toBe("SELECT * FROM events");
    expect(query.get("sql_cursor")).toBe("cursor-123");
    expect(query.get("sql_live")).toBe("0");
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
        sql_query: "SELECT * FROM events",
        sql_cursor: "c-1",
        sql_live: "0",
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
    expect(parsed.sqlQueryText).toBe("SELECT * FROM events");
    expect(parsed.sqlQueryCursor).toBe("c-1");
    expect(parsed.liveQueryEnabled).toBe(false);
  });
});
