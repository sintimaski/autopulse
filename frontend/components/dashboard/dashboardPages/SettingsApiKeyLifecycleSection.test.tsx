import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DashboardApiKeyItem } from "../dashboardTypes";

import { SettingsApiKeyLifecycleSection } from "./SettingsApiKeyLifecycleSection";

const sampleKeys: DashboardApiKeyItem[] = [
  { key_id: "lk_1", created_at: "2026-01-01T00:00:00Z", revoked_at: null },
  { key_id: "lk_2", created_at: "2026-01-01T01:00:00Z", revoked_at: "2026-01-01T02:00:00Z" },
];

describe("SettingsApiKeyLifecycleSection", () => {
  it("renders key table and actions for mutating users", () => {
    const html = renderToStaticMarkup(
      <SettingsApiKeyLifecycleSection
        canMutateApiKeys
        isApiSubpathDashboard={false}
        activeKeyIds={["lk_1"]}
        keyBulkAction=""
        selectedKeyIds={new Set<string>()}
        allKeysSelected={false}
        apiKeys={sampleKeys}
        lastIssuedApiKey={null}
        apiKeyMessage={null}
        onIssueKey={() => {}}
        onRefreshKeys={() => {}}
        onKeyBulkActionChange={() => {}}
        onApplyBulk={() => {}}
        onToggleSelectAll={() => {}}
        onToggleKeySelected={() => {}}
      />,
    );
    expect(html).toContain("API key lifecycle");
    expect(html).toContain("Issue new key");
    expect(html).toContain("Bulk API key action");
    expect(html).toContain("lk_1");
  });

  it("shows one-time issued key message when present", () => {
    const html = renderToStaticMarkup(
      <SettingsApiKeyLifecycleSection
        canMutateApiKeys={false}
        isApiSubpathDashboard
        activeKeyIds={[]}
        keyBulkAction=""
        selectedKeyIds={new Set<string>()}
        allKeysSelected={false}
        apiKeys={sampleKeys}
        lastIssuedApiKey="lumonox_demo_key"
        apiKeyMessage="saved"
        onIssueKey={() => {}}
        onRefreshKeys={() => {}}
        onKeyBulkActionChange={() => {}}
        onApplyBulk={() => {}}
        onToggleSelectAll={() => {}}
        onToggleKeySelected={() => {}}
      />,
    );
    expect(html).toContain("Copy this key now");
    expect(html).toContain("lumonox_demo_key");
    expect(html).toContain(".env.lumonox");
  });
});
