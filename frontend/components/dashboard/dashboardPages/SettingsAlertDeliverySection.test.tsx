import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { AlertSettings } from "../dashboardTypes";

import { SettingsAlertDeliverySection } from "./SettingsAlertDeliverySection";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

const baseDraft: AlertSettings = {
  enabled: true,
  destination_email: "ops@example.com",
  email_enabled: true,
  slack_enabled: false,
  slack_webhook_url: null,
  discord_enabled: false,
  discord_webhook_url: null,
  webhook_enabled: false,
  webhook_url: null,
  error_spike_ratio_threshold: 0.4,
  error_spike_min_requests: 20,
  error_spike_window_minutes: 5,
  outage_min_requests: 10,
  outage_window_minutes: 5,
  cooldown_minutes: 60,
};

describe("SettingsAlertDeliverySection", () => {
  it("renders alert delivery heading and save action when draft is present", () => {
    const html = renderToStaticMarkup(
      <SettingsAlertDeliverySection
        alertDeliveryDraft={baseDraft}
        dashboardLoading={false}
        dashboardErrorMessage={null}
        canEditAlertDelivery
        viewerSession={false}
        alertCapabilities={[
          { channel: "email", status: "active", enabled: true, reason: "SMTP configured" },
        ]}
        alertSettingsSaving={false}
        updateAlertSettingsDraft={() => {}}
        onSave={() => {}}
        onSendTestAlert={() => {}}
        channelMessage={null}
        testAlertSending={false}
        testAlertResult={null}
        testAlertError={null}
      />,
    );
    expect(html).toContain("Alert delivery");
    expect(html).toContain("Save alert delivery");
    expect(html).toContain("Server readiness");
    expect(html).toContain('href="/alerts"');
  });

  it("shows loading spinner when dashboard is loading and draft is absent", () => {
    const html = renderToStaticMarkup(
      <SettingsAlertDeliverySection
        alertDeliveryDraft={null}
        dashboardLoading
        dashboardErrorMessage={null}
        canEditAlertDelivery
        viewerSession={false}
        alertCapabilities={[]}
        alertSettingsSaving={false}
        updateAlertSettingsDraft={() => {}}
        onSave={() => {}}
        onSendTestAlert={() => {}}
        channelMessage={null}
        testAlertSending={false}
        testAlertResult={null}
        testAlertError={null}
      />,
    );
    expect(html).toContain("Loading alert delivery");
  });
});
