import { describe, expect, it } from "vitest";

import {
  parseDashboardAlertTestResponse,
  parseDashboardOrganizationListResponse,
  parseEventPlaneCutoverSettings,
  parseQueryExplorerResponse,
  parseTraceDetailResponse,
  parseTraceSearchResponse,
} from "./dashboardResponseGuards";

describe("parseQueryExplorerResponse", () => {
  it("accepts a well-formed payload", () => {
    const raw = {
      server_now: "2026-01-01T00:00:00Z",
      from_timestamp: "2026-01-01T00:00:00Z",
      to_timestamp: "2026-01-01T01:00:00Z",
      query: "SELECT 1",
      columns: ["a"],
      rows: [[1, "x", null, true]],
      truncated: false,
    };
    expect(parseQueryExplorerResponse(raw)).toEqual(raw);
  });

  it("rejects invalid rows", () => {
    const raw = {
      server_now: "a",
      from_timestamp: "b",
      to_timestamp: "c",
      query: "q",
      columns: ["a"],
      rows: [[{ o: 1 }]],
      truncated: false,
    };
    expect(parseQueryExplorerResponse(raw)).toBeNull();
  });
});

describe("parseTraceSearchResponse", () => {
  it("accepts a minimal valid list", () => {
    const raw = {
      server_now: "s",
      from_timestamp: "f",
      to_timestamp: "t",
      project_id: "p",
      total: 1,
      items: [
        {
          trace_id: "tr",
          first_seen: "a",
          last_seen: "b",
          span_count: 2,
          error_count: 0,
          services: ["api"],
          root_span_name: null,
        },
      ],
    };
    expect(parseTraceSearchResponse(raw)).toEqual(raw);
  });

  it("rejects bad item shape", () => {
    const raw = {
      server_now: "s",
      from_timestamp: "f",
      to_timestamp: "t",
      project_id: "p",
      total: 0,
      items: [{ trace_id: 1 }],
    };
    expect(parseTraceSearchResponse(raw)).toBeNull();
  });
});

describe("parseDashboardOrganizationListResponse", () => {
  it("accepts a minimal org list", () => {
    const raw = {
      organizations: [
        {
          organization_id: "o1",
          organization_name: "Org",
          projects: [{ project_id: "p1", project_name: "Proj", organization_id: "o1" }],
          role: "owner",
        },
      ],
    };
    expect(parseDashboardOrganizationListResponse(raw)).toEqual(raw);
  });

  it("rejects invalid org role", () => {
    expect(
      parseDashboardOrganizationListResponse({
        organizations: [{ organization_id: "o", organization_name: "O", projects: [], role: "god" }],
      }),
    ).toBeNull();
  });
});

describe("parseEventPlaneCutoverSettings", () => {
  it("accepts boolean flag", () => {
    expect(parseEventPlaneCutoverSettings({ use_snapshot_read: true })).toEqual({ use_snapshot_read: true });
  });

  it("rejects missing flag", () => {
    expect(parseEventPlaneCutoverSettings({})).toBeNull();
  });
});

describe("parseDashboardAlertTestResponse", () => {
  it("accepts a valid test payload", () => {
    const raw = {
      status: "ok",
      delivered_via: "email",
      reason_code: null,
      reason_message: null,
      attempt_count: 1,
      delivered_at: null,
      provider_message_id: null,
      destination_email: null,
    };
    expect(parseDashboardAlertTestResponse(raw)).toEqual(raw);
  });
});

describe("parseTraceDetailResponse", () => {
  it("accepts valid detail payload", () => {
    const span = {
      timestamp: "t",
      service_name: "s",
      environment: "e",
      span_name: "n",
      path: "/",
      method: "GET",
      status_code: 200,
      latency_ms: 1,
      trace_id: "tr",
      span_id: null,
      parent_span_id: null,
      request_id: null,
      otlp_status_code: null,
    };
    const raw = {
      trace_id: "tr",
      first_seen: null,
      last_seen: null,
      error_count: 0,
      items: [span],
    };
    expect(parseTraceDetailResponse(raw)).toEqual(raw);
  });
});
