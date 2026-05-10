"use client";

import { useCallback, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { AlertSettings, DashboardAlertTestResponse } from "../dashboardTypes";
import { dashboardSessionFetch } from "../dashboardSessionFetch";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import { parseDashboardAlertTestResponse } from "../../../utils/dashboardResponseGuards";
import {
  looksLikeCompleteDiscordIncomingWebhook,
  looksLikeCompleteSlackIncomingWebhook,
} from "./settingsContentUtils";

export function useSettingsAlertDelivery(
  alertDeliveryDraft: AlertSettings | null,
  saveAlertSettings: (next: AlertSettings) => Promise<boolean>,
  setRefreshToken: Dispatch<SetStateAction<number>>,
) {
  const [channelMessage, setChannelMessage] = useState<string | null>(null);
  const [testAlertSending, setTestAlertSending] = useState(false);
  const [testAlertResult, setTestAlertResult] = useState<DashboardAlertTestResponse | null>(null);
  const [testAlertError, setTestAlertError] = useState<string | null>(null);

  const sendTestAlert = useCallback(async () => {
    setTestAlertSending(true);
    setTestAlertError(null);
    setTestAlertResult(null);
    try {
      const response = await dashboardSessionFetch("/dashboard/alert-test", { method: "POST" });
      if (!response.ok) {
        throw new Error(`alert-test failed (${response.status})`);
      }
      const raw: unknown = await response.json();
      const body = parseDashboardAlertTestResponse(raw);
      if (!body) {
        throw new Error("alert-test returned unexpected JSON shape");
      }
      setTestAlertResult(body);
      setRefreshToken((token) => token + 1);
    } catch (error) {
      setTestAlertError(buildDashboardNetworkError(error));
    } finally {
      setTestAlertSending(false);
    }
  }, [setRefreshToken]);

  const saveDeliveryChannels = useCallback(async () => {
    if (!alertDeliveryDraft) {
      return;
    }
    if (alertDeliveryDraft.email_enabled && !alertDeliveryDraft.destination_email?.trim()) {
      setChannelMessage("Email delivery is enabled. Add a destination email address.");
      return;
    }
    if (alertDeliveryDraft.slack_enabled && !alertDeliveryDraft.slack_webhook_url?.trim()) {
      setChannelMessage("Slack is enabled. Add a Slack webhook URL.");
      return;
    }
    if (
      alertDeliveryDraft.slack_enabled &&
      alertDeliveryDraft.slack_webhook_url?.trim() &&
      !looksLikeCompleteSlackIncomingWebhook(alertDeliveryDraft.slack_webhook_url)
    ) {
      setChannelMessage(
        "Slack URL looks incomplete. Paste the full incoming webhook from Slack (includes /services/…/…/…).",
      );
      return;
    }
    if (alertDeliveryDraft.discord_enabled && !alertDeliveryDraft.discord_webhook_url?.trim()) {
      setChannelMessage("Discord is enabled. Add a Discord webhook URL.");
      return;
    }
    if (
      alertDeliveryDraft.discord_enabled &&
      alertDeliveryDraft.discord_webhook_url?.trim() &&
      !looksLikeCompleteDiscordIncomingWebhook(alertDeliveryDraft.discord_webhook_url)
    ) {
      setChannelMessage(
        "Discord URL looks incomplete. Paste the full webhook URL from Discord (ends with /webhooks/id/token).",
      );
      return;
    }
    if (alertDeliveryDraft.webhook_enabled && !alertDeliveryDraft.webhook_url?.trim()) {
      setChannelMessage("Webhook is enabled. Add a webhook URL.");
      return;
    }
    const ok = await saveAlertSettings(alertDeliveryDraft);
    setChannelMessage(ok ? "Alert delivery settings saved." : "Failed to save alert delivery settings.");
  }, [alertDeliveryDraft, saveAlertSettings]);

  return {
    channelMessage,
    testAlertSending,
    testAlertResult,
    testAlertError,
    sendTestAlert,
    saveDeliveryChannels,
  };
}
