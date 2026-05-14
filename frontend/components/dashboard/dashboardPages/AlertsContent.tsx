"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type {
  AlertChannelCapability,
  AlertDispatchItem,
  AlertSettings,
  DashboardAlertTestResponse,
} from "../dashboardTypes";
import { buildApiUrl } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { dashboardSessionFetch } from "../dashboardSessionFetch";
import { parseDashboardAlertTestResponse } from "../../../utils/dashboardResponseGuards";
import { canManageProjectAlertsAndRetention } from "../dashboardRoleHelpers";
import { buildScopedQuery } from "../dashboardQueryState";
import { CardSpinner } from "../../ui/CardSpinner";
import { SparklineMini } from "../SparklineMini";
import { useDashboardAlertsSlice } from "../data/useDashboardSlices";
import {
  Activity,
  Bell,
  Clock,
  Flame,
  Mail,
  RotateCw,
  Send,
  Server,
} from "lucide-react";
import {
  Banner,
  Chip,
  ConsoleButton,
  Panel,
  StatusPill,
  Tabs,
  Toggle,
} from "../../ui/console";

/** Labelled number input used across the alert rule cards. */
function NumberField({
  label,
  hint,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  onChange: (next: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
        {label}
      </span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="ap-input px-2 py-1 font-mono text-[13px] disabled:opacity-60"
      />
      {hint ? <span className="text-[11px] text-slate-400 dark:text-neutral-500">{hint}</span> : null}
    </label>
  );
}

/** Alert rule card — shared chrome for the error-spike and outage rules. */
function RuleCard({
  title,
  description,
  icon,
  tone,
  enabled,
  children,
}: {
  title: string;
  description: string;
  icon: typeof Flame;
  tone: "danger" | "warning";
  enabled: boolean;
  children: ReactNode;
}) {
  const Icon = icon;
  const iconWrap =
    tone === "danger"
      ? "bg-rose-500/12 text-rose-600 dark:text-rose-300"
      : "bg-amber-500/14 text-amber-700 dark:text-amber-300";
  return (
    <Panel
      title={title}
      subtitle={description}
      actions={
        <StatusPill tone={enabled ? "healthy" : "neutral"}>{enabled ? "active" : "paused"}</StatusPill>
      }
      bodyClassName="p-3.5"
    >
      <div className="flex items-start gap-3">
        <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${iconWrap}`}>
          <Icon className="size-4.5" aria-hidden />
        </span>
        <div className="grid flex-1 gap-3 sm:grid-cols-3">{children}</div>
      </div>
    </Panel>
  );
}

/** Map a channel-readiness capability to a StatusPill tone. */
function channelCapabilityTone(
  capability: AlertChannelCapability,
): "healthy" | "warning" | "neutral" {
  if (!capability.enabled) {
    return "neutral";
  }
  if (capability.status === "active") {
    return "healthy";
  }
  if (capability.status === "unavailable") {
    return "warning";
  }
  return "neutral";
}

export function AlertsContent() {
  const d = useDashboardData();
  const canEditAlertPolicy = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const alertsSlice = useDashboardAlertsSlice();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const [showFailedOnly, setShowFailedOnly] = useState(false);
  const [tab, setTab] = useState<"rules" | "history">("rules");
  const form = alertsSlice.alertSettings;

  const overview = d.overview;
  const { requestCount, errorCount } = useMemo(
    () => ({
      requestCount: d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.request_count || 0), 0),
      errorCount: d.sparklineSeries.reduce((sum, bucket) => sum + Number(bucket.error_count || 0), 0),
    }),
    [d.sparklineSeries],
  );
  const displayRequestCount = requestCount || overview?.request_count || 0;
  const displayErrorCount = requestCount ? errorCount : overview?.error_count || 0;
  const displayErrorRate = displayRequestCount ? displayErrorCount / displayRequestCount : 0;
  const successfulRequests = d.operationalSignals.successfulRequests;
  const errorSpikeCandidate = d.operationalSignals.errorSpikeCandidate;
  const outageCandidate = d.operationalSignals.outageCandidate;
  const canAckDispatches = d.sessionMembershipRole !== "viewer";
  const [ackingIds, setAckingIds] = useState<Set<number>>(new Set());
  const [localAcks, setLocalAcks] = useState<Record<number, AlertDispatchItem>>({});
  const [ackError, setAckError] = useState<string | null>(null);
  // Send-test-alert lives here too (not just Settings) — alerts are the MVP definition
  // of done, so "verify delivery" belongs on the alerts home.
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
        throw new Error(`Test alert failed (${response.status})`);
      }
      const raw: unknown = await response.json();
      const body = parseDashboardAlertTestResponse(raw);
      if (!body) {
        throw new Error("Test alert returned an unexpected response.");
      }
      setTestAlertResult(body);
    } catch (error) {
      setTestAlertError(
        error instanceof Error ? error.message : "Could not send test alert — network error.",
      );
    } finally {
      setTestAlertSending(false);
    }
  }, []);

  const errorRateSeries = useMemo(
    () =>
      d.sparklineSeries.map((bucket) => {
        const req = Number(bucket.request_count || 0);
        const err = Number(bucket.error_count || 0);
        return req > 0 ? (err / req) * 100 : 0;
      }),
    [d.sparklineSeries],
  );
  const requestVolumeSeries = useMemo(
    () => d.sparklineSeries.map((bucket) => Number(bucket.request_count || 0)),
    [d.sparklineSeries],
  );

  const acknowledgeDispatch = useCallback(async (dispatchId: number) => {
    setAckingIds((prev) => new Set(prev).add(dispatchId));
    setAckError(null);
    try {
      const res = await fetch(
        buildApiUrl(`/dashboard/alert-dispatches/${dispatchId}/acknowledge`),
        { method: "POST", credentials: "include" },
      );
      if (res.ok) {
        const updated: AlertDispatchItem = await res.json();
        setLocalAcks((prev) => ({ ...prev, [dispatchId]: updated }));
      } else {
        setAckError(`Could not acknowledge dispatch #${dispatchId} (${res.status}).`);
      }
    } catch {
      setAckError(`Could not acknowledge dispatch #${dispatchId} — network error.`);
    } finally {
      setAckingIds((prev) => {
        const next = new Set(prev);
        next.delete(dispatchId);
        return next;
      });
    }
  }, []);

  const dispatchesLoaded = alertsSlice.alertDispatches !== null;
  const recentDispatches = alertsSlice.alertDispatches?.items ?? [];
  const mergedDispatches = recentDispatches.map((dispatch) => localAcks[dispatch.id] ?? dispatch);
  const visibleDispatches = showFailedOnly
    ? mergedDispatches.filter((dispatch) => dispatch.status === "failed")
    : mergedDispatches;
  const failedCount = mergedDispatches.filter((dispatch) => dispatch.status === "failed").length;
  const dispatchesTotal = alertsSlice.alertDispatches?.total ?? mergedDispatches.length;
  const dispatchesTruncated = dispatchesTotal > mergedDispatches.length;
  const diagnosisParams = buildScopedQuery({
    isAbsoluteWindow: d.isAbsoluteWindow,
    windowMinutes: d.windowMinutes,
    windowFromTimestamp: d.windowFromTimestamp,
    windowToTimestamp: d.windowToTimestamp,
    method: d.method,
    statusClass: d.statusClass,
    minLatencyMs: d.minLatencyMs,
    maxLatencyMs: d.maxLatencyMs,
    pathQuery: d.pathQuery,
    serverEnvironmentQuery: d.serverEnvironmentQuery,
    serverServiceQuery: d.serverServiceQuery,
    requestLimit: d.requestLimit,
    requestPage: 0,
    errorGroupLimit: d.errorGroupLimit,
    errorGroupPage: 0,
    errorGroupSort: d.errorGroupSort,
    correlationRequestId: d.correlationRequestId,
    sqlFilterApplied: d.sqlFilterApplied,
    sqlFilterEnabled: d.sqlFilterEnabled,
  }).toString();
  const diagnosisBaseHref = `/diagnosis?${diagnosisParams}`;

  // A dispatch row links to /diagnosis scoped to that dispatch's own evaluation
  // window (window_start..window_end) rather than the current dashboard scope.
  const dispatchDiagnosisHref = (dispatch: AlertDispatchItem) =>
    `/diagnosis?${buildScopedQuery({
      isAbsoluteWindow: true,
      windowMinutes: d.windowMinutes,
      windowFromTimestamp: dispatch.window_start,
      windowToTimestamp: dispatch.window_end,
      method: "ALL",
      statusClass: "ALL",
      minLatencyMs: "",
      maxLatencyMs: "",
      pathQuery: "",
      serverEnvironmentQuery: "",
      serverServiceQuery: "",
      requestLimit: d.requestLimit,
      requestPage: 0,
      errorGroupLimit: d.errorGroupLimit,
      errorGroupPage: 0,
      errorGroupSort: "count",
      correlationRequestId: "",
    }).toString()}#grouped-errors`;

  const goToDiagnosisGrouped = () => {
    d.setErrorGroupSort("count");
    const groupedParams = new URLSearchParams(diagnosisParams);
    groupedParams.set("error_group_sort", "count");
    router.push(`/diagnosis?${groupedParams.toString()}#grouped-errors`);
  };

  const onSave = async () => {
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

  const updateForm = (patch: Partial<AlertSettings>) => {
    if (form) {
      d.updateAlertSettingsDraft({ ...form, ...patch });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Current-state summary */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Panel
          icon={Activity}
          title="Error rate"
          subtitle="Current dashboard window vs saved threshold"
          actions={
            <StatusPill tone={errorSpikeCandidate ? "danger" : "healthy"}>
              {errorSpikeCandidate ? "over threshold" : "within threshold"}
            </StatusPill>
          }
          bodyClassName="flex items-center justify-between gap-3 p-3.5"
        >
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
              {(displayErrorRate * 100).toFixed(1)}%
            </p>
            <p className="text-[11px] text-slate-400 dark:text-neutral-500">
              threshold {form ? `${(form.error_spike_ratio_threshold * 100).toFixed(1)}%` : "—"}
            </p>
          </div>
          <div className="w-28">
            <SparklineMini
              values={errorRateSeries}
              colorClass="text-rose-500 dark:text-rose-300"
              svgClassName="h-10 w-full"
              interactive={false}
            />
          </div>
        </Panel>
        <Panel
          icon={Flame}
          title="Spike candidates"
          subtitle="Preview over the current dashboard window"
          actions={
            <StatusPill tone={errorSpikeCandidate ? "warning" : "healthy"}>
              {errorSpikeCandidate ? "1 candidate" : "none"}
            </StatusPill>
          }
          bodyClassName="flex items-center justify-between gap-3 p-3.5"
        >
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
              {errorSpikeCandidate ? 1 : 0}
            </p>
            <p className="text-[11px] text-slate-400 dark:text-neutral-500">
              {displayErrorCount} errors · {successfulRequests} ok
            </p>
          </div>
          <div className="w-28">
            <SparklineMini
              values={errorRateSeries}
              colorClass="text-amber-500 dark:text-amber-300"
              svgClassName="h-10 w-full"
              interactive={false}
            />
          </div>
        </Panel>
        <Panel
          icon={Server}
          title="Outage candidates"
          subtitle="Preview over the current dashboard window"
          actions={
            <StatusPill tone={outageCandidate ? "danger" : "healthy"}>
              {outageCandidate ? "1 candidate" : "none"}
            </StatusPill>
          }
          bodyClassName="flex items-center justify-between gap-3 p-3.5"
        >
          <div>
            <p className="font-mono text-2xl font-semibold tabular-nums text-slate-900 dark:text-neutral-100">
              {outageCandidate ? 1 : 0}
            </p>
            <p className="text-[11px] text-slate-400 dark:text-neutral-500">
              {displayRequestCount} requests in window
            </p>
          </div>
          <div className="w-28">
            <SparklineMini
              values={requestVolumeSeries}
              colorClass="text-emerald-500 dark:text-emerald-300"
              svgClassName="h-10 w-full"
              interactive={false}
            />
          </div>
        </Panel>
      </section>
      <p className="-mt-2 text-[11px] text-slate-500 dark:text-neutral-500">
        These panels apply your saved spike/outage thresholds to the{" "}
        <span className="font-medium">current dashboard time window</span> as a quick sanity check.
        The alerts job itself evaluates over its own configured windows
        {form
          ? ` (spike: ${form.error_spike_window_minutes}m, outage: ${form.outage_window_minutes}m)`
          : ""}
        , so live results can differ.
      </p>

      <Tabs
        active={tab}
        onChange={(value) => setTab(value as "rules" | "history")}
        tabs={[
          { value: "rules", label: "Alert rules", icon: Bell },
          { value: "history", label: "Dispatch history", icon: Send, count: mergedDispatches.length },
        ]}
      />

      {tab === "rules" ? (
        form ? (
          <div className="flex flex-col gap-4">
            {!canEditAlertPolicy ? (
              <Banner tone="info" icon={Mail} title="Read-only alert policy">
                Only owners and admins can change alert policy. Members can still send a test alert from{" "}
                <Link href="/settings#alert-delivery" className="font-medium text-orange-700 hover:underline dark:text-orange-300">
                  Settings → Alert delivery
                </Link>{" "}
                and review dispatches.
              </Banner>
            ) : null}

            <Panel
              icon={Bell}
              title="Notification policy"
              subtitle="Master switch and where spike / outage alerts are delivered"
              bodyClassName="grid gap-4 p-3.5 sm:grid-cols-2"
            >
              <Toggle
                checked={form.enabled}
                disabled={!canEditAlertPolicy}
                onChange={(next) => updateForm({ enabled: next })}
                label="Alerts enabled"
                description="Master switch for automated spike and outage alerts"
              />
              <label className="flex flex-col gap-1">
                <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-neutral-400">
                  Destination email
                </span>
                <input
                  type="email"
                  disabled={!canEditAlertPolicy}
                  value={form.destination_email ?? ""}
                  onChange={(event) =>
                    updateForm({ destination_email: event.target.value.trim() || null })
                  }
                  placeholder="ops@example.com"
                  className="ap-input px-2 py-1 text-[13px] disabled:opacity-60"
                />
              </label>
            </Panel>

            <div className="grid gap-4 xl:grid-cols-2">
              <RuleCard
                title="Error spike"
                description="Fires when the error rate jumps above a threshold over a short window."
                icon={Flame}
                tone="danger"
                enabled={form.enabled}
              >
                <NumberField
                  label="Threshold (0–1)"
                  hint="error rate ratio"
                  value={form.error_spike_ratio_threshold}
                  min={0}
                  max={1}
                  step={0.01}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ error_spike_ratio_threshold: next })}
                />
                <NumberField
                  label="Min requests"
                  hint="ignore low traffic"
                  value={form.error_spike_min_requests}
                  min={1}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ error_spike_min_requests: next })}
                />
                <NumberField
                  label="Window (min)"
                  hint="evaluation window"
                  value={form.error_spike_window_minutes}
                  min={1}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ error_spike_window_minutes: next })}
                />
              </RuleCard>

              <RuleCard
                title="Service outage"
                description="Fires when a service receives no traffic for longer than expected."
                icon={Server}
                tone="warning"
                enabled={form.enabled}
              >
                <NumberField
                  label="Min requests"
                  hint="baseline traffic"
                  value={form.outage_min_requests}
                  min={1}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ outage_min_requests: next })}
                />
                <NumberField
                  label="Window (min)"
                  hint="silence window"
                  value={form.outage_window_minutes}
                  min={1}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ outage_window_minutes: next })}
                />
                <NumberField
                  label="Cooldown (min)"
                  hint="shared re-fire gap"
                  value={form.cooldown_minutes}
                  min={1}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ cooldown_minutes: next })}
                />
              </RuleCard>
            </div>

            <Panel
              icon={Clock}
              title="Notification pause"
              subtitle="Mute or snooze stops automated alerts — test alerts from Settings still deliver"
              bodyClassName="flex flex-col gap-3 p-3.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Toggle
                  checked={form.notifications_muted}
                  disabled={!canEditAlertPolicy}
                  onChange={(next) => updateForm({ notifications_muted: next })}
                  label="Mute notifications"
                />
                <span className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                  Snooze
                </span>
                {([1, 4, 24] as const).map((hours) => (
                  <ConsoleButton
                    key={hours}
                    size="xs"
                    variant="secondary"
                    disabled={!canEditAlertPolicy || d.alertSettingsSaving}
                    onClick={async () => {
                      setFormError(null);
                      await d.saveAlertSettings({
                        ...form,
                        notifications_snoozed_until: new Date(
                          Date.now() + hours * 3_600_000,
                        ).toISOString(),
                      });
                    }}
                  >
                    {hours}h
                  </ConsoleButton>
                ))}
                <ConsoleButton
                  size="xs"
                  variant="ghost"
                  disabled={!canEditAlertPolicy || d.alertSettingsSaving}
                  onClick={async () => {
                    setFormError(null);
                    await d.saveAlertSettings({
                      ...form,
                      notifications_snoozed_until: null,
                    });
                  }}
                >
                  Clear snooze
                </ConsoleButton>
                <ConsoleButton
                  size="xs"
                  variant="ghost"
                  disabled={!canEditAlertPolicy || d.alertSettingsSaving}
                  onClick={async () => {
                    setFormError(null);
                    await d.saveAlertSettings({ ...form, acknowledge_notifications: true });
                  }}
                >
                  Acknowledge
                </ConsoleButton>
              </div>
              {form.notifications_snoozed_until ? (
                <p className="text-[11px] text-slate-500 dark:text-neutral-400">
                  Snoozed until{" "}
                  <span className="font-mono">
                    {new Date(form.notifications_snoozed_until).toLocaleString()}
                  </span>
                </p>
              ) : null}
              {form.last_notifications_acknowledged_at ? (
                <p className="text-[11px] text-slate-400 dark:text-neutral-500">
                  Last acknowledged{" "}
                  <span className="font-mono">
                    {new Date(form.last_notifications_acknowledged_at).toLocaleString()}
                  </span>
                </p>
              ) : null}
            </Panel>

            <div className="flex flex-wrap items-center gap-3">
              <ConsoleButton
                variant="primary"
                icon={Send}
                disabled={!canEditAlertPolicy || d.alertSettingsSaving}
                onClick={onSave}
              >
                {d.alertSettingsSaving ? "Saving…" : "Save alert settings"}
              </ConsoleButton>
              {formError ? (
                <p role="alert" className="text-[12px] text-rose-600 dark:text-rose-300">
                  {formError}
                </p>
              ) : null}
              {d.alertSettingsMessage ? (
                <p
                  role="status"
                  aria-live="polite"
                  className="text-[12px] text-emerald-600 dark:text-emerald-300"
                >
                  {d.alertSettingsMessage}
                </p>
              ) : null}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Panel
                icon={Mail}
                title="Delivery channels"
                subtitle="Server-side readiness — configure URLs / addresses in Settings"
                bodyClassName="flex flex-col gap-3 p-3.5"
              >
                <ul className="flex flex-col gap-1.5">
                  {d.alertCapabilities.length === 0 ? (
                    <li className="text-[12px] text-slate-500 dark:text-neutral-400">
                      Channel readiness is unavailable.
                    </li>
                  ) : (
                    d.alertCapabilities.map((channel) => (
                      <li
                        key={channel.channel}
                        className="flex items-center justify-between gap-2 text-[12px]"
                      >
                        <span className="font-medium capitalize text-slate-700 dark:text-neutral-200">
                          {channel.channel}
                        </span>
                        <span className="flex items-center gap-2">
                          <span className="text-[11px] text-slate-500 dark:text-neutral-400">
                            {channel.reason}
                          </span>
                          <StatusPill tone={channelCapabilityTone(channel)}>
                            {channel.enabled ? channel.status : "off"}
                          </StatusPill>
                        </span>
                      </li>
                    ))
                  )}
                </ul>
                <div className="flex flex-wrap items-center gap-2">
                  <ConsoleButton
                    size="sm"
                    variant="primary"
                    icon={Send}
                    disabled={!canAckDispatches || testAlertSending}
                    onClick={sendTestAlert}
                  >
                    {testAlertSending ? "Sending…" : "Send test alert"}
                  </ConsoleButton>
                  <Link
                    href="/settings#alert-delivery"
                    className="text-[12px] font-medium text-orange-700 hover:underline dark:text-orange-300"
                  >
                    Configure channels →
                  </Link>
                </div>
                {testAlertResult ? (
                  <p
                    role="status"
                    aria-live="polite"
                    className={`text-[12px] ${
                      testAlertResult.status === "sent"
                        ? "text-emerald-600 dark:text-emerald-300"
                        : "text-amber-600 dark:text-amber-300"
                    }`}
                  >
                    Test alert {testAlertResult.status} via {testAlertResult.delivered_via}
                    {testAlertResult.reason_message ? ` — ${testAlertResult.reason_message}` : ""}.
                  </p>
                ) : null}
                {testAlertError ? (
                  <p role="alert" className="text-[12px] text-rose-600 dark:text-rose-300">
                    {testAlertError}
                  </p>
                ) : null}
              </Panel>
              <Panel
                icon={RotateCw}
                title="Runbook shortcuts"
                subtitle={`Raw events retention target: ${d.M5_ALERT_DEFAULTS.retentionRawDays} days`}
                bodyClassName="flex flex-col gap-2.5 p-3.5"
              >
                <div className="flex flex-wrap gap-2">
                  <ConsoleButton
                    size="sm"
                    onClick={() => d.copyRunbookCommand(d.RUNBOOK_ALERTS_CMD, "Alerts job command")}
                  >
                    Copy alerts-once
                  </ConsoleButton>
                  <ConsoleButton
                    size="sm"
                    onClick={() => d.copyRunbookCommand(d.RUNBOOK_RETENTION_CMD, "Retention job command")}
                  >
                    Copy retention-once
                  </ConsoleButton>
                  <ConsoleButton size="sm" variant="primary" onClick={goToDiagnosisGrouped}>
                    Open grouped errors
                  </ConsoleButton>
                </div>
                <pre className="max-h-20 overflow-auto rounded-md bg-slate-900 p-2 font-mono text-[11px] leading-relaxed text-slate-100">
                  {d.RUNBOOK_ALERTS_CMD}
                </pre>
                {d.runbookMessage ? (
                  <p
                    className="text-[11px] font-medium text-emerald-600 dark:text-emerald-300"
                    role="status"
                    aria-live="polite"
                  >
                    {d.runbookMessage}
                  </p>
                ) : null}
              </Panel>
            </div>
          </div>
        ) : d.loading && !d.errorMessage ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <CardSpinner size="compact" label="Traffic & sparkline" />
            <CardSpinner size="compact" label="Alert rules" />
          </div>
        ) : (
          <Panel bodyClassName="p-4">
            <p className="text-[13px] text-slate-500 dark:text-neutral-400">
              {d.errorMessage ?? "Alert settings are not available for this scope."}
            </p>
          </Panel>
        )
      ) : (
        <Panel
          icon={Send}
          title="Dispatch history"
          subtitle="Alerts dispatched in the selected time window"
          actions={
            <>
              <Toggle
                checked={showFailedOnly}
                onChange={setShowFailedOnly}
                label="Failed only"
              />
              <Chip tone="muted">
                {visibleDispatches.length} of {dispatchesTotal} shown
              </Chip>
            </>
          }
          footer={
            <span>
              {failedCount > 0
                ? `${failedCount} failed dispatch${failedCount === 1 ? "" : "es"} in window`
                : "No failed dispatches in window"}
              {dispatchesTruncated
                ? ` · showing the most recent ${mergedDispatches.length} of ${dispatchesTotal} — narrow the time window to see older alerts`
                : ""}
            </span>
          }
        >
          {ackError ? (
            <p
              role="alert"
              className="border-b border-rose-200/70 bg-rose-50/70 px-3.5 py-2 text-[12px] text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300"
            >
              {ackError}
            </p>
          ) : null}
          {!dispatchesLoaded ? (
            d.loading && !d.errorMessage ? (
              <div className="p-4">
                <CardSpinner size="compact" label="Loading dispatch history…" />
              </div>
            ) : (
              <p role="alert" className="px-3.5 py-6 text-center text-[13px] text-rose-600 dark:text-rose-300">
                {d.errorMessage ?? "Could not load dispatch history for this scope."}
              </p>
            )
          ) : visibleDispatches.length === 0 ? (
            <p className="px-3.5 py-6 text-center text-[13px] text-slate-500 dark:text-neutral-400">
              No matching alerts in the selected time window.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-[12px]">
                <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[10px] uppercase tracking-wide text-slate-400 dark:border-neutral-800 dark:bg-neutral-950/40 dark:text-neutral-500">
                  <tr>
                    <th className="px-3 py-1.5 font-semibold">Triggered</th>
                    <th className="px-3 py-1.5 font-semibold">Type</th>
                    <th className="px-3 py-1.5 font-semibold">Delivery</th>
                    <th className="px-3 py-1.5 font-semibold">Status</th>
                    <th className="px-3 py-1.5 font-semibold">Reason</th>
                    <th className="px-3 py-1.5 font-semibold">Destination</th>
                    <th className="px-3 py-1.5 font-semibold">Ack</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-neutral-800">
                  {visibleDispatches.map((dispatch) => (
                    <tr key={dispatch.id} className="hover:bg-slate-50/70 dark:hover:bg-neutral-800/40">
                      <td className="whitespace-nowrap px-3 py-2 font-mono">
                        <Link
                          href={dispatchDiagnosisHref(dispatch)}
                          className="text-orange-700 hover:underline dark:text-orange-300"
                          title="Open grouped errors for this dispatch's window"
                        >
                          {new Date(dispatch.triggered_at).toLocaleString()}
                        </Link>
                      </td>
                      <td className="px-3 py-2">
                        <Chip tone="accent">{dispatch.alert_type}</Chip>
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-neutral-300">
                        <div className="flex flex-col">
                          <span>{dispatch.delivered_via}</span>
                          {dispatch.provider_message_id ? (
                            <span className="font-mono text-[10px] text-slate-400 dark:text-neutral-500">
                              {dispatch.provider_message_id}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <StatusPill
                          tone={
                            dispatch.status === "sent"
                              ? "healthy"
                              : dispatch.status === "failed"
                                ? "danger"
                                : "neutral"
                          }
                        >
                          {dispatch.status}
                        </StatusPill>
                        {dispatch.delivered_at ? (
                          <div className="mt-1 font-mono text-[10px] text-slate-400 dark:text-neutral-500">
                            {new Date(dispatch.delivered_at).toLocaleString()}
                          </div>
                        ) : null}
                      </td>
                      <td className="max-w-[260px] px-3 py-2 text-slate-600 dark:text-neutral-300">
                        {dispatch.reason_message ?? dispatch.reason_code ?? "none"}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-600 dark:text-neutral-300">
                        {dispatch.destination_email ?? "not set"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        {dispatch.acknowledged_at ? (
                          <StatusPill tone="healthy">
                            acked {new Date(dispatch.acknowledged_at).toLocaleTimeString()}
                          </StatusPill>
                        ) : canAckDispatches ? (
                          <ConsoleButton
                            size="xs"
                            variant="secondary"
                            disabled={ackingIds.has(dispatch.id)}
                            onClick={() => acknowledgeDispatch(dispatch.id)}
                          >
                            {ackingIds.has(dispatch.id) ? "…" : "Ack"}
                          </ConsoleButton>
                        ) : (
                          <span className="text-slate-400 dark:text-neutral-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
