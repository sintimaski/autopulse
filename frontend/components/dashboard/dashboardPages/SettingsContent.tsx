"use client";

import { useState } from "react";

import type { AlertSettings } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";

type DeliveryPreset = "smtp_email" | "slack_webhook" | "teams_webhook";

export function SettingsContent() {
  const d = useDashboardData();
  const form = d.alertSettings;
  const [formError, setFormError] = useState<string | null>(null);
  const [deliveryPreset, setDeliveryPreset] = useState<DeliveryPreset>("smtp_email");

  const onSaveAlerts = async () => {
    if (!form) {
      return;
    }
    if (form.error_spike_ratio_threshold < 0 || form.error_spike_ratio_threshold > 1) {
      setFormError("Error spike threshold must be between 0 and 1.");
      return;
    }
    const integerFields: Array<keyof AlertSettings> = [
      "error_spike_min_requests",
      "error_spike_window_minutes",
      "outage_min_requests",
      "outage_window_minutes",
      "cooldown_minutes",
    ];
    for (const field of integerFields) {
      if (Number(form[field]) < 1) {
        setFormError("Minute/request threshold fields must be at least 1.");
        return;
      }
    }
    setFormError(null);
    await d.saveAlertSettings(form);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Settings model (MVP)</h2>
        <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
          This page defines project-level defaults used across Dashboard, Diagnosis, Logs, and Alerts.
        </p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
              <tr>
                <th className="px-3 py-2 font-semibold">Setting group</th>
                <th className="px-3 py-2 font-semibold">Parameters</th>
                <th className="px-3 py-2 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Server scope defaults</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  Time window, method/status/path/env/service filters, latency bounds, grouped-error sort.
                </td>
                <td className="px-3 py-2 text-emerald-700 dark:text-emerald-400">Active</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Alert policy</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  Enable flag, destination email, spike/outage thresholds, cooldown.
                </td>
                <td className="px-3 py-2 text-emerald-700 dark:text-emerald-400">Active</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Delivery channels</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  SMTP email now; Slack/Teams webhook presets scaffolded for next phase.
                </td>
                <td className="px-3 py-2 text-amber-700 dark:text-amber-400">Email live, vendors next</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Alert policy</h2>
        {form ? (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-2 text-xs text-slate-700 dark:text-neutral-200">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => d.updateAlertSettingsDraft({ ...form, enabled: event.target.checked })}
                />
                Alerts enabled
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Destination email
                <input
                  type="email"
                  value={form.destination_email ?? ""}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      destination_email: event.target.value.trim() || null,
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                  placeholder="ops@example.com"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Error spike threshold (0-1)
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={form.error_spike_ratio_threshold}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      error_spike_ratio_threshold: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Error spike min requests
                <input
                  type="number"
                  min={1}
                  value={form.error_spike_min_requests}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      error_spike_min_requests: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Error spike window (minutes)
                <input
                  type="number"
                  min={1}
                  value={form.error_spike_window_minutes}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      error_spike_window_minutes: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Outage min requests
                <input
                  type="number"
                  min={1}
                  value={form.outage_min_requests}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      outage_min_requests: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Outage window (minutes)
                <input
                  type="number"
                  min={1}
                  value={form.outage_window_minutes}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      outage_window_minutes: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
              <label className="text-xs text-slate-700 dark:text-neutral-200">
                Cooldown (minutes)
                <input
                  type="number"
                  min={1}
                  value={form.cooldown_minutes}
                  onChange={(event) =>
                    d.updateAlertSettingsDraft({
                      ...form,
                      cooldown_minutes: Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
                />
              </label>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={onSaveAlerts}
                disabled={d.alertSettingsSaving}
                className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-900 shadow-sm transition hover:bg-sky-100 disabled:opacity-60 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700"
              >
                {d.alertSettingsSaving ? "Saving..." : "Save policy"}
              </button>
              {formError ? <p className="text-xs text-rose-700 dark:text-rose-400">{formError}</p> : null}
              {d.alertSettingsMessage ? (
                <p className="text-xs text-emerald-700 dark:text-emerald-400">{d.alertSettingsMessage}</p>
              ) : null}
            </div>
          </>
        ) : (
          <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">Loading settings...</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Delivery channels</h2>
        <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
          SMTP email is currently active. Vendor channels are modeled here for the next integration phase.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <button
            type="button"
            onClick={() => setDeliveryPreset("smtp_email")}
            className={`rounded-xl border px-3 py-2 text-left text-xs ${
              deliveryPreset === "smtp_email"
                ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-neutral-500 dark:bg-neutral-800 dark:text-neutral-100"
                : "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
            }`}
          >
            SMTP Email
          </button>
          <button
            type="button"
            onClick={() => setDeliveryPreset("slack_webhook")}
            className={`rounded-xl border px-3 py-2 text-left text-xs ${
              deliveryPreset === "slack_webhook"
                ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-neutral-500 dark:bg-neutral-800 dark:text-neutral-100"
                : "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
            }`}
          >
            Slack Webhook
          </button>
          <button
            type="button"
            onClick={() => setDeliveryPreset("teams_webhook")}
            className={`rounded-xl border px-3 py-2 text-left text-xs ${
              deliveryPreset === "teams_webhook"
                ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-neutral-500 dark:bg-neutral-800 dark:text-neutral-100"
                : "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
            }`}
          >
            Teams Webhook
          </button>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-xs text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/70 dark:text-neutral-200">
          {deliveryPreset === "smtp_email" ? (
            <p>Active now: route alerts to `destination_email` via backend SMTP sender.</p>
          ) : deliveryPreset === "slack_webhook" ? (
            <p>Planned: add provider-neutral webhook sender and Slack-compatible message template.</p>
          ) : (
            <p>Planned: add Teams webhook sender with provider template adapter.</p>
          )}
        </div>
      </section>
    </div>
  );
}
