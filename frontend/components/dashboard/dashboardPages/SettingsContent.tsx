"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  DashboardAlertTestResponse,
  DashboardSystemDiagnosticsResponse,
  RetentionSettings,
} from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { buildApiUrl, isApiSubpathDashboard } from "../dashboardTypes";
import { DASHBOARD_FETCH_TIMEOUT_MS, fetchWithTimeout } from "../dashboardDataFetchUtils";
import {
  canInviteOrganizationMembers,
  canManageIngestApiKeys,
  canManageProjectAlertsAndRetention,
  isDashboardViewer,
} from "../dashboardRoleHelpers";
import {
  PROTECTED_OWNER_EMAIL,
  isProtectedOwnerEmail,
  looksLikeCompleteDiscordIncomingWebhook,
  looksLikeCompleteSlackIncomingWebhook,
} from "./settingsContentUtils";
import { normalizeSchedulerJobs, normalizeSystemDiagnostics } from "../../../utils/systemDiagnostics";
import { buildDashboardNetworkError } from "../../../utils/dashboardFetchErrors";
import {
  parseDashboardAlertTestResponse,
  parseDashboardInternalMetricsResponse,
  parseDashboardSystemDiagnosticsResponse,
  parseEventPlaneCutoverSettings,
} from "../../../utils/dashboardResponseGuards";

import type { InternalMetricsSnapshot } from "./settingsContentTypes";
import { SettingsAlertDeliverySection } from "./SettingsAlertDeliverySection";
import { SettingsActiveProjectSection } from "./SettingsActiveProjectSection";
import { SettingsOrganizationsMembersSection } from "./SettingsOrganizationsMembersSection";
import { SettingsAppearanceSessionSection } from "./SettingsAppearanceSessionSection";
import { SettingsExcludeLumonoxTrafficSection } from "./SettingsExcludeLumonoxTrafficSection";
import { SettingsEventPlaneCutoverSection } from "./SettingsEventPlaneCutoverSection";
import { SettingsApiKeyLifecycleSection } from "./SettingsApiKeyLifecycleSection";
import { SettingsInternalMetricsSection } from "./SettingsInternalMetricsSection";
import { SettingsSystemDiagnosticsSection } from "./SettingsSystemDiagnosticsSection";
import { SettingsRetentionPolicySection } from "./SettingsRetentionPolicySection";
import { useSettingsOrganizationsMembers } from "./useSettingsOrganizationsMembers";

type SystemDiagnosticsSnapshot = DashboardSystemDiagnosticsResponse;

