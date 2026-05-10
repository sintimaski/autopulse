import { describe, expect, it } from "vitest";

import { parseDashboardDataQueryResponse, parseOverviewResponse, parseRequestsResponse } from "./dashboardQueryResponseGuards";

const minimalOverview = {
  server_now: "2026-01-01T00:00:00Z",
  from_timestamp: "2026-01-01T00:00:00Z",
  to_timestamp: "2026-01-01T01:00:00Z",
  request_count: 10,
  error_count: 1,
  error_rate: 0.1,
  avg_latency_ms: 12.5,
  requests_per_minute: 2.5,
  series: [
    {
      minute: "2026-01-01T00:00:00Z",
      request_count: 5,
      error_count: 0,
      avg_latency_ms: 10,
      count_2xx: 5,
      count_3xx: 0,
      count_4xx: 0,
      count_5xx: 0,
    },
  ],
};

const minimalRequests = {
  server_now: "2026-01-01T00:00:00Z",
  from_timestamp: "2026-01-01T00:00:00Z",
  to_timestamp: "2026-01-01T01:00:00Z",
  total: 1,
  limit: 25,
  offset: 0,
  items: [
    {
      timestamp: "2026-01-01T00:30:00Z",
      method: "GET",
      path: "/health",
      status_code: 200,
      latency_ms: 5,
      service_name: "api",
      environment: "dev",
      request_id: null,
      log_message: null,
    },
  ],
};

describe("parseOverviewResponse", () => {
  it("accepts a minimal overview", () => {
    expect(parseOverviewResponse(minimalOverview)).toEqual(minimalOverview);
  });

  it("rejects invalid series", () => {
    expect(parseOverviewResponse({ ...minimalOverview, series: [{}] })).toBeNull();
  });
});

describe("parseRequestsResponse", () => {
  it("accepts minimal requests", () => {
    expect(parseRequestsResponse(minimalRequests)).toEqual(minimalRequests);
  });
});

describe("parseDashboardDataQueryResponse", () => {
  it("parses bundle with only overview + requests", () => {
    const raw = { overview: minimalOverview, requests: minimalRequests };
    const parsed = parseDashboardDataQueryResponse(raw);
    expect(parsed).not.toBeNull();
    expect(parsed?.overview).toEqual(minimalOverview);
    expect(parsed?.requests).toEqual(minimalRequests);
    expect(parsed?.overview_extended).toBeNull();
    expect(parsed?.widgets).toBeNull();
    expect(parsed?.error_groups).toBeNull();
  });

  it("rejects when requests invalid", () => {
    expect(
      parseDashboardDataQueryResponse({
        overview: minimalOverview,
        requests: { ...minimalRequests, items: "bad" },
      }),
    ).toBeNull();
  });

  it("accepts widgets payload with backend layout pages", () => {
    const parsed = parseDashboardDataQueryResponse({
      overview: minimalOverview,
      requests: minimalRequests,
      widgets: {
        server_now: "2026-01-01T00:00:00Z",
        from_timestamp: "2026-01-01T00:00:00Z",
        to_timestamp: "2026-01-01T01:00:00Z",
        definitions: [
          {
            widget_id: "custom_latency",
            type: "line",
            title: "Latency",
            description: null,
            order: 10,
            config: { page_id: "ops", section: "charts" },
          },
        ],
        points: [{ widget_id: "custom_latency", timestamp: "2026-01-01T00:30:00Z", label: null, value: 42 }],
        layout: {
          default_page_id: "ops",
          pages: [
            {
              page_id: "ops",
              title: "Operations",
              description: "Backend-provisioned page",
              order: 1,
              widgets: [
                {
                  widget_id: "custom_latency",
                  order: 10,
                  section: "charts",
                  column_span: 1,
                  row_span: 1,
                },
              ],
            },
          ],
          unplaced_widget_ids: [],
        },
      },
    });
    expect(parsed?.widgets?.layout?.pages[0]?.page_id).toBe("ops");
  });

  it("rejects non-object or non-record roots", () => {
    expect(parseDashboardDataQueryResponse(null)).toBeNull();
    expect(parseDashboardDataQueryResponse(undefined)).toBeNull();
    expect(parseDashboardDataQueryResponse([])).toBeNull();
    expect(parseDashboardDataQueryResponse("not-json")).toBeNull();
  });

  it("rejects when overview or requests key missing", () => {
    expect(parseDashboardDataQueryResponse({ overview: minimalOverview })).toBeNull();
    expect(parseDashboardDataQueryResponse({ requests: minimalRequests })).toBeNull();
  });
});
