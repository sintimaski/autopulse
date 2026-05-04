import type { DashboardSessionResponse } from "./dashboardTypes";

/** Role for the active dashboard session (current project org). */
export type DashboardOrgRole = DashboardSessionResponse["membership_role"];

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