export function SettingsContent() {
  const d = useDashboardData();
  const [themeMessage, setThemeMessage] = useState<string | null>(null);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);
  const [retentionDraft, setRetentionDraft] = useState<RetentionSettings | null>(null);
  const orgMembers = useSettingsOrganizationsMembers(d.sessionProjectId);
  const [selectedKeyIds, setSelectedKeyIds] = useState<Set<string>>(new Set());
  const [keyBulkAction, setKeyBulkAction] = useState<"" | "rotate" | "revoke">("");
  const [apiKeyMessage, setApiKeyMessage] = useState<string | null>(null);
  const [channelMessage, setChannelMessage] = useState<string | null>(null);
  const [testAlertSending, setTestAlertSending] = useState(false);
  const [testAlertResult, setTestAlertResult] = useState<DashboardAlertTestResponse | null>(null);
  const [testAlertError, setTestAlertError] = useState<string | null>(null);
  const [activeProjectBusy, setActiveProjectBusy] = useState(false);
  const [activeProjectMessage, setActiveProjectMessage] = useState<string | null>(null);
  const [internalMetricsLoadState, setInternalMetricsLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [internalMetricsEnabled, setInternalMetricsEnabled] = useState(false);
  const [internalMetricsReason, setInternalMetricsReason] = useState<string | null>(null);
  const [internalMetricsSnapshot, setInternalMetricsSnapshot] = useState<InternalMetricsSnapshot | null>(null);
  const [systemDiagnosticsLoadState, setSystemDiagnosticsLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [systemDiagnosticsSnapshot, setSystemDiagnosticsSnapshot] =
    useState<SystemDiagnosticsSnapshot | null>(null);
  const [systemDiagnosticsMessage, setSystemDiagnosticsMessage] = useState<string | null>(null);
  const [eventPlaneCutoverLoadState, setEventPlaneCutoverLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [eventPlaneCutoverSaving, setEventPlaneCutoverSaving] = useState(false);
  const [eventPlaneUseSnapshotRead, setEventPlaneUseSnapshotRead] = useState(false);
  const [eventPlaneCutoverMessage, setEventPlaneCutoverMessage] = useState<string | null>(null);
  const effectiveRetentionDraft = retentionDraft ?? d.retentionSettings;
  const canEditRetention = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canMutateApiKeys = canManageIngestApiKeys(d.sessionMembershipRole);
  const viewerSession = isDashboardViewer(d.sessionMembershipRole);

  /** Invites are tied to the signed-in dashboard session role, not the org picker alone. */
  const canInviteMembers = canInviteOrganizationMembers(d.sessionMembershipRole);

  const primaryActiveKeyId = useMemo(() => {
    const active = d.apiKeys.filter((k) => !k.revoked_at);
    if (active.length === 0) {
      return null;
    }
    const sorted = [...active].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    return sorted[0]?.key_id ?? null;
  }, [d.apiKeys]);

  const onActiveProjectChange = useCallback(
    async (nextId: string) => {
      if (!nextId || nextId === d.sessionProjectId) {
        return;
      }
      setActiveProjectBusy(true);
      setActiveProjectMessage(null);
      const ok = await d.setActiveDashboardProject(nextId);
      setActiveProjectBusy(false);
      setActiveProjectMessage(
        ok ? "Switched active project. Charts and keys will refresh." : "Could not switch project. Try again.",
      );
    },
    // Context value identity changes frequently; only stable fields should drive this callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- d.setActiveDashboardProject + sessionProjectId are sufficient
    [d.sessionProjectId, d.setActiveDashboardProject],
  );

  const toggleKeySelected = (keyId: string) => {
    setSelectedKeyIds((prev) => {
      const next = new Set(prev);
      if (next.has(keyId)) {
        next.delete(keyId);
      } else {
        next.add(keyId);
      }
      return next;
    });
  };

  const activeKeyIds = d.apiKeys.filter((k) => !k.revoked_at).map((k) => k.key_id);
  const allKeysSelected = activeKeyIds.length > 0 && activeKeyIds.every((id) => selectedKeyIds.has(id));

  const applyKeyBulk = async () => {
    if (!keyBulkAction || selectedKeyIds.size === 0) {
      return;
    }
    const activeKeys = d.apiKeys.filter((k) => !k.revoked_at);
    const activeIdSet = new Set(activeKeys.map((k) => k.key_id));
    let targetIds = [...selectedKeyIds].filter((id) => activeIdSet.has(id));

    if (keyBulkAction === "revoke") {
      if (activeKeys.length === 1) {
        setApiKeyMessage("Cannot revoke your only active ingest key.");
        return;
      }
      if (activeKeys.length > 1 && primaryActiveKeyId) {
        targetIds = targetIds.filter((id) => id !== primaryActiveKeyId);
      }
      if (targetIds.length === 0) {
        setApiKeyMessage(
          "Primary (oldest) active key cannot be bulk-revoked. Deselect it or revoke other keys first.",
        );
        return;
      }
      if (activeKeys.length - targetIds.length < 1) {
        setApiKeyMessage("Leave at least one active key. Deselect some keys.");
        return;
      }
    }

    const label = keyBulkAction === "rotate" ? "Rotate" : "Revoke";
    if (!window.confirm(`${label} ${targetIds.length} key(s)?`)) {
      return;
    }

    let ok = 0;
    let failed = 0;
    for (const keyId of targetIds) {
      if (keyBulkAction === "rotate") {
        const success = await d.rotateApiKey(keyId);
        if (success) {
          ok += 1;
        } else {
          failed += 1;
        }
      } else {
        const success = await d.revokeApiKey(keyId);
        if (success) {
          ok += 1;
        } else {
          failed += 1;
        }
      }
    }
    await d.refreshApiKeys();
    setSelectedKeyIds(new Set());
    setKeyBulkAction("");
    setApiKeyMessage(
      ok || failed ? `${ok} succeeded${failed ? `, ${failed} failed` : ""}.` : "No changes applied.",
    );
  };

  const orgOwnerAccess = orgMembers.selectedOrganization?.role === "owner";
  const alertDeliveryDraft = d.alertSettings;
  const canEditAlertDelivery = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canViewInternalMetrics = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canViewSystemDiagnostics = canViewInternalMetrics;
  const canManageEventPlaneCutover = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const aggregateQueueDepth = internalMetricsSnapshot?.ingest_aggregate_queue?.depth ?? null;
  const aggregateQueueMax = internalMetricsSnapshot?.ingest_aggregate_queue?.max_size ?? null;
  const aggregateQueueEnabled = Boolean(internalMetricsSnapshot?.ingest_aggregate_queue?.enabled);
  const queueUsageRatio =
    typeof aggregateQueueDepth === "number" &&
    typeof aggregateQueueMax === "number" &&
    aggregateQueueMax > 0
      ? aggregateQueueDepth / aggregateQueueMax
      : null;
  const aggregateQueueHealthy = queueUsageRatio === null ? null : queueUsageRatio < 0.8;
  const aggregateWorkerHealthy = aggregateQueueEnabled ? aggregateQueueHealthy : null;
  const systemDiagnosticsSummary = useMemo(
    () => normalizeSystemDiagnostics(systemDiagnosticsSnapshot),
    [systemDiagnosticsSnapshot],
  );
  const schedulerJobs = useMemo(
    () => normalizeSchedulerJobs(systemDiagnosticsSnapshot),
    [systemDiagnosticsSnapshot],
  );
  const metricStatusClass = (ok: boolean | null): string => {
    if (ok === true) {
      return "border-emerald-300 bg-emerald-50/90 dark:border-emerald-900/70 dark:bg-emerald-950/35";
    }
    if (ok === false) {
      return "border-rose-300 bg-rose-50/90 dark:border-rose-900/70 dark:bg-rose-950/35";
    }
    return "border-slate-200 bg-slate-50/70 dark:border-neutral-700 dark:bg-neutral-800/60";
  };

  useEffect(() => {
    let cancelled = false;
    if (!canViewInternalMetrics) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setInternalMetricsLoadState("idle");
        setInternalMetricsEnabled(false);
        setInternalMetricsReason(null);
        setInternalMetricsSnapshot(null);
      });
      return;
    }
    queueMicrotask(() => {
      if (cancelled) {
        return;
      }
      setInternalMetricsLoadState("loading");
    });
    void (async () => {
      try {
        const response = await fetchWithTimeout(buildApiUrl("/dashboard/internal-metrics"), {
          credentials: "include",
        }, DASHBOARD_FETCH_TIMEOUT_MS);
        if (!response.ok) {
          throw new Error(`internal-metrics failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseDashboardInternalMetricsResponse(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("internal-metrics returned unexpected JSON shape");
        }
        const metrics =
          payload.metrics && typeof payload.metrics === "object"
            ? (payload.metrics as InternalMetricsSnapshot)
            : null;
        setInternalMetricsEnabled(Boolean(payload.enabled));
        setInternalMetricsReason(payload.reason ?? null);
        setInternalMetricsSnapshot(metrics);
        setInternalMetricsLoadState("ready");
      } catch {
        if (!cancelled) {
          setInternalMetricsLoadState("error");
          setInternalMetricsEnabled(false);
          setInternalMetricsReason("Could not load internal metrics from the server.");
          setInternalMetricsSnapshot(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canViewInternalMetrics]);

  useEffect(() => {
    let cancelled = false;
    if (!canViewSystemDiagnostics) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setSystemDiagnosticsLoadState("idle");
        setSystemDiagnosticsSnapshot(null);
      });
      return;
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setSystemDiagnosticsLoadState("loading");
      }
    });
    void (async () => {
      try {
        const response = await fetchWithTimeout(buildApiUrl("/dashboard/system-diagnostics"), {
          credentials: "include",
        }, DASHBOARD_FETCH_TIMEOUT_MS);
        if (!response.ok) {
          throw new Error(`system-diagnostics failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseDashboardSystemDiagnosticsResponse(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("system-diagnostics returned unexpected JSON shape");
        }
        setSystemDiagnosticsSnapshot(payload);
        setSystemDiagnosticsLoadState("ready");
      } catch {
        if (!cancelled) {
          setSystemDiagnosticsLoadState("error");
          setSystemDiagnosticsSnapshot(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canViewSystemDiagnostics]);

  useEffect(() => {
    let cancelled = false;
    if (!canManageEventPlaneCutover) {
      queueMicrotask(() => {
        if (cancelled) {
          return;
        }
        setEventPlaneCutoverLoadState("idle");
        setEventPlaneUseSnapshotRead(false);
      });
      return;
    }
    queueMicrotask(() => {
      if (!cancelled) {
        setEventPlaneCutoverLoadState("loading");
      }
    });
    void (async () => {
      try {
        const response = await fetchWithTimeout(buildApiUrl("/dashboard/event-plane-cutover"), {
          credentials: "include",
        }, DASHBOARD_FETCH_TIMEOUT_MS);
        if (!response.ok) {
          throw new Error(`event-plane-cutover failed (${response.status})`);
        }
        const raw: unknown = await response.json();
        const payload = parseEventPlaneCutoverSettings(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          throw new Error("event-plane-cutover returned unexpected JSON shape");
        }
        setEventPlaneUseSnapshotRead(Boolean(payload.use_snapshot_read));
        setEventPlaneCutoverLoadState("ready");
      } catch {
        if (!cancelled) {
          setEventPlaneCutoverLoadState("error");
          setEventPlaneCutoverMessage("Could not load Event Plane cutover setting.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canManageEventPlaneCutover]);

  const sendTestAlert = async () => {
    setTestAlertSending(true);
    setTestAlertError(null);
    setTestAlertResult(null);
    try {
      const response = await fetchWithTimeout(
        buildApiUrl("/dashboard/alert-test"),
        { method: "POST", credentials: "include" },
        DASHBOARD_FETCH_TIMEOUT_MS,
      );
      if (!response.ok) {
        throw new Error(`alert-test failed (${response.status})`);
      }
      const raw: unknown = await response.json();
      const body = parseDashboardAlertTestResponse(raw);
      if (!body) {
        throw new Error("alert-test returned unexpected JSON shape");
      }
      setTestAlertResult(body);
      d.setRefreshToken((token) => token + 1);
    } catch (error) {
      setTestAlertError(buildDashboardNetworkError(error));
    } finally {
      setTestAlertSending(false);
    }
  };

  const saveDeliveryChannels = async () => {
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
    const ok = await d.saveAlertSettings(alertDeliveryDraft);
    setChannelMessage(ok ? "Alert delivery settings saved." : "Failed to save alert delivery settings.");
  };

  return (
    <div className="space-y-6">
      <SettingsRetentionPolicySection
        effectiveDraft={effectiveRetentionDraft}
        canEditRetention={canEditRetention}
        dashboardLoading={d.loading}
        dashboardErrorMessage={d.errorMessage}
        retentionMessage={retentionMessage}
        onDraftChange={(next) => setRetentionDraft(next)}
        onSave={async () => {
          const draft = retentionDraft ?? d.retentionSettings;
          if (!draft) {
            return;
          }
          const ok = await d.saveRetentionSettings(draft);
          setRetentionMessage(ok ? "Retention settings saved." : "Failed to save retention settings.");
        }}
      />

      <SettingsInternalMetricsSection
        canViewInternalMetrics={canViewInternalMetrics}
        internalMetricsLoadState={internalMetricsLoadState}
        internalMetricsEnabled={internalMetricsEnabled}
        internalMetricsReason={internalMetricsReason}
        internalMetricsSnapshot={internalMetricsSnapshot}
        metricStatusClass={metricStatusClass}
        aggregateQueueHealthy={aggregateQueueHealthy}
        aggregateWorkerHealthy={aggregateWorkerHealthy}
        queueUsageRatio={queueUsageRatio}
      />

      <SettingsSystemDiagnosticsSection
        canViewSystemDiagnostics={canViewSystemDiagnostics}
        systemDiagnosticsLoadState={systemDiagnosticsLoadState}
        systemDiagnosticsSnapshot={systemDiagnosticsSnapshot}
        systemDiagnosticsSummary={systemDiagnosticsSummary}
        schedulerJobs={schedulerJobs}
        metricStatusClass={metricStatusClass}
        systemDiagnosticsMessage={systemDiagnosticsMessage}
        setSystemDiagnosticsMessage={setSystemDiagnosticsMessage}
      />

      <SettingsEventPlaneCutoverSection
        canManageEventPlaneCutover={canManageEventPlaneCutover}
        eventPlaneCutoverLoadState={eventPlaneCutoverLoadState}
        eventPlaneCutoverMessage={eventPlaneCutoverMessage}
        eventPlaneUseSnapshotRead={eventPlaneUseSnapshotRead}
        setEventPlaneUseSnapshotRead={setEventPlaneUseSnapshotRead}
        eventPlaneCutoverSaving={eventPlaneCutoverSaving}
        onSaveCutover={async () => {
          setEventPlaneCutoverSaving(true);
          setEventPlaneCutoverMessage(null);
          try {
            const response = await fetchWithTimeout(
              buildApiUrl("/dashboard/event-plane-cutover"),
              {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ use_snapshot_read: eventPlaneUseSnapshotRead }),
              },
              DASHBOARD_FETCH_TIMEOUT_MS,
            );
            if (!response.ok) {
              throw new Error(`event-plane-cutover update failed (${response.status})`);
            }
            const raw: unknown = await response.json();
            const payload = parseEventPlaneCutoverSettings(raw);
            if (!payload) {
              throw new Error("event-plane-cutover save returned unexpected JSON shape");
            }
            setEventPlaneUseSnapshotRead(Boolean(payload.use_snapshot_read));
            setEventPlaneCutoverMessage("Event Plane cutover saved.");
          } catch {
            setEventPlaneCutoverMessage("Failed to save Event Plane cutover.");
          } finally {
            setEventPlaneCutoverSaving(false);
          }
        }}
      />

      <SettingsExcludeLumonoxTrafficSection
        canEditRetention={canEditRetention}
        excludeLumonoxTraffic={d.excludeLumonoxTraffic}
        themeSettingsSaving={d.themeSettingsSaving}
        onToggleExclude={async (next) => {
          const ok = await d.saveExcludeLumonoxTraffic(next);
          setThemeMessage(ok ? "Saved." : "Could not save. Try again.");
        }}
      />

      <SettingsAlertDeliverySection
        alertDeliveryDraft={alertDeliveryDraft}
        dashboardLoading={d.loading}
        dashboardErrorMessage={d.errorMessage}
        canEditAlertDelivery={canEditAlertDelivery}
        viewerSession={viewerSession}
        alertCapabilities={d.alertCapabilities}
        alertSettingsSaving={d.alertSettingsSaving}
        updateAlertSettingsDraft={d.updateAlertSettingsDraft}
        onSave={() => void saveDeliveryChannels()}
        onSendTestAlert={() => void sendTestAlert()}
        channelMessage={channelMessage}
        testAlertSending={testAlertSending}
        testAlertResult={testAlertResult}
        testAlertError={testAlertError}
      />

      <SettingsActiveProjectSection
        organizationsLoadState={orgMembers.organizationsLoadState}
        accessibleProjects={orgMembers.accessibleProjects}
        currentProjectLabel={orgMembers.currentProjectLabel}
        sessionProjectId={d.sessionProjectId}
        activeProjectBusy={activeProjectBusy}
        activeProjectMessage={activeProjectMessage}
        onActiveProjectChange={onActiveProjectChange}
      />

      <SettingsOrganizationsMembersSection
        organizationsLoadState={orgMembers.organizationsLoadState}
        organizations={orgMembers.organizations}
        selectedOrganizationId={orgMembers.selectedOrganizationId}
        onSelectedOrganizationIdChange={orgMembers.onSelectedOrganizationIdChange}
        selectedOrganization={orgMembers.selectedOrganization}
        members={orgMembers.members}
        membersLoadState={orgMembers.membersLoadState}
        orgOwnerAccess={orgOwnerAccess}
        canInviteMembers={canInviteMembers}
        memberBulkRole={orgMembers.memberBulkRole}
        onMemberBulkRoleChange={orgMembers.setMemberBulkRole}
        selectedMemberIds={orgMembers.selectedMemberIds}
        allMembersSelected={orgMembers.allMembersSelected}
        onToggleMemberSelected={orgMembers.toggleMemberSelected}
        onToggleSelectAllMembers={() => {
          if (orgMembers.allMembersSelected) {
            orgMembers.setSelectedMemberIds(new Set());
          } else {
            orgMembers.setSelectedMemberIds(new Set(orgMembers.members.map((m) => m.user_id)));
          }
        }}
        onApplyMemberBulk={() => void orgMembers.applyMemberBulk()}
        inviteEmail={orgMembers.inviteEmail}
        onInviteEmailChange={orgMembers.setInviteEmail}
        inviteRole={orgMembers.inviteRole}
        onInviteRoleChange={orgMembers.setInviteRole}
        onSendInvite={async () => {
          if (!orgMembers.selectedOrganizationId) {
            return;
          }
          const email = orgMembers.inviteEmail.trim();
          if (orgMembers.inviteRole === "member" && isProtectedOwnerEmail(email)) {
            orgMembers.setOrgMessage(`${PROTECTED_OWNER_EMAIL} cannot be invited as a member.`);
            return;
          }
          const response = await fetchWithTimeout(
            buildApiUrl(`/dashboard/organizations/${orgMembers.selectedOrganizationId}/members/invite`),
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ email, role: orgMembers.inviteRole }),
            },
            DASHBOARD_FETCH_TIMEOUT_MS,
          );
          if (response.ok) {
            orgMembers.setInviteEmail("");
            orgMembers.setOrgMessage("Invitation sent.");
            void orgMembers.loadMembers(orgMembers.selectedOrganizationId);
          } else {
            orgMembers.setOrgMessage("Failed to invite member.");
          }
        }}
        orgMessage={orgMembers.orgMessage}
      />

      <SettingsApiKeyLifecycleSection
        canMutateApiKeys={canMutateApiKeys}
        isApiSubpathDashboard={isApiSubpathDashboard()}
        activeKeyIds={activeKeyIds}
        keyBulkAction={keyBulkAction}
        selectedKeyIds={selectedKeyIds}
        allKeysSelected={allKeysSelected}
        apiKeys={d.apiKeys}
        lastIssuedApiKey={d.lastIssuedApiKey}
        apiKeyMessage={apiKeyMessage}
        onIssueKey={async () => {
          const ok = await d.issueApiKey();
          setApiKeyMessage(ok ? "New API key issued." : "Failed to issue API key.");
        }}
        onRefreshKeys={async () => {
          await d.refreshApiKeys();
          setApiKeyMessage("API keys refreshed.");
        }}
        onKeyBulkActionChange={setKeyBulkAction}
        onApplyBulk={() => void applyKeyBulk()}
        onToggleSelectAll={() => {
          if (allKeysSelected) {
            setSelectedKeyIds(new Set());
          } else {
            setSelectedKeyIds(new Set(activeKeyIds));
          }
        }}
        onToggleKeySelected={toggleKeySelected}
      />

      <SettingsAppearanceSessionSection
        viewerSession={viewerSession}
        themeMessage={themeMessage}
        setThemeMessage={setThemeMessage}
        themePreference={d.themePreference}
        themeSettingsSaving={d.themeSettingsSaving}
        saveThemePreference={d.saveThemePreference}
        signOutDashboard={d.signOutDashboard}
      />
    </div>
  );
}
