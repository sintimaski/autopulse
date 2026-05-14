import type { DashboardSessionResponse } from "./dashboardTypes";

/** Role for the active dashboard session (current project org). */
export type DashboardOrgRole = DashboardSessionResponse["membership_role"];

/** Full organization membership role enum — mirrors the backend `schemas/dashboard.py` enum. */
export const MEMBERSHIP_ROLES = ["owner", "admin", "member", "viewer"] as const;
export type MembershipRole = (typeof MEMBERSHIP_ROLES)[number];

/** Human label for a membership role (for selectors / badges). */
export function membershipRoleLabel(role: MembershipRole): string {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

/**
 * Roles an inviter may assign, matching backend `organization_routes.py`:
 * owners can assign any role; admins can only invite members/viewers.
 */
export function assignableMemberRoles(
  inviterRole: MembershipRole | null | undefined,
): MembershipRole[] {
  if (inviterRole === "owner") {
    return ["owner", "admin", "member", "viewer"];
  }
  if (inviterRole === "admin") {
    return ["member", "viewer"];
  }
  return [];
}

export function canManageProjectAlertsAndRetention(role: DashboardOrgRole): boolean {
  return role === "owner" || role === "admin";
}

export function canManageIngestApiKeys(role: DashboardOrgRole): boolean {
  return role === "owner" || role === "admin";
}

export function canInviteOrganizationMembers(
  role: "owner" | "admin" | "member" | "viewer" | null | undefined,
): boolean {
  return role === "owner" || role === "admin";
}

export function isDashboardViewer(role: DashboardOrgRole): boolean {
  return role === "viewer";
}
