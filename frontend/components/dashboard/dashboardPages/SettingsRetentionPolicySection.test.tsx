import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { RetentionSettings } from "../dashboardTypes";

import { SettingsRetentionPolicySection } from "./SettingsRetentionPolicySection";

const sampleDraft: RetentionSettings = {
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

describe("SettingsRetentionPolicySection", () => {
  it("renders policy heading and save action when editable", () => {
    const html = renderToStaticMarkup(
      <SettingsRetentionPolicySection
        effectiveDraft={sampleDraft}
        canEditRetention
        dashboardLoading={false}
        dashboardErrorMessage={null}
        retentionMessage={null}
        onDraftChange={() => {}}
        onSave={async () => {}}
      />,
    );
    expect(html).toContain("Retention policy");
    expect(html).toContain("Save retention policy");
    expect(html).toContain("Raw events retention");
  });

  it("shows read-only copy when user cannot edit retention", () => {
    const html = renderToStaticMarkup(
      <SettingsRetentionPolicySection
        effectiveDraft={sampleDraft}
        canEditRetention={false}
        dashboardLoading={false}
        dashboardErrorMessage={null}
        retentionMessage={null}
        onDraftChange={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    expect(html).toContain("Only organization owners and admins can change retention");
  });
});
