import { beforeEach, describe, expect, it, vi } from "vitest";

import { dashboardSessionFetch } from "./dashboardSessionFetch";
import { loadDashboardBootstrap } from "./dashboardWorkspaceBootstrap";

vi.mock("./dashboardSessionFetch", () => ({
  dashboardSessionFetch: vi.fn(),
}));

const minimalBootstrap = {
  retention_settings: {
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
  },
  alert_settings: {
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
    notifications_muted: false,
    notifications_snoozed_until: null,
    last_notifications_acknowledged_at: null,
  },
  theme_settings: { theme_preference: "system" as const, exclude_lumonox_traffic: true },
  api_keys: { items: [] },
  alert_capabilities: { channels: [] },
  onboarding_status: null,
};

describe("loadDashboardBootstrap", () => {
  beforeEach(() => {
    vi.mocked(dashboardSessionFetch).mockReset();
  });

  it("calls onUnauthorized when bootstrap returns 401", async () => {
    vi.mocked(dashboardSessionFetch).mockResolvedValue(new Response(JSON.stringify({}), { status: 401 }));
    const on401 = vi.fn();
    await expect(loadDashboardBootstrap(new AbortController().signal, on401)).rejects.toThrow();
    expect(on401).toHaveBeenCalledTimes(1);
  });

  it("returns parsed bootstrap on 200", async () => {
    vi.mocked(dashboardSessionFetch).mockResolvedValue(
      new Response(JSON.stringify(minimalBootstrap), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const data = await loadDashboardBootstrap(new AbortController().signal, vi.fn());
    expect(data.retention_settings.raw_events_days).toBe(7);
    expect(data.theme_settings.exclude_lumonox_traffic).toBe(true);
  });
});
