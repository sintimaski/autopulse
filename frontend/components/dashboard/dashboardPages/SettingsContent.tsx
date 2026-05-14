"use client";

import { useAsyncAction } from "../../../lib/useAsyncAction";
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
import { SettingsSdkNoiseSection } from "./SettingsSdkNoiseSection";
import { useSettingsAlertDelivery } from "./useSettingsAlertDelivery";
import { useSettingsApiKeyBulk } from "./useSettingsApiKeyBulk";
import { useSettingsEventPlaneCutoverSave } from "./useSettingsEventPlaneCutoverSave";
import { settingsMetricStatusClass, useSettingsDiagnosticsPanels } from "./useSettingsDiagnosticsPanels";
import { useSettingsOrganizationsMembers } from "./useSettingsOrganizationsMembers";
import { useSettingsRetentionPolicy } from "./useSettingsRetentionPolicy";
import { useSettingsActiveProject } from "./useSettingsActiveProject";
import { useSettingsAggregateQueueStats } from "./useSettingsAggregateQueueStats";
import { useSettingsAppearanceTrafficFeedback } from "./useSettingsAppearanceTrafficFeedback";
import { SettingsSectionNav, settingsSectionAnchorId } from "./SettingsSectionNav";

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

  // Wrap every mutating settings action with a pending flag + concurrent-call
  // guard so each button shows a loader and a rapid double-click can't fire the
  // request twice.
  const [issueApiKey, issuingApiKey] = useAsyncAction(apiKeyBulk.issueKey);
  const [refreshApiKeys, refreshingApiKeys] = useAsyncAction(apiKeyBulk.refreshKeys);
  const [applyApiKeyBulk, applyingApiKeyBulk] = useAsyncAction(apiKeyBulk.applyKeyBulk);
  const [saveRetention, savingRetention] = useAsyncAction(retentionPolicy.saveRetention);
  const [applyMemberBulk, applyingMemberBulk] = useAsyncAction(orgMembers.applyMemberBulk);
  const [sendInvite, sendingInvite] = useAsyncAction(orgMembers.sendInvite);
  const [signOutDashboard, signingOut] = useAsyncAction(d.signOutDashboard);

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <SettingsSectionNav />
      <div className="flex min-w-0 flex-col gap-5">
        <div id={settingsSectionAnchorId("retention")} className="scroll-mt-24">
          <SettingsRetentionPolicySection
            effectiveDraft={retentionPolicy.effectiveRetentionDraft}
            canEditRetention={canEditRetention}
            dashboardLoading={d.loading}
            dashboardErrorMessage={d.errorMessage}
            retentionMessage={retentionPolicy.retentionMessage}
            onDraftChange={(next) => retentionPolicy.setRetentionDraft(next)}
            onSave={saveRetention}
            saving={savingRetention}
          />
        </div>

        <div id={settingsSectionAnchorId("sdk")} className="scroll-mt-24">
          <SettingsSdkNoiseSection />
        </div>

        <div id={settingsSectionAnchorId("internal-metrics")} className="scroll-mt-24">
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
        </div>

        <div id={settingsSectionAnchorId("system-diagnostics")} className="scroll-mt-24">
          <SettingsSystemDiagnosticsSection
            canViewSystemDiagnostics={canViewSystemDiagnostics}
            systemDiagnosticsLoadState={diagnostics.systemDiagnosticsLoadState}
            systemDiagnosticsSnapshot={diagnostics.systemDiagnosticsSnapshot}
            systemDiagnosticsSummary={diagnostics.systemDiagnosticsSummary}
            schedulerJobs={diagnostics.schedulerJobs}
            metricStatusClass={settingsMetricStatusClass}
            systemDiagnosticsMessage={diagnostics.systemDiagnosticsMessage}
            setSystemDiagnosticsMessage={diagnostics.setSystemDiagnosticsMessage}
          />
        </div>

        <div id={settingsSectionAnchorId("event-plane")} className="scroll-mt-24">
          <SettingsEventPlaneCutoverSection
            canManageEventPlaneCutover={canManageEventPlaneCutover}
            eventPlaneCutoverLoadState={diagnostics.eventPlaneCutoverLoadState}
            eventPlaneCutoverMessage={diagnostics.eventPlaneCutoverMessage}
            eventPlaneUseSnapshotRead={diagnostics.eventPlaneUseSnapshotRead}
            setEventPlaneUseSnapshotRead={diagnostics.setEventPlaneUseSnapshotRead}
            eventPlaneCutoverSaving={eventPlaneCutoverSave.eventPlaneCutoverSaving}
            onSaveCutover={() => eventPlaneCutoverSave.saveEventPlaneCutover()}
          />
        </div>

        <div id={settingsSectionAnchorId("exclude-traffic")} className="scroll-mt-24">
          <SettingsExcludeLumonoxTrafficSection
            canEditRetention={canEditRetention}
            excludeLumonoxTraffic={d.excludeLumonoxTraffic}
            themeSettingsSaving={d.themeSettingsSaving}
            onToggleExclude={appearanceTraffic.onToggleExcludeLumonoxTraffic}
          />
        </div>

        <div id={settingsSectionAnchorId("alert-delivery")} className="scroll-mt-24">
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
        </div>

        <div id={settingsSectionAnchorId("active-project")} className="scroll-mt-24">
          <SettingsActiveProjectSection
            organizationsLoadState={orgMembers.organizationsLoadState}
            accessibleProjects={orgMembers.accessibleProjects}
            currentProjectLabel={orgMembers.currentProjectLabel}
            sessionProjectId={d.sessionProjectId}
            activeProjectBusy={activeProject.activeProjectBusy}
            activeProjectMessage={activeProject.activeProjectMessage}
            onActiveProjectChange={activeProject.onActiveProjectChange}
          />
        </div>

        <div id={settingsSectionAnchorId("members")} className="scroll-mt-24">
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
            onApplyMemberBulk={applyMemberBulk}
            applyingMemberBulk={applyingMemberBulk}
            inviteEmail={orgMembers.inviteEmail}
            onInviteEmailChange={orgMembers.setInviteEmail}
            inviteRole={orgMembers.inviteRole}
            onInviteRoleChange={orgMembers.setInviteRole}
            onSendInvite={sendInvite}
            sendingInvite={sendingInvite}
            orgMessage={orgMembers.orgMessage}
          />
        </div>

        <div id={settingsSectionAnchorId("api-keys")} className="scroll-mt-24">
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
            onIssueKey={issueApiKey}
            onRefreshKeys={refreshApiKeys}
            onKeyBulkActionChange={apiKeyBulk.setKeyBulkAction}
            onApplyBulk={applyApiKeyBulk}
            onToggleSelectAll={apiKeyBulk.onToggleSelectAll}
            onToggleKeySelected={apiKeyBulk.toggleKeySelected}
            issuingKey={issuingApiKey}
            refreshingKeys={refreshingApiKeys}
            applyingBulk={applyingApiKeyBulk}
          />
        </div>

        <div id={settingsSectionAnchorId("appearance")} className="scroll-mt-24">
          <SettingsAppearanceSessionSection
            viewerSession={viewerSession}
            themeMessage={appearanceTraffic.themeMessage}
            setThemeMessage={appearanceTraffic.setThemeMessage}
            themePreference={d.themePreference}
            themeSettingsSaving={d.themeSettingsSaving}
            saveThemePreference={d.saveThemePreference}
            signOutDashboard={signOutDashboard}
            signingOut={signingOut}
          />
        </div>
      </div>
    </div>
  );
}
