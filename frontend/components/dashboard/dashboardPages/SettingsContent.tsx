"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type {
  DashboardAlertTestResponse,
  DashboardMembershipItem,
  DashboardOrganizationSummary,
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
  parseDashboardMembershipItemsPayload,
  parseDashboardOrganizationListResponse,
  parseDashboardSystemDiagnosticsResponse,
  parseEventPlaneCutoverSettings,
} from "../../../utils/dashboardResponseGuards";

import type { InternalMetricsSnapshot } from "./settingsContentTypes";
import { SettingsAppearanceSessionSection } from "./SettingsAppearanceSessionSection";
import { SettingsExcludeLumonoxTrafficSection } from "./SettingsExcludeLumonoxTrafficSection";
import { SettingsEventPlaneCutoverSection } from "./SettingsEventPlaneCutoverSection";
import { SettingsInternalMetricsSection } from "./SettingsInternalMetricsSection";
import { SettingsSystemDiagnosticsSection } from "./SettingsSystemDiagnosticsSection";
import { SettingsRetentionPolicySection } from "./SettingsRetentionPolicySection";

type SystemDiagnosticsSnapshot = DashboardSystemDiagnosticsResponse;

export function SettingsContent() {
  const d = useDashboardData();
  const [themeMessage, setThemeMessage] = useState<string | null>(null);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);
  const [retentionDraft, setRetentionDraft] = useState<RetentionSettings | null>(null);
  const [organizations, setOrganizations] = useState<DashboardOrganizationSummary[]>([]);
  const [organizationsLoadState, setOrganizationsLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [members, setMembers] = useState<DashboardMembershipItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"owner" | "member">("member");
  const [orgMessage, setOrgMessage] = useState<string | null>(null);
  const [membersLoadState, setMembersLoadState] = useState<"idle" | "loading" | "ready">("idle");
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [memberBulkRole, setMemberBulkRole] = useState<"" | "owner" | "member">("");
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

  const selectedOrganization = organizations.find((organization) => organization.organization_id === selectedOrganizationId);
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

  const loadMembers = async (organizationId: string) => {
    try {
      const response = await fetchWithTimeout(
        buildApiUrl(`/dashboard/organizations/${organizationId}/members`),
        { credentials: "include" },
        DASHBOARD_FETCH_TIMEOUT_MS,
      );
      if (!response.ok) {
        setMembers([]);
        return;
      }
      const raw: unknown = await response.json();
      const members = parseDashboardMembershipItemsPayload(raw);
      setMembers(members ?? []);
    } catch {
      setMembers([]);
    }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setOrganizationsLoadState("loading");
      try {
        const response = await fetchWithTimeout(buildApiUrl("/dashboard/organizations"), {
          credentials: "include",
        }, DASHBOARD_FETCH_TIMEOUT_MS);
        if (cancelled) {
          return;
        }
        if (!response.ok) {
          setOrganizationsLoadState("error");
          return;
        }
        const raw: unknown = await response.json();
        const payload = parseDashboardOrganizationListResponse(raw);
        if (cancelled) {
          return;
        }
        if (!payload) {
          setOrganizationsLoadState("error");
          return;
        }
        setOrganizations(payload.organizations);
        if (payload.organizations[0]) {
          setSelectedOrganizationId((prev) => prev ?? payload.organizations[0].organization_id);
        }
        setOrganizationsLoadState("ready");
      } catch {
        if (!cancelled) {
          setOrganizationsLoadState("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (selectedOrganizationId) {
      queueMicrotask(() => {
        setMembersLoadState("loading");
      });
      void (async () => {
        try {
          const response = await fetchWithTimeout(
            buildApiUrl(`/dashboard/organizations/${selectedOrganizationId}/members`),
            { credentials: "include" },
            DASHBOARD_FETCH_TIMEOUT_MS,
          );
          if (!response.ok || cancelled) {
            setMembers([]);
            if (!cancelled) {
              setMembersLoadState("ready");
            }
            return;
          }
          const raw: unknown = await response.json();
          const members = parseDashboardMembershipItemsPayload(raw);
          if (!cancelled) {
            setMembers(members ?? []);
            setMembersLoadState("ready");
          }
        } catch {
          if (!cancelled) {
            setMembers([]);
            setMembersLoadState("ready");
          }
        }
      })();
    } else {
      queueMicrotask(() => {
        setMembersLoadState("idle");
      });
    }
    return () => {
      cancelled = true;
    };
  }, [selectedOrganizationId]);

  const accessibleProjects = useMemo(() => {
    const rows: { id: string; label: string }[] = [];
    for (const org of organizations) {
      for (const p of org.projects) {
        rows.push({
          id: p.project_id,
          label: `${org.organization_name} / ${p.project_name}`,
        });
      }
    }
    rows.sort((a, b) => a.label.localeCompare(b.label));
    return rows;
  }, [organizations]);

  const currentProjectLabel = useMemo(() => {
    if (!d.sessionProjectId) {
      return null;
    }
    return accessibleProjects.find((r) => r.id === d.sessionProjectId)?.label ?? d.sessionProjectId;
  }, [accessibleProjects, d.sessionProjectId]);

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

  const toggleMemberSelected = (userId: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const allMemberIdsSelectable = members.map((m) => m.user_id);
  const allMembersSelected =
    allMemberIdsSelectable.length > 0 && allMemberIdsSelectable.every((id) => selectedMemberIds.has(id));

  const applyMemberBulk = async () => {
    if (!selectedOrganizationId || !memberBulkRole || selectedMemberIds.size === 0) {
      return;
    }
    const label = memberBulkRole === "owner" ? "Promote to owner" : "Demote to member";
    if (!window.confirm(`${label} for ${selectedMemberIds.size} selected member(s)?`)) {
      return;
    }
    let ok = 0;
    let skipped = 0;
    let failed = 0;
    for (const userId of selectedMemberIds) {
      const member = members.find((m) => m.user_id === userId);
      if (!member) {
        continue;
      }
      if (memberBulkRole === "member" && isProtectedOwnerEmail(member.email)) {
        skipped += 1;
        continue;
      }
      if (member.role === memberBulkRole) {
        continue;
      }
      try {
        const response = await fetchWithTimeout(
          buildApiUrl(`/dashboard/organizations/${selectedOrganizationId}/members/${userId}/role`),
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ role: memberBulkRole }),
          },
          DASHBOARD_FETCH_TIMEOUT_MS,
        );
        if (response.ok) {
          ok += 1;
        } else {
          failed += 1;
        }
      } catch {
        failed += 1;
      }
    }
    await loadMembers(selectedOrganizationId);
    setSelectedMemberIds(new Set());
    setMemberBulkRole("");
    const parts = [];
    if (ok) {
      parts.push(`Updated ${ok}.`);
    }
    if (skipped) {
      parts.push(`Skipped ${skipped} (protected address).`);
    }
    if (failed) {
      parts.push(`${failed} failed.`);
    }
    setOrgMessage(parts.join(" ") || "No changes applied.");
  };

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

  const orgOwnerAccess = selectedOrganization?.role === "owner";
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

      <section
        id="alert-delivery"
        className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      >
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">
          Alert delivery
        </h2>
        {alertDeliveryDraft ? (
          <>
            <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
              Turn project alerts on, set where notifications go (email and webhooks), then save. Heuristic thresholds
              (error spikes, cooldown) stay on the{" "}
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
                  d.updateAlertSettingsDraft({
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
                      d.updateAlertSettingsDraft({
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
                      d.updateAlertSettingsDraft({
                        ...alertDeliveryDraft,
                        destination_email: event.target.value.trim() || null,
                      })
                    }
                    className="ap-input mt-1 text-sm"
                    placeholder="ops@example.com"
                  />
                </label>
                <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                  SMTP, Resend, SendGrid, etc. are configured on the Lumonox server (environment variables), not in
                  this form—you only choose who receives mail. See readiness below.
                </span>
              </div>
              <label className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
                <span className="flex items-center gap-2 font-medium">
                  <input
                    type="checkbox"
                    disabled={!canEditAlertDelivery}
                    checked={alertDeliveryDraft.slack_enabled}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
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
                    d.updateAlertSettingsDraft({
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
                      d.updateAlertSettingsDraft({
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
                    d.updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      discord_webhook_url: event.target.value.trim() || null,
                    })
                  }
                  className="ap-input mt-2"
                  placeholder="https://discord.com/api/webhooks/..."
                />
                <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                  Paste the full URL from Server Settings → Integrations → Webhooks (it includes webhook id and token in
                  the path). A bare <code className="rounded bg-slate-200/80 px-0.5 font-mono text-[11px] dark:bg-neutral-950/80">/api/webhooks</code> prefix will not work.
                </span>
              </label>
              <label className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-sm text-slate-700 dark:border-neutral-700 dark:bg-neutral-800/60 dark:text-neutral-200">
                <span className="flex items-center gap-2 font-medium">
                  <input
                    type="checkbox"
                    disabled={!canEditAlertDelivery}
                    checked={alertDeliveryDraft.webhook_enabled}
                    onChange={(event) =>
                      d.updateAlertSettingsDraft({
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
                    d.updateAlertSettingsDraft({
                      ...alertDeliveryDraft,
                      webhook_url: event.target.value.trim() || null,
                    })
                  }
                  className="ap-input mt-2"
                  placeholder="https://example.com/alerts/webhook"
                />
                <span className="mt-2 block text-xs text-slate-500 dark:text-neutral-400">
                  Lumonox POSTs a JSON payload to this URL. There is no separate API-key field; if your endpoint
                  needs auth, use a signed URL or terminate TLS at a gateway you control (custom headers are not
                  configured here yet).
                </span>
              </label>
            </div>

            <div className="mt-6 rounded-xl border border-slate-200/90 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-neutral-200">Server readiness</h3>
              <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
                Status reflects backend environment wiring. &quot;Active&quot; means the server can dispatch through
                that channel when your project settings allow it.
              </p>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {d.alertCapabilities.map((capability) => (
                  <li
                    key={capability.channel}
                    className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900/60"
                  >
                    <div>
                      <p className="font-medium capitalize text-slate-800 dark:text-neutral-100">
                        {capability.channel}
                      </p>
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
                onClick={() => void sendTestAlert()}
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
                disabled={!canEditAlertDelivery || d.alertSettingsSaving}
                onClick={() => void saveDeliveryChannels()}
                className="ap-btn-primary"
              >
                {d.alertSettingsSaving ? "Saving..." : "Save alert delivery"}
              </button>
              {channelMessage ? (
                <p className="text-sm text-slate-600 dark:text-neutral-300">{channelMessage}</p>
              ) : null}
            </div>
          </>
        ) : d.loading && !d.errorMessage ? (
          <div className="mt-4">
            <InlineDataSpinner label="Loading alert delivery…" />
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
            {d.errorMessage ?? "Alert delivery settings are not available."}
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex flex-col gap-1 border-b border-slate-200/80 pb-4 dark:border-neutral-800">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
            Dashboard scope
          </p>
          <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Active project</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-neutral-400">
            Charts and API keys follow the project bound to your signed-in session (not the organization picker below).
            If you see empty traffic while your app is sending events, your ingest key may belong to another project in
            the same organization—select the matching project here.
          </p>
        </div>
        <div className="mt-6">
          {organizationsLoadState === "loading" ? (
            <InlineDataSpinner label="Loading projects…" />
          ) : organizationsLoadState === "error" ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">Could not load projects for this account.</p>
          ) : accessibleProjects.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-neutral-400">No projects found.</p>
          ) : accessibleProjects.length === 1 ? (
            <p className="text-sm text-slate-700 dark:text-neutral-200">
              <span className="font-medium text-slate-900 dark:text-neutral-100">Current project:</span>{" "}
              {currentProjectLabel ?? "—"}
            </p>
          ) : (
            <label className="block max-w-xl text-sm font-medium text-slate-700 dark:text-neutral-200">
              Project for dashboard queries
              <select
                className="ap-select mt-1.5 w-full"
                value={d.sessionProjectId ?? ""}
                disabled={activeProjectBusy}
                onChange={(event) => void onActiveProjectChange(event.target.value)}
              >
                {accessibleProjects.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {activeProjectMessage ? (
            <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">{activeProjectMessage}</p>
          ) : null}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex flex-col gap-1 border-b border-slate-200/80 pb-4 dark:border-neutral-800 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
              Access control
            </p>
            <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Organizations &amp; members</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-neutral-400">
              Owners: select members, choose an action, confirm, then apply. Admins can invite members and manage most
              settings; only owners can promote or demote roles here.{" "}
              <span className="font-medium text-slate-800 dark:text-neutral-200">{PROTECTED_OWNER_EMAIL}</span> cannot be
              assigned the member role.
            </p>
          </div>
        </div>
        {organizationsLoadState === "loading" ? (
          <div className="mt-6">
            <InlineDataSpinner label="Loading organizations…" />
          </div>
        ) : organizationsLoadState === "error" ? (
          <p className="mt-6 text-sm text-rose-700 dark:text-rose-300">
            Could not load organizations. Check your connection and dashboard API availability, then reload this page.
          </p>
        ) : organizations.length === 0 ? (
          <p className="mt-6 text-sm text-slate-600 dark:text-neutral-300">
            No organizations are linked to this account yet.
          </p>
        ) : (
          <div className="mt-6 space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <label className="block w-full max-w-md text-sm font-medium text-slate-700 dark:text-neutral-200">
                Active organization
                <select
                  value={selectedOrganizationId ?? ""}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedMemberIds(new Set());
                    setMemberBulkRole("");
                    setSelectedOrganizationId(value);
                    const nextOrg = organizations.find((o) => o.organization_id === value);
                    if (nextOrg?.role === "admin") {
                      setInviteRole((r) => (r === "owner" ? "member" : r));
                    }
                  }}
                  className="ap-select mt-1.5 w-full"
                >
                  {organizations.map((organization) => (
                    <option key={organization.organization_id} value={organization.organization_id}>
                      {organization.organization_name} — {organization.role}
                    </option>
                  ))}
                </select>
              </label>
              {selectedOrganization ? (
                <span
                  className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${
                    selectedOrganization.role === "owner"
                      ? "bg-sky-100 text-sky-900 dark:bg-sky-950/60 dark:text-sky-100"
                      : "bg-slate-100 text-slate-700 dark:bg-neutral-800 dark:text-neutral-200"
                  }`}
                >
                  Your role: {selectedOrganization.role}
                </span>
              ) : null}
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-neutral-700">
              <div className="border-b border-slate-200 bg-slate-50 px-4 py-2.5 dark:border-neutral-700 dark:bg-neutral-800/80">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-neutral-300">
                  Members ({members.length})
                </h3>
              </div>
              {orgOwnerAccess ? (
                <div className="flex flex-wrap items-end gap-3 border-b border-slate-200 bg-slate-50/90 px-4 py-3 dark:border-neutral-700 dark:bg-neutral-800/60">
                  <label className="block min-w-[12rem] text-sm font-medium text-slate-700 dark:text-neutral-200">
                    Action
                    <select
                      value={memberBulkRole}
                      onChange={(event) => setMemberBulkRole(event.target.value as "" | "owner" | "member")}
                      className="ap-select mt-1 w-full"
                      aria-label="Bulk member action"
                    >
                      <option value="">Choose action…</option>
                      <option value="owner">Promote to owner</option>
                      <option value="member">Demote to member</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    disabled={!memberBulkRole || selectedMemberIds.size === 0}
                    onClick={() => void applyMemberBulk()}
                    className="ap-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Apply
                  </button>
                  <p className="max-w-md text-xs text-slate-500 dark:text-neutral-400">
                    Select rows with the checkboxes, pick an action, then Apply (you will confirm).{" "}
                    {PROTECTED_OWNER_EMAIL} is never demoted to member.
                  </p>
                </div>
              ) : null}
              {membersLoadState === "loading" ? (
                <div className="p-6">
                  <InlineDataSpinner label="Loading members…" />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="border-b border-slate-200 bg-white text-xs font-semibold uppercase tracking-wide text-slate-500 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
                      <tr>
                        {orgOwnerAccess ? (
                          <th className="w-12 px-3 py-3">
                            <input
                              type="checkbox"
                              className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                              checked={allMembersSelected}
                              onChange={() => {
                                if (allMembersSelected) {
                                  setSelectedMemberIds(new Set());
                                } else {
                                  setSelectedMemberIds(new Set(members.map((m) => m.user_id)));
                                }
                              }}
                              aria-label="Select all members"
                            />
                          </th>
                        ) : null}
                        <th className="px-4 py-3">Member</th>
                        <th className="px-4 py-3">Role</th>
                        <th className="px-4 py-3">Joined</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white dark:divide-neutral-800 dark:bg-neutral-950/40">
                      {members.length === 0 ? (
                        <tr>
                          <td
                            colSpan={orgOwnerAccess ? 4 : 3}
                            className="px-4 py-8 text-center text-sm text-slate-500 dark:text-neutral-400"
                          >
                            No members returned for this organization.
                          </td>
                        </tr>
                      ) : (
                        members.map((member) => (
                          <tr key={member.user_id} className="hover:bg-slate-50/80 dark:hover:bg-neutral-900/60">
                            {orgOwnerAccess ? (
                              <td className="px-3 py-3 align-middle">
                                <input
                                  type="checkbox"
                                  className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                                  checked={selectedMemberIds.has(member.user_id)}
                                  onChange={() => toggleMemberSelected(member.user_id)}
                                  aria-label={`Select ${member.email}`}
                                />
                              </td>
                            ) : null}
                            <td className="px-4 py-3 font-medium text-slate-800 dark:text-neutral-100">
                              {member.email}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${
                                  member.role === "owner"
                                    ? "bg-violet-100 text-violet-900 dark:bg-violet-950/50 dark:text-violet-200"
                                    : "bg-slate-100 text-slate-700 dark:bg-neutral-800 dark:text-neutral-200"
                                }`}
                              >
                                {member.role}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-slate-600 dark:text-neutral-300">
                              {new Date(member.created_at).toLocaleString()}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {canInviteMembers ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-900/50">
                <h3 className="text-sm font-semibold text-slate-800 dark:text-neutral-100">Invite member</h3>
                <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">
                  Invitation email must be allowed by your auth policy.
                </p>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
                  <label className="block min-w-[220px] flex-1 text-sm text-slate-700 dark:text-neutral-200">
                    Email
                    <input
                      type="email"
                      id="org-invite-email"
                      autoComplete="email"
                      value={inviteEmail}
                      placeholder="colleague@company.com"
                      onChange={(event) => setInviteEmail(event.target.value)}
                      className="ap-input mt-1"
                    />
                  </label>
                  <label className="block w-full max-w-[10rem] text-sm text-slate-700 dark:text-neutral-200">
                    Role
                    <select
                      value={inviteRole}
                      onChange={(event) => setInviteRole(event.target.value as "owner" | "member")}
                      className="ap-select mt-1 w-full"
                      aria-label="Invite role"
                    >
                      <option value="member">Member</option>
                      {selectedOrganization?.role === "owner" ? (
                        <option value="owner">Owner</option>
                      ) : null}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={async () => {
                      if (!selectedOrganizationId) {
                        return;
                      }
                      const email = inviteEmail.trim();
                      if (inviteRole === "member" && isProtectedOwnerEmail(email)) {
                        setOrgMessage(`${PROTECTED_OWNER_EMAIL} cannot be invited as a member.`);
                        return;
                      }
                      const response = await fetchWithTimeout(
                        buildApiUrl(`/dashboard/organizations/${selectedOrganizationId}/members/invite`),
                        {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          credentials: "include",
                          body: JSON.stringify({ email, role: inviteRole }),
                        },
                        DASHBOARD_FETCH_TIMEOUT_MS,
                      );
                      if (response.ok) {
                        setInviteEmail("");
                        setOrgMessage("Invitation sent.");
                        void loadMembers(selectedOrganizationId);
                      } else {
                        setOrgMessage("Failed to invite member.");
                      }
                    }}
                    className="ap-btn-primary w-full sm:w-auto"
                  >
                    Send invite
                  </button>
                </div>
              </div>
            ) : null}
            {orgMessage ? (
              <p className="text-sm text-slate-600 dark:text-neutral-300" role="status">
                {orgMessage}
              </p>
            ) : null}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">API key lifecycle</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          {canMutateApiKeys
            ? "Issue, rotate, and revoke ingest keys (owners and admins). All changes are audited."
            : "Active keys for this project (read-only). Ask an owner or admin to issue or rotate keys."}
        </p>
        {isApiSubpathDashboard() ? (
          <p className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
            First boot writes <code className="rounded bg-slate-100 px-1 font-mono dark:bg-neutral-950">.env.lumonox</code> — source before{" "}
            <code className="rounded bg-slate-100 px-1 font-mono dark:bg-neutral-950">npm run build</code>. New keys here: paste both API_KEY lines there, rebuild, restart.
          </p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!canMutateApiKeys}
            onClick={async () => {
              const ok = await d.issueApiKey();
              setApiKeyMessage(ok ? "New API key issued." : "Failed to issue API key.");
            }}
            className="ap-btn-primary"
          >
            Issue new key
          </button>
          <button
            type="button"
            onClick={async () => {
              await d.refreshApiKeys();
              setApiKeyMessage("API keys refreshed.");
            }}
            className="ap-btn"
          >
            Refresh
          </button>
        </div>
        {d.lastIssuedApiKey ? (
          <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-200">
            <p className="font-semibold">Copy this key now (shown once):</p>
            <code className="mt-1 block break-all">{d.lastIssuedApiKey}</code>
          </div>
        ) : null}
        {activeKeyIds.length > 0 && canMutateApiKeys ? (
          <div className="mt-3 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50/90 px-4 py-3 dark:border-neutral-700 dark:bg-neutral-800/60">
            <label className="block min-w-[12rem] text-sm font-medium text-slate-700 dark:text-neutral-200">
              Action
              <select
                value={keyBulkAction}
                onChange={(event) => setKeyBulkAction(event.target.value as "" | "rotate" | "revoke")}
                className="ap-select mt-1 w-full"
                aria-label="Bulk API key action"
              >
                <option value="">Choose action…</option>
                <option value="rotate">Rotate selected</option>
                <option value="revoke">Revoke selected</option>
              </select>
            </label>
            <button
              type="button"
              disabled={!keyBulkAction || selectedKeyIds.size === 0}
              onClick={() => void applyKeyBulk()}
              className={
                keyBulkAction === "revoke"
                  ? "ap-btn-danger disabled:cursor-not-allowed disabled:opacity-50"
                  : "ap-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              }
            >
              Apply
            </button>
            <p className="max-w-md text-xs text-slate-500 dark:text-neutral-400">
              Select active keys, choose an action, Apply, then confirm. With multiple active keys, the oldest active key
              cannot be bulk-revoked.
            </p>
          </div>
        ) : null}
        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
              <tr>
                <th className="w-10 px-2 py-2">
                  {activeKeyIds.length > 0 && canMutateApiKeys ? (
                    <input
                      type="checkbox"
                      className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                      checked={allKeysSelected}
                      onChange={() => {
                        if (allKeysSelected) {
                          setSelectedKeyIds(new Set());
                        } else {
                          setSelectedKeyIds(new Set(activeKeyIds));
                        }
                      }}
                      aria-label="Select all active API keys"
                    />
                  ) : null}
                </th>
                <th className="px-3 py-2 font-semibold">Key ID</th>
                <th className="px-3 py-2 font-semibold">Created</th>
                <th className="px-3 py-2 font-semibold">Revoked</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
              {d.apiKeys.map((item) => (
                <tr key={item.key_id}>
                  <td className="px-2 py-2 align-middle">
                    {!item.revoked_at && canMutateApiKeys ? (
                      <input
                        type="checkbox"
                        className="size-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 dark:border-neutral-600"
                        checked={selectedKeyIds.has(item.key_id)}
                        onChange={() => toggleKeySelected(item.key_id)}
                        aria-label={`Select key ${item.key_id}`}
                      />
                    ) : (
                      <span className="inline-block w-4" aria-hidden />
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-200">{item.key_id}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                    {item.revoked_at ? new Date(item.revoked_at).toLocaleString() : "active"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {apiKeyMessage ? <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{apiKeyMessage}</p> : null}
      </section>

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
