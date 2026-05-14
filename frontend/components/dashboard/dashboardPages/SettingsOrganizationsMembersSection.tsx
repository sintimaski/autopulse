"use client";

import { InlineDataSpinner } from "../../ui/InlineDataSpinner";
import type { DashboardMembershipItem, DashboardOrganizationSummary } from "../dashboardTypes";
import { PROTECTED_OWNER_EMAIL } from "./settingsContentUtils";

export type SettingsOrganizationsMembersSectionProps = {
  organizationsLoadState: "loading" | "ready" | "error";
  organizations: DashboardOrganizationSummary[];
  selectedOrganizationId: string | null;
  onSelectedOrganizationIdChange: (organizationId: string) => void;
  selectedOrganization: DashboardOrganizationSummary | undefined;
  members: DashboardMembershipItem[];
  membersLoadState: "idle" | "loading" | "ready";
  orgOwnerAccess: boolean;
  canInviteMembers: boolean;
  memberBulkRole: "" | "owner" | "member";
  onMemberBulkRoleChange: (role: "" | "owner" | "member") => void;
  selectedMemberIds: Set<string>;
  allMembersSelected: boolean;
  onToggleMemberSelected: (userId: string) => void;
  onToggleSelectAllMembers: () => void;
  onApplyMemberBulk: () => void | Promise<void>;
  inviteEmail: string;
  onInviteEmailChange: (email: string) => void;
  inviteRole: "owner" | "member";
  onInviteRoleChange: (role: "owner" | "member") => void;
  onSendInvite: () => void | Promise<void>;
  orgMessage: string | null;
};

export function SettingsOrganizationsMembersSection({
  organizationsLoadState,
  organizations,
  selectedOrganizationId,
  onSelectedOrganizationIdChange,
  selectedOrganization,
  members,
  membersLoadState,
  orgOwnerAccess,
  canInviteMembers,
  memberBulkRole,
  onMemberBulkRoleChange,
  selectedMemberIds,
  allMembersSelected,
  onToggleMemberSelected,
  onToggleSelectAllMembers,
  onApplyMemberBulk,
  inviteEmail,
  onInviteEmailChange,
  inviteRole,
  onInviteRoleChange,
  onSendInvite,
  orgMessage,
}: SettingsOrganizationsMembersSectionProps) {
  return (
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
                onChange={(event) => onSelectedOrganizationIdChange(event.target.value)}
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
                    ? "bg-orange-100 text-orange-900 dark:bg-orange-950/60 dark:text-orange-100"
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
                    onChange={(event) => onMemberBulkRoleChange(event.target.value as "" | "owner" | "member")}
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
                  onClick={() => void onApplyMemberBulk()}
                  className="ap-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Apply
                </button>
                <p className="max-w-md text-xs text-slate-500 dark:text-neutral-400">
                  Select rows with the checkboxes, pick an action, then Apply (you will confirm). {PROTECTED_OWNER_EMAIL}{" "}
                  is never demoted to member.
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
                            className="size-4 rounded border-slate-300 text-orange-600 focus:ring-orange-500 dark:border-neutral-600"
                            checked={allMembersSelected}
                            onChange={onToggleSelectAllMembers}
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
                                className="size-4 rounded border-slate-300 text-orange-600 focus:ring-orange-500 dark:border-neutral-600"
                                checked={selectedMemberIds.has(member.user_id)}
                                onChange={() => onToggleMemberSelected(member.user_id)}
                                aria-label={`Select ${member.email}`}
                              />
                            </td>
                          ) : null}
                          <td className="px-4 py-3 font-medium text-slate-800 dark:text-neutral-100">{member.email}</td>
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
                    onChange={(event) => onInviteEmailChange(event.target.value)}
                    className="ap-input mt-1"
                  />
                </label>
                <label className="block w-full max-w-[10rem] text-sm text-slate-700 dark:text-neutral-200">
                  Role
                  <select
                    value={inviteRole}
                    onChange={(event) => onInviteRoleChange(event.target.value as "owner" | "member")}
                    className="ap-select mt-1 w-full"
                    aria-label="Invite role"
                  >
                    <option value="member">Member</option>
                    {selectedOrganization?.role === "owner" ? <option value="owner">Owner</option> : null}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void onSendInvite()}
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
  );
}
