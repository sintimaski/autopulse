"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  parseDashboardMembershipItemsPayload,
  parseDashboardOrganizationListResponse,
} from "../../../utils/dashboardResponseGuards";
import {
  dashboardSessionFetch,
  dashboardSessionJsonPost,
  dashboardSessionJsonPut,
} from "../dashboardSessionFetch";
import type { DashboardMembershipItem, DashboardOrganizationSummary } from "../dashboardTypes";
import type { MembershipRole } from "../dashboardRoleHelpers";
import { PROTECTED_OWNER_EMAIL, isProtectedOwnerEmail } from "./settingsContentUtils";

/** How long the inline "Confirm" affordance stays armed before reverting. */
const CONFIRM_WINDOW_MS = 4000;

export function useSettingsOrganizationsMembers(sessionProjectId: string | null) {
  const [organizations, setOrganizations] = useState<DashboardOrganizationSummary[]>([]);
  const [organizationsLoadState, setOrganizationsLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [members, setMembers] = useState<DashboardMembershipItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<MembershipRole>("member");
  const [orgMessage, setOrgMessage] = useState<string | null>(null);
  const [membersLoadState, setMembersLoadState] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [memberBulkRole, setMemberBulkRole] = useState<"" | MembershipRole>("");
  // Two-click inline confirm: first Apply arms this, second Apply runs it.
  const [memberBulkConfirmCount, setMemberBulkConfirmCount] = useState<number | null>(null);
  const memberConfirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelMemberBulkConfirm = useCallback(() => {
    if (memberConfirmTimerRef.current) {
      clearTimeout(memberConfirmTimerRef.current);
      memberConfirmTimerRef.current = null;
    }
    setMemberBulkConfirmCount(null);
  }, []);

  useEffect(() => {
    return () => {
      if (memberConfirmTimerRef.current) {
        clearTimeout(memberConfirmTimerRef.current);
      }
    };
  }, []);

  const loadMembers = useCallback(async (organizationId: string) => {
    try {
      const response = await dashboardSessionFetch(`/dashboard/organizations/${organizationId}/members`);
      if (!response.ok) {
        setMembers([]);
        return;
      }
      const raw: unknown = await response.json();
      const parsed = parseDashboardMembershipItemsPayload(raw);
      setMembers(parsed ?? []);
    } catch {
      setMembers([]);
    }
  }, []);

  // Bumping this token re-runs the organizations-loading effect — used by the
  // Active project section's retry affordance after a failed fetch.
  const [organizationsReloadToken, setOrganizationsReloadToken] = useState(0);
  const reloadOrganizations = useCallback(() => {
    setOrganizationsReloadToken((token) => token + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setOrganizationsLoadState("loading");
      try {
        const response = await dashboardSessionFetch("/dashboard/organizations");
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
  }, [organizationsReloadToken]);

  // Bumping this token re-runs the members-loading effect — used by the
  // section's retry affordance after a failed fetch.
  const [membersReloadToken, setMembersReloadToken] = useState(0);
  const reloadMembers = useCallback(() => {
    setMembersReloadToken((token) => token + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (selectedOrganizationId) {
      queueMicrotask(() => {
        setMembersLoadState("loading");
      });
      void (async () => {
        try {
          const response = await dashboardSessionFetch(
            `/dashboard/organizations/${selectedOrganizationId}/members`,
          );
          if (cancelled) {
            return;
          }
          if (!response.ok) {
            setMembers([]);
            setMembersLoadState("error");
            return;
          }
          const raw: unknown = await response.json();
          const parsed = parseDashboardMembershipItemsPayload(raw);
          if (!cancelled) {
            setMembers(parsed ?? []);
            setMembersLoadState("ready");
          }
        } catch {
          if (!cancelled) {
            setMembers([]);
            setMembersLoadState("error");
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
  }, [selectedOrganizationId, membersReloadToken]);

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
    if (!sessionProjectId) {
      return null;
    }
    return accessibleProjects.find((r) => r.id === sessionProjectId)?.label ?? sessionProjectId;
  }, [accessibleProjects, sessionProjectId]);

  const selectedOrganization = organizations.find(
    (organization) => organization.organization_id === selectedOrganizationId,
  );

  const onSelectedOrganizationIdChange = useCallback(
    (value: string) => {
      cancelMemberBulkConfirm();
      setSelectedMemberIds(new Set());
      setMemberBulkRole("");
      setSelectedOrganizationId(value);
      const nextOrg = organizations.find((o) => o.organization_id === value);
      // Admins cannot assign owner/admin — clamp the invite role when switching orgs.
      if (nextOrg?.role === "admin") {
        setInviteRole((r) => (r === "owner" || r === "admin" ? "member" : r));
      }
    },
    [cancelMemberBulkConfirm, organizations],
  );

  const toggleMemberSelected = useCallback(
    (userId: string) => {
      cancelMemberBulkConfirm();
      setSelectedMemberIds((prev) => {
        const next = new Set(prev);
        if (next.has(userId)) {
          next.delete(userId);
        } else {
          next.add(userId);
        }
        return next;
      });
    },
    [cancelMemberBulkConfirm],
  );

  // Changing the chosen role invalidates any armed inline confirm.
  const changeMemberBulkRole = useCallback(
    (role: "" | MembershipRole) => {
      cancelMemberBulkConfirm();
      setMemberBulkRole(role);
    },
    [cancelMemberBulkConfirm],
  );

  const toggleSelectAllMembers = useCallback(() => {
    cancelMemberBulkConfirm();
    const ids = members.map((m) => m.user_id);
    setSelectedMemberIds((prev) => {
      const allSelected = ids.length > 0 && ids.every((id) => prev.has(id));
      if (allSelected) {
        return new Set();
      }
      return new Set(ids);
    });
  }, [cancelMemberBulkConfirm, members]);

  const allMemberIdsSelectable = members.map((m) => m.user_id);
  const allMembersSelected =
    allMemberIdsSelectable.length > 0 && allMemberIdsSelectable.every((id) => selectedMemberIds.has(id));

  const sendInvite = useCallback(async () => {
    if (!selectedOrganizationId) {
      return;
    }
    const email = inviteEmail.trim();
    if (inviteRole !== "owner" && isProtectedOwnerEmail(email)) {
      setOrgMessage(`${PROTECTED_OWNER_EMAIL} can only hold the owner role.`);
      return;
    }
    try {
      const response = await dashboardSessionJsonPost(
        `/dashboard/organizations/${selectedOrganizationId}/members/invite`,
        { email, role: inviteRole },
      );
      if (response.ok) {
        setInviteEmail("");
        setOrgMessage("Invitation sent.");
        void loadMembers(selectedOrganizationId);
      } else {
        setOrgMessage("Failed to invite member.");
      }
    } catch {
      setOrgMessage("Failed to invite member.");
    }
  }, [inviteEmail, inviteRole, loadMembers, selectedOrganizationId]);

  const applyMemberBulk = useCallback(async () => {
    if (!selectedOrganizationId || !memberBulkRole || selectedMemberIds.size === 0) {
      return;
    }
    // First Apply click arms the inline confirm; second click within the
    // window actually runs the bulk action. Non-blocking, no window.confirm.
    if (memberBulkConfirmCount !== selectedMemberIds.size) {
      setMemberBulkConfirmCount(selectedMemberIds.size);
      if (memberConfirmTimerRef.current) {
        clearTimeout(memberConfirmTimerRef.current);
      }
      memberConfirmTimerRef.current = setTimeout(() => {
        memberConfirmTimerRef.current = null;
        setMemberBulkConfirmCount(null);
      }, CONFIRM_WINDOW_MS);
      return;
    }
    cancelMemberBulkConfirm();
    let ok = 0;
    let skipped = 0;
    const failedEmails: string[] = [];
    for (const userId of selectedMemberIds) {
      const member = members.find((m) => m.user_id === userId);
      if (!member) {
        continue;
      }
      // The protected owner address can only ever hold the owner role.
      if (memberBulkRole !== "owner" && isProtectedOwnerEmail(member.email)) {
        skipped += 1;
        continue;
      }
      if (member.role === memberBulkRole) {
        continue;
      }
      try {
        const response = await dashboardSessionJsonPut(
          `/dashboard/organizations/${selectedOrganizationId}/members/${userId}/role`,
          { role: memberBulkRole },
        );
        if (response.ok) {
          ok += 1;
        } else {
          failedEmails.push(member.email);
        }
      } catch {
        failedEmails.push(member.email);
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
    if (failedEmails.length) {
      parts.push(`${failedEmails.length} failed (${failedEmails.join(", ")}).`);
    }
    setOrgMessage(parts.join(" ") || "No changes applied.");
  }, [
    cancelMemberBulkConfirm,
    loadMembers,
    memberBulkConfirmCount,
    memberBulkRole,
    members,
    selectedMemberIds,
    selectedOrganizationId,
  ]);

  return {
    organizations,
    organizationsLoadState,
    selectedOrganizationId,
    setSelectedOrganizationId,
    selectedOrganization,
    members,
    membersLoadState,
    reloadMembers,
    reloadOrganizations,
    inviteEmail,
    setInviteEmail,
    inviteRole,
    setInviteRole,
    orgMessage,
    setOrgMessage,
    memberBulkRole,
    setMemberBulkRole: changeMemberBulkRole,
    memberBulkConfirmCount,
    cancelMemberBulkConfirm,
    selectedMemberIds,
    setSelectedMemberIds,
    loadMembers,
    accessibleProjects,
    currentProjectLabel,
    onSelectedOrganizationIdChange,
    toggleMemberSelected,
    toggleSelectAllMembers,
    allMembersSelected,
    applyMemberBulk,
    sendInvite,
  };
}
