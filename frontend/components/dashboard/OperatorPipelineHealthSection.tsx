"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { parseDashboardOperatorHealthResponse } from "../../utils/dashboardResponseGuards";
import type { DashboardOperatorHealthResponse, OperatorHealthStatus } from "./dashboardTypes";
import { useDashboardData } from "./DashboardDataContext";
import { canManageProjectAlertsAndRetention } from "./dashboardRoleHelpers";
import { dashboardSessionFetch } from "./dashboardSessionFetch";
import { OperatorReliabilityCallout } from "./OperatorReliabilityCallout";

function statusTone(status: OperatorHealthStatus): string {
  switch (status) {
    case "healthy":
      return "border-emerald-300/80 bg-emerald-50/90 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/35 dark:text-emerald-200";
    case "degraded":
      return "border-amber-300/80 bg-amber-50/90 text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100";
    case "critical":
      return "border-rose-300/80 bg-rose-50/90 text-rose-950 dark:border-rose-900/50 dark:bg-rose-950/35 dark:text-rose-100";
    case "not_configured":
      return "border-slate-200/80 bg-slate-100/80 text-slate-700 dark:border-neutral-600 dark:bg-neutral-800/70 dark:text-neutral-200";
    default:
      return "border-slate-200/80 bg-slate-50/90 text-slate-700 dark:border-neutral-600 dark:bg-neutral-800/60 dark:text-neutral-200";
  }
}

function HealthMetricsBody({ payload }: { payload: DashboardOperatorHealthResponse }) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-slate-600 dark:text-neutral-400">Overall</span>
        <span
          className={`inline-flex rounded-full border px-2 py-0.5 font-semibold capitalize ${statusTone(payload.overall_status)}`}
        >
          {payload.overall_status.replace(/_/g, " ")}
        </span>
      </div>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {payload.subsystems.map((row) => (
          <li
            key={row.id}
            className="flex flex-col gap-0.5 rounded-md border border-slate-200/70 bg-white/80 px-2 py-1.5 dark:border-neutral-700 dark:bg-neutral-950/40"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-slate-800 dark:text-neutral-100">{row.label}</span>
              <span
                className={`inline-flex shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold capitalize ${statusTone(row.status)}`}
              >
                {row.status.replace(/_/g, " ")}
              </span>
            </div>
            <p className="text-[10px] leading-snug text-slate-600 dark:text-neutral-400">{row.summary}</p>
            {row.settings_anchor ? (
              <Link
                href={`/settings#${row.settings_anchor}`}
                className="text-[10px] font-medium text-sky-800 underline-offset-2 hover:underline dark:text-sky-300"
              >
                Open in Settings
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OperatorPipelineHealthSection() {
  const d = useDashboardData();
  const canView = canManageProjectAlertsAndRetention(d.sessionMembershipRole);
  const [loadState, setLoadState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [payload, setPayload] = useState<DashboardOperatorHealthResponse | null>(null);

  useEffect(() => {
    if (!canView) {
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoadState("loading");
      try {
        const response = await dashboardSessionFetch("/dashboard/operator-health");
        if (!response.ok) {
          throw new Error(`operator-health ${response.status}`);
        }
        const raw: unknown = await response.json();
        const parsed = parseDashboardOperatorHealthResponse(raw);
        if (cancelled) {
          return;
        }
        if (!parsed) {
          throw new Error("unexpected shape");
        }
        setPayload(parsed);
        setLoadState("ready");
      } catch {
        if (!cancelled) {
          setPayload(null);
          setLoadState("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canView]);

  const allChecksOk = useMemo(() => {
    if (!payload?.enabled || loadState !== "ready") {
      return false;
    }
    if (payload.overall_status !== "healthy") {
      return false;
    }
    return payload.subsystems.every(
      (s) => s.status === "healthy" || s.status === "not_configured",
    );
  }, [payload, loadState]);

  if (!canView) {
    return <OperatorReliabilityCallout />;
  }

  return (
    <section
      className="mb-3 rounded-lg border border-slate-200/80 bg-slate-50/90 px-3 py-2.5 text-xs text-slate-700 dark:border-neutral-700 dark:bg-neutral-900/60 dark:text-neutral-300"
      aria-label="Operator subsystem health"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-800 dark:text-neutral-100">Operator health</p>
          <p className="mt-0.5 text-[11px] leading-snug text-slate-600 dark:text-neutral-400">
            Scheduler, ingest, realtime bus, retention poll, and alert job signals for this API process.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-1 sm:flex-row sm:items-center">
          <Link
            href="/settings#lx-settings-internal-metrics"
            className="rounded-md border border-slate-300/80 bg-white px-2 py-1 text-[11px] font-medium text-sky-800 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-sky-200 dark:hover:bg-neutral-800/80"
          >
            Internal metrics
          </Link>
          <Link
            href="/settings#lx-settings-system-diagnostics"
            className="rounded-md border border-slate-300/80 bg-white px-2 py-1 text-[11px] font-medium text-sky-800 hover:bg-slate-50 dark:border-neutral-600 dark:bg-neutral-800 dark:text-sky-200 dark:hover:bg-neutral-800/80"
          >
            System diagnostics
          </Link>
        </div>
      </div>
      {loadState === "loading" ? (
        <p className="mt-2 text-[11px] text-slate-500 dark:text-neutral-500">Loading health summary…</p>
      ) : loadState === "error" || !payload ? (
        <p className="mt-2 text-[11px] text-rose-700 dark:text-rose-300">
          Could not load operator health. Use Settings links above.
        </p>
      ) : !payload.enabled ? (
        <p className="mt-2 text-[11px] text-slate-600 dark:text-neutral-400">
          {payload.reason ?? "Internal metrics are disabled on this server."}
        </p>
      ) : allChecksOk ? (
        <details className="mt-2 rounded-md border border-emerald-200/70 bg-emerald-50/40 dark:border-emerald-900/45 dark:bg-emerald-950/20">
          <summary className="cursor-pointer list-none px-2 py-1.5 text-[11px] font-medium text-emerald-900 marker:content-none dark:text-emerald-100 [&::-webkit-details-marker]:hidden">
            <span className="select-none">All operator checks passed — expand for subsystem details</span>
          </summary>
          <div className="border-t border-emerald-200/60 px-2 pb-2 pt-2 dark:border-emerald-900/40">
            <HealthMetricsBody payload={payload} />
          </div>
        </details>
      ) : (
        <div className="mt-2">
          <HealthMetricsBody payload={payload} />
        </div>
      )}
    </section>
  );
}
