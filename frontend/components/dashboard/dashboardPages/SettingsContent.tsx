"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type {
  DashboardMembershipItem,
  DashboardOrganizationListResponse,
  DashboardOrganizationSummary,
} from "../dashboardTypes";
import { useDashboardData } from "../DashboardDataContext";
import { buildApiUrl } from "../dashboardTypes";

export function SettingsContent() {
  const d = useDashboardData();
  const [themeMessage, setThemeMessage] = useState<string | null>(null);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);
  const [retentionDraft, setRetentionDraft] = useState<{
    raw_events_days: number;
    logs_query_max_window_minutes: number;
    retention_plan: "starter" | "standard" | "extended";
    archival_enabled: boolean;
    archival_mode: "db_archive";
    archival_status: "idle" | "running" | "failed";
    archival_last_success_at: string | null;
    archival_last_error: string | null;
  } | null>(null);
  const [organizations, setOrganizations] = useState<DashboardOrganizationSummary[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [members, setMembers] = useState<DashboardMembershipItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"owner" | "member">("member");
  const [orgMessage, setOrgMessage] = useState<string | null>(null);
  const [apiKeyMessage, setApiKeyMessage] = useState<string | null>(null);
  const effectiveRetentionDraft = retentionDraft ?? d.retentionSettings;

  const selectedOrganization = organizations.find((organization) => organization.organization_id === selectedOrganizationId);

  const loadMembers = async (organizationId: string) => {
    try {
      const response = await fetch(buildApiUrl(`/dashboard/organizations/${organizationId}/members`), {
        credentials: "include",
      });
      if (!response.ok) {
        setMembers([]);
        return;
      }
      const payload = (await response.json()) as { members: DashboardMembershipItem[] };
      setMembers(payload.members);
    } catch {
      setMembers([]);
    }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(buildApiUrl("/dashboard/organizations"), {
          credentials: "include",
        });
        if (!response.ok || cancelled) {
          return;
        }
        const payload = (await response.json()) as DashboardOrganizationListResponse;
        if (cancelled) {
          return;
        }
        setOrganizations(payload.organizations);
        if (payload.organizations[0]) {
          setSelectedOrganizationId((prev) => prev ?? payload.organizations[0].organization_id);
        }
      } catch {
        // no-op
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (selectedOrganizationId) {
      void (async () => {
        try {
          const response = await fetch(
            buildApiUrl(`/dashboard/organizations/${selectedOrganizationId}/members`),
            {
              credentials: "include",
            },
          );
          if (!response.ok || cancelled) {
            setMembers([]);
            return;
          }
          const payload = (await response.json()) as { members: DashboardMembershipItem[] };
          if (!cancelled) {
            setMembers(payload.members);
          }
        } catch {
          if (!cancelled) {
            setMembers([]);
          }
        }
      })();
    }
    return () => {
      cancelled = true;
    };
  }, [selectedOrganizationId]);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Retention policy</h2>
        {effectiveRetentionDraft ? (
          <>
            <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
              Configure how long raw events are retained and the max query window for SQL logs.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-slate-700 dark:text-neutral-200">
                Raw events retention (days)
                <input
                  type="number"
                  min={1}
                  value={effectiveRetentionDraft.raw_events_days}
                  onChange={(event) =>
                    setRetentionDraft({
                      raw_events_days: Number(event.target.value),
                      logs_query_max_window_minutes:
                        effectiveRetentionDraft.logs_query_max_window_minutes,
                      retention_plan: effectiveRetentionDraft.retention_plan,
                      archival_enabled: effectiveRetentionDraft.archival_enabled,
                      archival_mode: effectiveRetentionDraft.archival_mode,
                      archival_status: effectiveRetentionDraft.archival_status,
                      archival_last_success_at: effectiveRetentionDraft.archival_last_success_at,
                      archival_last_error: effectiveRetentionDraft.archival_last_error,
                    })
                  }
                  className="ap-input mt-1"
                />
              </label>
              <label className="text-sm text-slate-700 dark:text-neutral-200">
                Max SQL query window (minutes)
                <input
                  type="number"
                  min={1}
                  value={effectiveRetentionDraft.logs_query_max_window_minutes}
                  onChange={(event) =>
                    setRetentionDraft({
                      raw_events_days: effectiveRetentionDraft.raw_events_days,
                      logs_query_max_window_minutes: Number(event.target.value),
                      retention_plan: effectiveRetentionDraft.retention_plan,
                      archival_enabled: effectiveRetentionDraft.archival_enabled,
                      archival_mode: effectiveRetentionDraft.archival_mode,
                      archival_status: effectiveRetentionDraft.archival_status,
                      archival_last_success_at: effectiveRetentionDraft.archival_last_success_at,
                      archival_last_error: effectiveRetentionDraft.archival_last_error,
                    })
                  }
                  className="ap-input mt-1"
                />
              </label>
              <label className="text-sm text-slate-700 dark:text-neutral-200">
                Retention tier
                <select
                  value={effectiveRetentionDraft.retention_plan}
                  onChange={(event) =>
                    setRetentionDraft({
                      ...effectiveRetentionDraft,
                      retention_plan: event.target.value as "starter" | "standard" | "extended",
                    })
                  }
                  className="ap-input mt-1"
                >
                  <option value="starter">Starter</option>
                  <option value="standard">Standard</option>
                  <option value="extended">Extended</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-neutral-200">
                <input
                  type="checkbox"
                  checked={effectiveRetentionDraft.archival_enabled}
                  onChange={(event) =>
                    setRetentionDraft({
                      ...effectiveRetentionDraft,
                      archival_enabled: event.target.checked,
                    })
                  }
                />
                Archive expired events before delete
              </label>
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-neutral-400">
              Archive status: {effectiveRetentionDraft.archival_status}
              {effectiveRetentionDraft.archival_last_success_at
                ? ` · last success ${new Date(effectiveRetentionDraft.archival_last_success_at).toLocaleString()}`
                : ""}
              {effectiveRetentionDraft.archival_last_error
                ? ` · last error ${effectiveRetentionDraft.archival_last_error}`
                : ""}
            </p>
            <button
              type="button"
              onClick={async () => {
                if (!effectiveRetentionDraft) {
                  return;
                }
                const ok = await d.saveRetentionSettings(effectiveRetentionDraft);
                setRetentionMessage(ok ? "Retention settings saved." : "Failed to save retention settings.");
              }}
              className="ap-btn-primary mt-3"
            >
              Save retention policy
            </button>
            {retentionMessage ? (
              <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{retentionMessage}</p>
            ) : null}
          </>
        ) : (
          <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">Loading retention settings...</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Organization governance</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Manage small-team membership with owner/member roles.
        </p>
        {organizations.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600 dark:text-neutral-300">No organizations available for this account.</p>
        ) : (
          <>
            <label className="mt-3 block text-sm text-slate-700 dark:text-neutral-200">
              Organization
              <select
                value={selectedOrganizationId ?? ""}
                onChange={(event) => {
                  setSelectedOrganizationId(event.target.value);
                  void loadMembers(event.target.value);
                }}
                className="ap-select mt-1"
              >
                {organizations.map((organization) => (
                  <option key={organization.organization_id} value={organization.organization_id}>
                    {organization.organization_name} ({organization.role})
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Email</th>
                    <th className="px-3 py-2 font-semibold">Role</th>
                    <th className="px-3 py-2 font-semibold">Joined</th>
                    <th className="px-3 py-2 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
                  {members.map((member) => (
                    <tr key={member.user_id}>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">{member.email}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">{member.role}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                        {new Date(member.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        {selectedOrganization?.role === "owner" ? (
                          <button
                            type="button"
                            onClick={async () => {
                              if (!selectedOrganizationId) {
                                return;
                              }
                              const nextRole = member.role === "owner" ? "member" : "owner";
                              const response = await fetch(
                                buildApiUrl(
                                  `/dashboard/organizations/${selectedOrganizationId}/members/${member.user_id}/role`,
                                ),
                                {
                                  method: "PUT",
                                  headers: { "Content-Type": "application/json" },
                                  credentials: "include",
                                  body: JSON.stringify({ role: nextRole }),
                                },
                              );
                              if (response.ok) {
                                setOrgMessage("Member role updated.");
                                void loadMembers(selectedOrganizationId);
                              } else {
                                setOrgMessage("Failed to update member role.");
                              }
                            }}
                            className="ap-btn-primary px-2 py-1 text-xs"
                          >
                            Set {member.role === "owner" ? "member" : "owner"}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-500 dark:text-neutral-400">Owner only</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {selectedOrganization?.role === "owner" ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <input
                  type="email"
                  value={inviteEmail}
                  placeholder="new-member@example.com"
                  onChange={(event) => setInviteEmail(event.target.value)}
                  className="ap-input"
                />
                <select
                  value={inviteRole}
                  onChange={(event) => setInviteRole(event.target.value as "owner" | "member")}
                  className="ap-select"
                >
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
                <button
                  type="button"
                  onClick={async () => {
                    if (!selectedOrganizationId) {
                      return;
                    }
                    const response = await fetch(
                      buildApiUrl(`/dashboard/organizations/${selectedOrganizationId}/members/invite`),
                      {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        credentials: "include",
                        body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
                      },
                    );
                    if (response.ok) {
                      setInviteEmail("");
                      setOrgMessage("Member invited.");
                      void loadMembers(selectedOrganizationId);
                    } else {
                      setOrgMessage("Failed to invite member.");
                    }
                  }}
                  className="ap-btn-primary"
                >
                  Invite member
                </button>
              </div>
            ) : null}
            {orgMessage ? <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{orgMessage}</p> : null}
          </>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">API key lifecycle</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Issue, rotate, and revoke ingest keys. These actions are owner-only and audited.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
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
        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
              <tr>
                <th className="px-3 py-2 font-semibold">Key ID</th>
                <th className="px-3 py-2 font-semibold">Created</th>
                <th className="px-3 py-2 font-semibold">Revoked</th>
                <th className="px-3 py-2 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
              {d.apiKeys.map((item) => (
                <tr key={item.key_id}>
                  <td className="px-3 py-2 font-mono text-slate-700 dark:text-neutral-200">{item.key_id}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                    {item.revoked_at ? new Date(item.revoked_at).toLocaleString() : "active"}
                  </td>
                  <td className="px-3 py-2">
                    {item.revoked_at ? (
                      <span className="text-xs text-slate-500 dark:text-neutral-400">No actions</span>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={async () => {
                            const ok = await d.rotateApiKey(item.key_id);
                            setApiKeyMessage(ok ? "API key rotated." : "Failed to rotate API key.");
                          }}
                          className="ap-btn-primary px-2 py-1 text-xs"
                        >
                          Rotate
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            const ok = await d.revokeApiKey(item.key_id);
                            setApiKeyMessage(ok ? "API key revoked." : "Failed to revoke API key.");
                          }}
                          className="ap-btn-danger px-2 py-1 text-xs"
                        >
                          Revoke
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {apiKeyMessage ? <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{apiKeyMessage}</p> : null}
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Appearance</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Theme preference is now a project setting stored in the backend.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {(["system", "light", "dark"] as const).map((theme) => (
            <button
              key={theme}
              type="button"
              onClick={async () => {
                const ok = await d.saveThemePreference(theme);
                setThemeMessage(ok ? "Theme saved." : "Failed to save theme.");
              }}
              disabled={d.themeSettingsSaving}
              className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 ${
                d.themePreference === theme
                  ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-100"
                  : "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
              }`}
            >
              {theme === "system" ? "System" : theme === "light" ? "Light" : "Dark"}
            </button>
          ))}
        </div>
        {themeMessage ? (
          <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">{themeMessage}</p>
        ) : null}
        <div className="mt-4 border-t border-slate-200 pt-3 dark:border-neutral-700">
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-neutral-200">
            <input
              type="checkbox"
              checked={d.excludeAutopulseTraffic}
              disabled={d.themeSettingsSaving}
              onChange={async (event) => {
                const ok = await d.saveExcludeAutopulseTraffic(event.target.checked);
                setThemeMessage(
                  ok
                    ? "Traffic filter preference saved."
                    : "Failed to save traffic filter preference.",
                );
              }}
            />
            Exclude AutoPulse internal traffic (`/autopulse/*`, `/dashboard/*`, `/ingest`) from analytics
          </label>
          <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
            Applies to dashboard, diagnosis, request logs, SQL log queries, and alert evaluations so
            embedded UI, dashboard API, and ingest calls do not skew counts.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Settings model (MVP)</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          This page defines project-level defaults used across Dashboard, Diagnosis, Logs, and Alerts.
        </p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-neutral-700">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 dark:bg-neutral-800 dark:text-neutral-300">
              <tr>
                <th className="px-3 py-2 font-semibold">Setting group</th>
                <th className="px-3 py-2 font-semibold">Parameters</th>
                <th className="px-3 py-2 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white dark:divide-neutral-800 dark:bg-neutral-900">
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Server scope defaults</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  Time window, method/status/path/env/service filters, latency bounds, grouped-error sort.
                </td>
                <td className="px-3 py-2 text-emerald-700 dark:text-emerald-400">Active</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Alert policy</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  Enable flag, destination email, spike/outage thresholds, cooldown.
                </td>
                <td className="px-3 py-2 text-emerald-700 dark:text-emerald-400">Active</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-medium text-slate-800 dark:text-neutral-100">Delivery channels</td>
                <td className="px-3 py-2 text-slate-700 dark:text-neutral-200">
                  Email dispatch is active. Additional channels are explicitly marked as planned until implemented.
                </td>
                <td className="px-3 py-2 text-amber-700 dark:text-amber-400">Capability-driven</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Alert policy</h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-neutral-400">
          Alert policy editing is centralized in the Alerts page to avoid drift between two separate forms.
        </p>
        <Link
          href="/alerts"
          className="ap-btn-primary mt-3"
        >
          Open Alerts policy editor
        </Link>
        <Link
          href="/onboarding"
          className="ap-btn mt-3 ml-2"
        >
          Open onboarding checklist
        </Link>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Delivery channels</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Channel availability is sourced from backend capabilities.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {d.alertCapabilities.map((capability) => (
            <div
              key={capability.channel}
              className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-neutral-700 dark:bg-neutral-800/70"
            >
              <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">
                {capability.channel.toUpperCase()}
              </p>
              <p
                className={`mt-1 text-xs font-medium ${
                  capability.status === "active"
                    ? "text-emerald-700 dark:text-emerald-300"
                    : capability.status === "planned"
                      ? "text-amber-700 dark:text-amber-300"
                      : "text-rose-700 dark:text-rose-300"
                }`}
              >
                {capability.status === "active" ? "Active" : capability.status === "planned" ? "Planned" : "Unavailable"}
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-neutral-300">{capability.reason}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
