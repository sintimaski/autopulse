"use client";

import { useDashboardData } from "../DashboardDataContext";
import { isApiSubpathDashboard } from "../dashboardTypes";
import {
  canInviteOrganizationMembers,
  canManageIngestApiKeys,
  canManageProjectAlertsAndRetention,
  isDashboardViewer,
} from "../dashboardRoleHelpers";
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
import { useSettingsRetentionPolicy } from "./useSettingsRetentionPolicy";
import { useSettingsActiveProject } from "./useSettingsActiveProject";
import { useSettingsAggregateQueueStats } from "./useSettingsAggregateQueueStats";
import { useSettingsAppearanceTrafficFeedback } from "./useSettingsAppearanceTrafficFeedback";
import { useSettingsSystemDiagnosticsDerived } from "./useSettingsSystemDiagnosticsDerived";

export function SettingsContent() {
  const d = useDashboardData();
  const appearanceTraffic = useSettingsAppearanceTrafficFeedback(d.saveExcludeLumonoxTraffic);
  const orgMembers = useSettingsOrganizationsMembers(d.sessionProjectId);
  const retentionPolicy = useSettingsRetentionPolicy(d.retentionSettings, d.saveRetentionSettings);
  const alertDelivery = useSettingsAlertDelivery(d.alertSettings, d.saveAlertSettings, d.setRefreshToken);
  const apiKeyBulk = useSettingsApiKeyBulk(
    d.apiKeys,
    d.rotateApiKey,
    d.revokeApiKey,
    d.refreshApiKeys,
    d.issueApiKey,
  );
  const activeProject = useSettingsActiveProject(d.sessionProjectId, d.setActiveDashboardProject);
  const canEditRetention = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const canMutateApiKeys = canManageIngestApiKeys(d.sessionMembershipRole);
  const viewerSession = isDashboardViewer(d.sessionMembershipRole);

  /** Invites are tied to the signed-in dashboard session role, not the org picker alone. */
  const canInviteMembers = canInviteOrganizationMembers(d.sessionMembershipRole);

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
  const aggregateQueue = useSettingsAggregateQueueStats(diagnostics.internalMetricsSnapshot);
  const systemDiagnosticsDerived = useSettingsSystemDiagnosticsDerived(diagnostics.systemDiagnosticsSnapshot);

  return (
    <div className="space-y-6">
      <SettingsRetentionPolicySection
        effectiveDraft={retentionPolicy.effectiveRetentionDraft}
        canEditRetention={canEditRetention}
        dashboardLoading={d.loading}
        dashboardErrorMessage={d.errorMessage}
        retentionMessage={retentionPolicy.retentionMessage}
        onDraftChange={(next) => retentionPolicy.setRetentionDraft(next)}
        onSave={() => retentionPolicy.saveRetention()}
      />

      <SettingsInternalMetricsSection
        canViewInternalMetrics={canViewInternalMetrics}
        internalMetricsLoadState={diagnostics.internalMetricsLoadState}
        internalMetricsEnabled={diagnostics.internalMetricsEnabled}
        internalMetricsReason={diagnostics.internalMetricsReason}
        internalMetricsSnapshot={diagnostics.internalMetricsSnapshot}
        metricStatusClass={settingsMetricStatusClass}
        aggregateQueueHealthy={aggregateQueue.aggregateQueueHealthy}
        aggregateWorkerHealthy={aggregateQueue.aggregateWorkerHealthy}
        queueUsageRatio={aggregateQueue.queueUsageRatio}
      />

      <SettingsSystemDiagnosticsSection
        canViewSystemDiagnostics={canViewSystemDiagnostics}
        systemDiagnosticsLoadState={diagnostics.systemDiagnosticsLoadState}
        systemDiagnosticsSnapshot={diagnostics.systemDiagnosticsSnapshot}
        systemDiagnosticsSummary={systemDiagnosticsDerived.systemDiagnosticsSummary}
        schedulerJobs={systemDiagnosticsDerived.schedulerJobs}
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
        onToggleExclude={appearanceTraffic.onToggleExcludeLumonoxTraffic}
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
        activeProjectBusy={activeProject.activeProjectBusy}
        activeProjectMessage={activeProject.activeProjectMessage}
        onActiveProjectChange={activeProject.onActiveProjectChange}
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
        onToggleSelectAllMembers={orgMembers.toggleSelectAllMembers}
        onApplyMemberBulk={() => void orgMembers.applyMemberBulk()}
        inviteEmail={orgMembers.inviteEmail}
        onInviteEmailChange={orgMembers.setInviteEmail}
        inviteRole={orgMembers.inviteRole}
        onInviteRoleChange={orgMembers.setInviteRole}
        onSendInvite={() => void orgMembers.sendInvite()}
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
        themeMessage={appearanceTraffic.themeMessage}
        setThemeMessage={appearanceTraffic.setThemeMessage}
        themePreference={d.themePreference}
        themeSettingsSaving={d.themeSettingsSaving}
        saveThemePreference={d.saveThemePreference}
        signOutDashboard={d.signOutDashboard}
      />
    </div>
  );
}
