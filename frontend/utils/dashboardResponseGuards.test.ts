import { describe, expect, it } from "vitest";

import {
  parseDashboardAlertTestResponse,
  parseDashboardBootstrapResponse,
  parseDashboardOrganizationListResponse,
  parseEventPlaneCutoverSettings,
  parseLogQueryValidationResponse,
  parseQueryExplorerResponse,
  parseRetentionSettings,
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

describe("parseRetentionSettings", () => {
  it("accepts a minimal valid payload", () => {
    const raw = {
      raw_events_days: 7,
      logs_query_max_window_minutes: 60,
      retention_max_db_size_mb: null,
      retention_max_log_rows: null,
      retention_plan: "starter",
      archival_enabled: false,
      archival_mode: "db_archive",
      archival_status: "idle",
      archival_last_success_at: null,
      archival_last_error: null,
    };
    expect(parseRetentionSettings(raw)).toEqual(raw);
  });

  it("rejects bad archival_mode", () => {
    const raw = {
      raw_events_days: 7,
      logs_query_max_window_minutes: 60,
      retention_max_db_size_mb: null,
      retention_max_log_rows: null,
      retention_plan: "starter",
      archival_enabled: false,
      archival_mode: "wrong",
      archival_status: "idle",
      archival_last_success_at: null,
      archival_last_error: null,
    };
    expect(parseRetentionSettings(raw)).toBeNull();
  });
});

describe("parseLogQueryValidationResponse", () => {
  it("accepts a valid payload", () => {
    const raw = { valid: true, normalized_query: "status_code >= 500", error: null };
    expect(parseLogQueryValidationResponse(raw)).toEqual(raw);
  });

  it("rejects missing normalized_query", () => {
    expect(parseLogQueryValidationResponse({ valid: true, error: null })).toBeNull();
  });
});

describe("parseDashboardBootstrapResponse", () => {
  it("accepts a minimal coherent bootstrap payload", () => {
    const retention = {
      raw_events_days: 7,
      logs_query_max_window_minutes: 60,
      retention_max_db_size_mb: null,
      retention_max_log_rows: null,
      retention_plan: "starter" as const,
      archival_enabled: false,
      archival_mode: "db_archive" as const,
      archival_status: "idle" as const,
      archival_last_success_at: null,
      archival_last_error: null,
    };
    const alert_settings = {
      enabled: false,
      destination_email: null,
      email_enabled: false,
      slack_enabled: false,
      slack_webhook_url: null,
      discord_enabled: false,
      discord_webhook_url: null,
      webhook_enabled: false,
      webhook_url: null,
      error_spike_ratio_threshold: 0.05,
      error_spike_min_requests: 20,
      error_spike_window_minutes: 5,
      outage_min_requests: 50,
      outage_window_minutes: 5,
      cooldown_minutes: 30,
    };
    const raw = {
      retention_settings: retention,
      alert_settings,
      theme_settings: { theme_preference: "system", exclude_lumonox_traffic: true },
      api_keys: { items: [] },
      alert_capabilities: { channels: [] },
      onboarding_status: null,
    };
    expect(parseDashboardBootstrapResponse(raw)).toEqual(raw);
  });
});
