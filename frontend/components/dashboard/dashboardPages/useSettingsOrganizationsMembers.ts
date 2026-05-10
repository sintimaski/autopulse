"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { DASHBOARD_FETCH_TIMEOUT_MS, fetchWithTimeout } from "../dashboardDataFetchUtils";
import {
  parseDashboardMembershipItemsPayload,
  parseDashboardOrganizationListResponse,
} from "../../../utils/dashboardResponseGuards";
import {
  buildApiUrl,
  type DashboardMembershipItem,
  type DashboardOrganizationSummary,
} from "../dashboardTypes";
import { isProtectedOwnerEmail } from "./settingsContentUtils";

export function useSettingsOrganizationsMembers(sessionProjectId: string | null) {
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

  const loadMembers = useCallback(async (organizationId: string) => {
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
      const parsed = parseDashboardMembershipItemsPayload(raw);
      setMembers(parsed ?? []);
    } catch {
      setMembers([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setOrganizationsLoadState("loading");
      try {
        const response = await fetchWithTimeout(
          buildApiUrl("/dashboard/organizations"),
          { credentials: "include" },
          DASHBOARD_FETCH_TIMEOUT_MS,
        );
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
          const parsed = parseDashboardMembershipItemsPayload(raw);
          if (!cancelled) {
            setMembers(parsed ?? []);
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
      setSelectedMemberIds(new Set());
      setMemberBulkRole("");
      setSelectedOrganizationId(value);
      const nextOrg = organizations.find((o) => o.organization_id === value);
      if (nextOrg?.role === "admin") {
        setInviteRole((r) => (r === "owner" ? "member" : r));
      }
    },
    [organizations],
  );

  const toggleMemberSelected = useCallback((userId: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  }, []);

  const allMemberIdsSelectable = members.map((m) => m.user_id);
  const allMembersSelected =
    allMemberIdsSelectable.length > 0 && allMemberIdsSelectable.every((id) => selectedMemberIds.has(id));

  const applyMemberBulk = useCallback(async () => {
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
  }, [loadMembers, memberBulkRole, members, selectedMemberIds, selectedOrganizationId]);

  return {
    organizations,
    organizationsLoadState,
    selectedOrganizationId,
    setSelectedOrganizationId,
    selectedOrganization,
    members,
    membersLoadState,
    inviteEmail,
    setInviteEmail,
    inviteRole,
    setInviteRole,
    orgMessage,
    setOrgMessage,
    memberBulkRole,
    setMemberBulkRole,
    selectedMemberIds,
    setSelectedMemberIds,
    loadMembers,
    accessibleProjects,
    currentProjectLabel,
    onSelectedOrganizationIdChange,
    toggleMemberSelected,
    allMembersSelected,
    applyMemberBulk,
  };
}
