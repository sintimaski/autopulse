"use client";

import { useCallback, useMemo, useState } from "react";
import type { RetentionSettings } from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { buildApiUrl, isApiSubpathDashboard } from "../dashboardTypes";
import { DASHBOARD_FETCH_TIMEOUT_MS, fetchWithTimeout } from "../dashboardDataFetchUtils";
import {
  canInviteOrganizationMembers,
  canManageIngestApiKeys,
  canManageProjectAlertsAndRetention,
  isDashboardViewer,
} from "../dashboardRoleHelpers";
import { PROTECTED_OWNER_EMAIL, isProtectedOwnerEmail } from "./settingsContentUtils";
import { normalizeSchedulerJobs, normalizeSystemDiagnostics } from "../../../utils/systemDiagnostics";

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
import { useSettingsAlertDelivery } from "./useSettingsAlertDelivery";
import { useSettingsApiKeyBulk } from "./useSettingsApiKeyBulk";
import { useSettingsEventPlaneCutoverSave } from "./useSettingsEventPlaneCutoverSave";
import { settingsMetricStatusClass, useSettingsDiagnosticsPanels } from "./useSettingsDiagnosticsPanels";
import { useSettingsOrganizationsMembers } from "./useSettingsOrganizationsMembers";

export function SettingsContent() {
  const d = useDashboardData();
  const [themeMessage, setThemeMessage] = useState<string | null>(null);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);
  const [retentionDraft, setRetentionDraft] = useState<RetentionSettings | null>(null);
  const orgMembers = useSettingsOrganizationsMembers(d.sessionProjectId);
  const alertDelivery = useSettingsAlertDelivery(d.alertSettings, d.saveAlertSettings, d.setRefreshToken);
  const apiKeyBulk = useSettingsApiKeyBulk(
    d.apiKeys,
    d.rotateApiKey,
    d.revokeApiKey,
    d.refreshApiKeys,
    d.issueApiKey,
  );
  const [activeProjectBusy, setActiveProjectBusy] = useState(false);
  const [activeProjectMessage, setActiveProjectMessage] = useState<string | null>(null);
  const effectiveRetentionDraft = retentionDraft ?? d.retentionSettings;
  const canEditRetention = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canMutateApiKeys = canManageIngestApiKeys(d.sessionMembershipRole);
  const viewerSession = isDashboardViewer(d.sessionMembershipRole);

  /** Invites are tied to the signed-in dashboard session role, not the org picker alone. */
  const canInviteMembers = canInviteOrganizationMembers(d.sessionMembershipRole);

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

  const orgOwnerAccess = orgMembers.selectedOrganization?.role === "owner";
  const canEditAlertDelivery = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canViewInternalMetrics = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canViewSystemDiagnostics = canViewInternalMetrics;
  const canManageEventPlaneCutover = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const diagnostics = useSettingsDiagnosticsPanels({
    canViewInternalMetrics,
    canViewSystemDiagnostics,
    canManageEventPlaneCutover,
  });
  const eventPlaneCutoverSave = useSettingsEventPlaneCutoverSave(
    diagnostics.eventPlaneUseSnapshotRead,
    diagnostics.setEventPlaneUseSnapshotRead,
    diagnostics.setEventPlaneCutoverMessage,
  );
  const aggregateQueueDepth = diagnostics.internalMetricsSnapshot?.ingest_aggregate_queue?.depth ?? null;
  const aggregateQueueMax = diagnostics.internalMetricsSnapshot?.ingest_aggregate_queue?.max_size ?? null;
  const aggregateQueueEnabled = Boolean(diagnostics.internalMetricsSnapshot?.ingest_aggregate_queue?.enabled);
  const queueUsageRatio =
    typeof aggregateQueueDepth === "number" &&
    typeof aggregateQueueMax === "number" &&
    aggregateQueueMax > 0
      ? aggregateQueueDepth / aggregateQueueMax
      : null;
  const aggregateQueueHealthy = queueUsageRatio === null ? null : queueUsageRatio < 0.8;
  const aggregateWorkerHealthy = aggregateQueueEnabled ? aggregateQueueHealthy : null;
  const systemDiagnosticsSummary = useMemo(
    () => normalizeSystemDiagnostics(diagnostics.systemDiagnosticsSnapshot),
    [diagnostics.systemDiagnosticsSnapshot],
  );
  const schedulerJobs = useMemo(
    () => normalizeSchedulerJobs(diagnostics.systemDiagnosticsSnapshot),
    [diagnostics.systemDiagnosticsSnapshot],
  );

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
        internalMetricsLoadState={diagnostics.internalMetricsLoadState}
        internalMetricsEnabled={diagnostics.internalMetricsEnabled}
        internalMetricsReason={diagnostics.internalMetricsReason}
        internalMetricsSnapshot={diagnostics.internalMetricsSnapshot}
        metricStatusClass={settingsMetricStatusClass}
        aggregateQueueHealthy={aggregateQueueHealthy}
        aggregateWorkerHealthy={aggregateWorkerHealthy}
        queueUsageRatio={queueUsageRatio}
      />

      <SettingsSystemDiagnosticsSection
        canViewSystemDiagnostics={canViewSystemDiagnostics}
        systemDiagnosticsLoadState={diagnostics.systemDiagnosticsLoadState}
        systemDiagnosticsSnapshot={diagnostics.systemDiagnosticsSnapshot}
        systemDiagnosticsSummary={systemDiagnosticsSummary}
        schedulerJobs={schedulerJobs}
        metricStatusClass={settingsMetricStatusClass}
        systemDiagnosticsMessage={diagnostics.systemDiagnosticsMessage}
        setSystemDiagnosticsMessage={diagnostics.setSystemDiagnosticsMessage}
      />

      <SettingsEventPlaneCutoverSection
        canManageEventPlaneCutover={canManageEventPlaneCutover}
        eventPlaneCutoverLoadState={diagnostics.eventPlaneCutoverLoadState}
        eventPlaneCutoverMessage={diagnostics.eventPlaneCutoverMessage}
        eventPlaneUseSnapshotRead={diagnostics.eventPlaneUseSnapshotRead}
        setEventPlaneUseSnapshotRead={diagnostics.setEventPlaneUseSnapshotRead}
        eventPlaneCutoverSaving={eventPlaneCutoverSave.eventPlaneCutoverSaving}
        onSaveCutover={() => eventPlaneCutoverSave.saveEventPlaneCutover()}
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
        alertDeliveryDraft={d.alertSettings}
        dashboardLoading={d.loading}
        dashboardErrorMessage={d.errorMessage}
        canEditAlertDelivery={canEditAlertDelivery}
        viewerSession={viewerSession}
        alertCapabilities={d.alertCapabilities}
        alertSettingsSaving={d.alertSettingsSaving}
        updateAlertSettingsDraft={d.updateAlertSettingsDraft}
        onSave={() => void alertDelivery.saveDeliveryChannels()}
        onSendTestAlert={() => void alertDelivery.sendTestAlert()}
        channelMessage={alertDelivery.channelMessage}
        testAlertSending={alertDelivery.testAlertSending}
        testAlertResult={alertDelivery.testAlertResult}
        testAlertError={alertDelivery.testAlertError}
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
        activeKeyIds={apiKeyBulk.activeKeyIds}
        keyBulkAction={apiKeyBulk.keyBulkAction}
        selectedKeyIds={apiKeyBulk.selectedKeyIds}
        allKeysSelected={apiKeyBulk.allKeysSelected}
        apiKeys={d.apiKeys}
        lastIssuedApiKey={d.lastIssuedApiKey}
        apiKeyMessage={apiKeyBulk.apiKeyMessage}
        onIssueKey={() => void apiKeyBulk.issueKey()}
        onRefreshKeys={() => void apiKeyBulk.refreshKeys()}
        onKeyBulkActionChange={apiKeyBulk.setKeyBulkAction}
        onApplyBulk={() => void apiKeyBulk.applyKeyBulk()}
        onToggleSelectAll={apiKeyBulk.onToggleSelectAll}
        onToggleKeySelected={apiKeyBulk.toggleKeySelected}
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
