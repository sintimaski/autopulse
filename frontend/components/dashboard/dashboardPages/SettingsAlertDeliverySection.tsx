"use client";

import Link from "next/link";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type {
  AlertChannelCapability,
  AlertSettings,
  DashboardAlertTestResponse,
} from "../dashboardTypes";

export type SettingsAlertDeliverySectionProps = {
  alertDeliveryDraft: AlertSettings | null;
  dashboardLoading: boolean;
  dashboardErrorMessage: string | null;
  canEditAlertDelivery: boolean;
  viewerSession: boolean;
  alertCapabilities: AlertChannelCapability[];
  alertSettingsSaving: boolean;
  updateAlertSettingsDraft: (next: AlertSettings) => void;
  onSave: () => void | Promise<void>;
  onSendTestAlert: () => void | Promise<void>;
  channelMessage: string | null;
  testAlertSending: boolean;
  testAlertResult: DashboardAlertTestResponse | null;
  testAlertError: string | null;
};

export function SettingsAlertDeliverySection({
  alertDeliveryDraft,
  dashboardLoading,
  dashboardErrorMessage,
  canEditAlertDelivery,
  viewerSession,
  alertCapabilities,
  alertSettingsSaving,
  updateAlertSettingsDraft,
  onSave,
  onSendTestAlert,
  channelMessage,
  testAlertSending,
  testAlertResult,
  testAlertError,
}: SettingsAlertDeliverySectionProps) {
  return (
    <section
      id="alert-delivery"
      className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
    >
      <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Alert delivery</h2>
      {alertDeliveryDraft ? (
        <>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
            Turn project alerts on, set where notifications go (email, Slack/Discord webhooks via env, or generic
            webhooks), then save. Heuristic thresholds (error spikes, cooldown) stay on the{" "}
            <Link
              href="/alerts"
              className="font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
            >
              Alerts
            </Link>{" "}
            page.
          </p>
          {!canEditAlertDelivery ? (
            <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
              Only organization owners and admins can change alert delivery. Viewers can send a test alert when the
              server allows it.
            </p>
          ) : null}
          <label className="mt-4 flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/60 px-3 py-2.5 text-sm font-medium text-slate-800 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-100">
            <input
              type="checkbox"
              disabled={!canEditAlertDelivery}
              checked={alertDeliveryDraft.enabled}
              onChange={(event) =>
                updateAlertSettingsDraft({
                  ...alertDeliveryDraft,
                  enabled: event.target.checked,
                })
              }
            />
            Project alerts enabled
          </label>
          <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
            When off, no alert notifications are sent for this project regardless of channel toggles.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
              <label className="flex items-center gap-2 font-medium">
                <input
                  type="checkbox"
                  disabled={!canEditAlertDelivery}
                  checked={alertDeliveryDraft.email_enabled}
                  onChange={(event) =>
                    updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      email_enabled: event.target.checked,
                    })
                  }
                />
                Email
              </label>
              <label className="mt-2 block text-xs font-normal text-slate-600 dark:text-neutral-300">
                Destination address
                <input
                  type="email"
                  disabled={!canEditAlertDelivery}
                  value={alertDeliveryDraft.destination_email ?? ""}
                  onChange={(event) =>
                    updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      destination_email: event.target.value.trim() || null,
                    })
                  }
                  className="ap-input mt-1 text-sm"
                  placeholder="ops@example.com"
                />
              </label>
              <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                SMTP, Resend, SendGrid, etc. are configured on the Lumonox server (environment variables), not in this
                form—you only choose who receives mail. See readiness below.
              </span>
            </div>
            <label className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="checkbox"
                  disabled={!canEditAlertDelivery}
                  checked={alertDeliveryDraft.slack_enabled}
                  onChange={(event) =>
                    updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      slack_enabled: event.target.checked,
                    })
                  }
                />
                Slack
              </span>
              <input
                type="url"
                disabled={!canEditAlertDelivery}
                value={alertDeliveryDraft.slack_webhook_url ?? ""}
                onChange={(event) =>
                  updateAlertSettingsDraft({
                    ...alertDeliveryDraft,
                    slack_webhook_url: event.target.value.trim() || null,
                  })
                }
                className="ap-input mt-2"
                placeholder="https://hooks.slack.com/services/..."
              />
              <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                One field is enough: Slack puts the secret in the webhook URL. Paste the full link from &quot;Incoming
                Webhooks&quot; (not an API token alone).
              </span>
            </label>
            <label className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="checkbox"
                  disabled={!canEditAlertDelivery}
                  checked={alertDeliveryDraft.discord_enabled}
                  onChange={(event) =>
                    updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      discord_enabled: event.target.checked,
                    })
                  }
                />
                Discord
              </span>
              <input
                type="url"
                disabled={!canEditAlertDelivery}
                value={alertDeliveryDraft.discord_webhook_url ?? ""}
                onChange={(event) =>
                  updateAlertSettingsDraft({
                    ...alertDeliveryDraft,
                    discord_webhook_url: event.target.value.trim() || null,
                  })
                }
                className="ap-input mt-2"
                placeholder="https://discord.com/api/webhooks/..."
              />
              <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                Paste the full URL from Server Settings → Integrations → Webhooks (it includes webhook id and token in
                the path). A bare{" "}
                <code className="rounded bg-slate-200/80 px-0.5 font-mono text-[11px] dark:bg-neutral-950/80">
                  /api/webhooks
                </code>{" "}
                prefix will not work.
              </span>
            </label>
            <label className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="checkbox"
                  disabled={!canEditAlertDelivery}
                  checked={alertDeliveryDraft.webhook_enabled}
                  onChange={(event) =>
                    updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      webhook_enabled: event.target.checked,
                    })
                  }
                />
                Generic webhook
              </span>
              <input
                type="url"
                disabled={!canEditAlertDelivery}
                value={alertDeliveryDraft.webhook_url ?? ""}
                onChange={(event) =>
                  updateAlertSettingsDraft({
                    ...alertDeliveryDraft,
                    webhook_url: event.target.value.trim() || null,
                  })
                }
                className="ap-input mt-2"
                placeholder="https://example.com/alerts/webhook"
              />
              <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                Lumonox POSTs a JSON payload to this URL. There is no separate API-key field; if your endpoint needs
                auth, use a signed URL or terminate TLS at a gateway you control (custom headers are not configured here
                yet).
              </span>
            </label>
          </div>

          <div className="mt-6 rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">Server readiness</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
              Status reflects backend environment wiring. &quot;Active&quot; means the server can dispatch through that
              channel when your project settings allow it.
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {alertCapabilities.map((capability) => (
                <li
                  key={capability.channel}
                  className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900/60"
                >
                  <div>
                    <p className="font-medium capitalize text-slate-800 dark:text-neutral-100">{capability.channel}</p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-neutral-400">{capability.reason}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                      capability.status === "active"
                        ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300"
                        : capability.status === "planned"
                          ? "bg-slate-300/40 text-slate-700 dark:bg-neutral-700 dark:text-neutral-200"
                          : "bg-amber-500/15 text-amber-800 dark:text-amber-300"
                    }`}
                  >
                    {capability.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-6 flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
            <div>
              <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">Test delivery</h3>
              <p className="mt-1 max-w-xl text-xs text-slate-500 dark:text-neutral-400">
                Sends a sample notification through the project&apos;s configured channels (same as the Alerts page
                test). Save changes above first if you edited URLs or toggles.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onSendTestAlert()}
              disabled={viewerSession || testAlertSending}
              className="ap-btn-primary shrink-0"
            >
              {testAlertSending ? "Sending test alert…" : "Send test alert"}
            </button>
          </div>
          {testAlertResult ? (
            <p
              className={`mt-2 text-xs ${
                testAlertResult.status === "sent"
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-rose-700 dark:text-rose-400"
              }`}
              role="status"
              aria-live="polite"
            >
              Test alert {testAlertResult.status} via {testAlertResult.delivered_via}
              {testAlertResult.reason_message ? ` — ${testAlertResult.reason_message}` : ""}
              {testAlertResult.destination_email ? ` (to ${testAlertResult.destination_email})` : ""}.
            </p>
          ) : null}
          {testAlertError ? (
            <p className="mt-2 text-xs text-rose-700 dark:text-rose-400">{testAlertError}</p>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={!canEditAlertDelivery || alertSettingsSaving}
              onClick={() => void onSave()}
              className="ap-btn-primary"
            >
              {alertSettingsSaving ? "Saving..." : "Save alert delivery"}
            </button>
            {channelMessage ? (
              <p className="text-sm text-slate-600 dark:text-neutral-300">{channelMessage}</p>
            ) : null}
          </div>
        </>
      ) : dashboardLoading && !dashboardErrorMessage ? (
        <div className="mt-4">
          <InlineDataSpinner label="Loading alert delivery…" />
        </div>
      ) : (
        <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
          {dashboardErrorMessage ?? "Alert delivery settings are not available."}
        </p>
      )}
    </section>
  );
}
