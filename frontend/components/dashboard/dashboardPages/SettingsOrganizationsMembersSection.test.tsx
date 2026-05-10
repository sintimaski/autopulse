import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DashboardMembershipItem, DashboardOrganizationSummary } from "../dashboardTypes";

import { SettingsOrganizationsMembersSection } from "./SettingsOrganizationsMembersSection";

const org: DashboardOrganizationSummary = {
  organization_id: "org1",
  organization_name: "Acme",
  role: "owner",
  projects: [{ project_id: "p1", project_name: "API", organization_id: "org1" }],
};

const member: DashboardMembershipItem = {
  user_id: "u1",
  email: "a@example.com",
  role: "member",
  invited_email: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("SettingsOrganizationsMembersSection", () => {
  it("renders heading and org picker when organizations are ready", () => {
    const html = renderToStaticMarkup(
      <SettingsOrganizationsMembersSection
        organizationsLoadState="ready"
        organizations={[org]}
        selectedOrganizationId="org1"
        onSelectedOrganizationIdChange={() => {}}
        selectedOrganization={org}
        members={[member]}
        membersLoadState="ready"
        orgOwnerAccess
        canInviteMembers
        memberBulkRole=""
        onMemberBulkRoleChange={() => {}}
        selectedMemberIds={new Set()}
        allMembersSelected={false}
        onToggleMemberSelected={() => {}}
        onToggleSelectAllMembers={() => {}}
        onApplyMemberBulk={() => {}}
        inviteEmail=""
        onInviteEmailChange={() => {}}
        inviteRole="member"
        onInviteRoleChange={() => {}}
        onSendInvite={() => {}}
        orgMessage={null}
      />,
    );
    expect(html).toContain("Organizations &amp; members");
    expect(html).toContain("Active organization");
    expect(html).toContain("a@example.com");
    expect(html).toContain("Invite member");
  });

  it("shows loading state while organizations load", () => {
    const html = renderToStaticMarkup(
      <SettingsOrganizationsMembersSection
        organizationsLoadState="loading"
        organizations={[]}
        selectedOrganizationId={null}
        onSelectedOrganizationIdChange={() => {}}
        selectedOrganization={undefined}
        members={[]}
        membersLoadState="idle"
        orgOwnerAccess={false}
        canInviteMembers={false}
        memberBulkRole=""
        onMemberBulkRoleChange={() => {}}
        selectedMemberIds={new Set()}
        allMembersSelected={false}
        onToggleMemberSelected={() => {}}
        onToggleSelectAllMembers={() => {}}
        onApplyMemberBulk={() => {}}
        inviteEmail=""
        onInviteEmailChange={() => {}}
        inviteRole="member"
        onInviteRoleChange={() => {}}
        onSendInvite={() => {}}
        orgMessage={null}
      />,
    );
    expect(html).toContain("Loading organizations");
  });
});
