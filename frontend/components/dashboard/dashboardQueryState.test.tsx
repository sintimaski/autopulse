import { describe, expect, it } from "vitest";

import {
  buildDiagnosisPageHref,
  buildIncidentShareQuery,
  buildRequestsPageHref,
  buildScopedQuery,
  mergeIncidentShareIntoScopeQueryString,
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
      correlationRequestId: "abc-123",
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
    expect(query.get("correlation")).toBe("abc-123");
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
    expect(parsed.correlationRequestId).toBe("");
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

  it("mergeIncidentShareIntoScopeQueryString preserves incident_share_id", () => {
    expect(
      mergeIncidentShareIntoScopeQueryString(
        "window_minutes=60",
        "incident_share_id=ba7c5357-e73e-40bc-a835-d23df3471057&window_minutes=60",
      ),
    ).toBe("window_minutes=60&incident_share_id=ba7c5357-e73e-40bc-a835-d23df3471057");
    expect(mergeIncidentShareIntoScopeQueryString("window_minutes=60", "window_minutes=60")).toBe(
      "window_minutes=60",
    );
  });

  it("mergeIncidentShareIntoScopeQueryString preserves incident_saved_id and both ids", () => {
    expect(
      mergeIncidentShareIntoScopeQueryString(
        "window_minutes=30",
        "window_minutes=30&incident_saved_id=11111111-1111-1111-1111-111111111111",
      ),
    ).toBe("window_minutes=30&incident_saved_id=11111111-1111-1111-1111-111111111111");
    expect(
      mergeIncidentShareIntoScopeQueryString(
        "window_minutes=15",
        "incident_share_id=ba7c5357-e73e-40bc-a835-d23df3471057&incident_saved_id=22222222-2222-2222-2222-222222222222&window_minutes=15",
      ),
    ).toBe(
      "window_minutes=15&incident_share_id=ba7c5357-e73e-40bc-a835-d23df3471057&incident_saved_id=22222222-2222-2222-2222-222222222222",
    );
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
      correlationRequestId: "",
      sqlFilterApplied: "status_code >= 500",
      sqlFilterEnabled: false,
    });
    expect(query.has("sql_filter")).toBe(false);
  });

  const baseScope = {
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
    errorGroupSort: "last_seen" as const,
    correlationRequestId: "",
    sqlFilterApplied: "",
    sqlFilterEnabled: false,
  };

  it("buildRequestsPageHref preserves scope and applies path patch", () => {
    const href = buildRequestsPageHref(baseScope, { pathQuery: "/api/orders", statusClass: "5" });
    expect(href.startsWith("/requests?")).toBe(true);
    const q = new URLSearchParams(href.slice("/requests?".length));
    expect(q.get("window_minutes")).toBe("60");
    expect(q.get("path_contains")).toBe("/api/orders");
    expect(q.get("status_class")).toBe("5");
  });

  it("buildDiagnosisPageHref appends hash and resets error group page", () => {
    const href = buildDiagnosisPageHref(
      { ...baseScope, errorGroupPage: 2 },
      { pathQuery: "/fail" },
      "#grouped-errors",
    );
    expect(href.includes("#grouped-errors")).toBe(true);
    const q = new URLSearchParams(href.split("#")[0].replace("/diagnosis?", ""));
    expect(q.get("path_contains")).toBe("/fail");
    expect(q.get("error_group_page")).toBeNull();
  });

  it("parseScopedQuery round-trips buildScopedQuery for URL scope sync", () => {
    const state = {
      ...baseScope,
      windowMinutes: 30,
      method: "PUT",
      statusClass: "4",
      pathQuery: "/widgets",
      serverEnvironmentQuery: "prod,staging",
      serverServiceQuery: "api",
      requestLimit: 200,
      requestPage: 1,
      errorGroupLimit: 50,
      errorGroupPage: 2,
      errorGroupSort: "count" as const,
      sqlFilterApplied: "status_code >= 400",
      sqlFilterEnabled: true,
      correlationRequestId: "rid-1",
    };
    const built = buildScopedQuery(state);
    const parsed = parseScopedQuery(new URLSearchParams(built.toString()));
    expect(parsed.windowMinutes).toBe(30);
    expect(parsed.method).toBe("PUT");
    expect(parsed.statusClass).toBe("4");
    expect(parsed.pathQuery).toBe("/widgets");
    expect(parsed.serverEnvironmentQuery).toBe("prod,staging");
    expect(parsed.serverServiceQuery).toBe("api");
    expect(parsed.requestLimit).toBe(200);
    expect(parsed.requestPage).toBe(1);
    expect(parsed.errorGroupLimit).toBe(50);
    expect(parsed.errorGroupPage).toBe(2);
    expect(parsed.errorGroupSort).toBe("count");
    expect(parsed.sqlFilterApplied).toBe("status_code >= 400");
    expect(parsed.sqlFilterEnabled).toBe(true);
    expect(parsed.correlationRequestId).toBe("rid-1");
  });

  it("buildIncidentShareQuery carries only the time window", () => {
    const absolute = buildIncidentShareQuery({
      isAbsoluteWindow: true,
      windowMinutes: 60,
      windowFromTimestamp: "2026-04-27T10:00:00.000Z",
      windowToTimestamp: "2026-04-27T11:00:00.000Z",
      method: "GET",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: 50,
      requestPage: 0,
      errorGroupLimit: 100,
      errorGroupPage: 0,
      errorGroupSort: "last_seen",
      correlationRequestId: "",
      sqlFilterApplied: "",
      sqlFilterEnabled: false,
    });
    const absParams = new URLSearchParams(absolute);
    expect(absParams.get("from_timestamp")).toBe("2026-04-27T10:00:00.000Z");
    expect(absParams.get("to_timestamp")).toBe("2026-04-27T11:00:00.000Z");
    expect(absParams.get("method")).toBeNull();

    const rolling = buildIncidentShareQuery({
      isAbsoluteWindow: false,
      windowMinutes: 45,
      windowFromTimestamp: "",
      windowToTimestamp: "",
      method: "ALL",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: 50,
      requestPage: 0,
      errorGroupLimit: 100,
      errorGroupPage: 0,
      errorGroupSort: "last_seen",
      correlationRequestId: "",
      sqlFilterApplied: "",
      sqlFilterEnabled: false,
    });
    expect(new URLSearchParams(rolling).get("window_minutes")).toBe("45");
  });
});
