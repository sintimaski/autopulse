"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { recordActivationMilestone } from "../../../lib/activationClientMetrics";
import { useAsyncAction } from "../../../lib/useAsyncAction";
import { ApCard } from "../../ui/ApCard";
import { useDashboardData } from "../DashboardDataContext";
import { isApiSubpathDashboard } from "../dashboardTypes";
import { canManageIngestApiKeys } from "../dashboardRoleHelpers";

export function onboardingFirstIngestGuidance(subpathUi: boolean): string {
  if (subpathUi) {
    return (
      "After the SDK sends its first batch, expect HTTP 200 with an accepted count; " +
      "counts update here shortly after (refresh if you just deployed)."
    );
  }
  return (
    "Send traffic through your instrumented app and confirm your ingest call returns HTTP 200 " +
    "with an accepted count, then refresh."
  );
}

export function onboardingRoleActionCopy(canIssueKeys: boolean): string {
  if (canIssueKeys) {
    return "As owner/admin, issue or rotate the ingest key and verify the app receives traffic.";
  }
  return "As member/viewer, request an owner/admin to issue or rotate the ingest key, then verify incoming traffic.";
}

export function onboardingNoDataPrimaryAction(canIssueKeys: boolean, subpathUi: boolean): string {
  if (canIssueKeys) {
    return subpathUi
      ? "Primary next action: issue a key, rebuild static UI, restart backend, then send one request."
      : "Primary next action: issue a key, add it to your app env, restart, then send one request.";
  }
  return "Primary next action: ask an owner/admin for a key update, then send one request to confirm data flow.";
}

/**
 * Surfaces practical SDK knobs that reduce noisy telemetry without expanding MVP scope.
 * Mirrors `lumonox.monitor(..., request_sample_rate=..., ignore_path_prefixes=(...))` defaults.
 */
export function onboardingNoiseControlHint(): string {
  return (
    "Reduce noise: pass `ignore_path_prefixes=(\"/health\", \"/ready\")` to skip probes, " +
    "and set `request_sample_rate=0.5` (or lower) on high-volume routes to keep ingest small."
  );
}

export function OnboardingContent() {
  const router = useRouter();
  const d = useDashboardData();
  const canIssueKeys = canManageIngestApiKeys(d.sessionMembershipRole);
  const subpathUi = isApiSubpathDashboard();
  const [message, setMessage] = useState<string | null>(null);
  const [continueBusy, setContinueBusy] = useState(false);
  const status = d.onboardingStatus;
  const hasIssuedApiKey = status?.ingest_key_ready ?? (d.apiKeys.length > 0 || Boolean(d.lastIssuedApiKey));
  const hasFirstEvent =
    status?.first_event_received ?? ((d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0);

  const apiKeyPreview = useMemo(() => {
    if (d.lastIssuedApiKey) return d.lastIssuedApiKey;
    if (d.apiKeys[0]) return `${d.apiKeys[0].key_id} (existing)`;
    return null;
  }, [d.apiKeys, d.lastIssuedApiKey]);

  // Loader + double-submit guard for the key actions (mirrors Settings).
  const [issueApiKey, issuingApiKey] = useAsyncAction(
    useCallback(async () => {
      const ok = await d.issueApiKey();
      setMessage(
        ok
          ? subpathUi
            ? "Issued — .env.lumonox synced automatically. Rebuild UI + restart host."
            : "Issued — copy into host env and restart app."
          : "Issue failed.",
      );
    }, [d, subpathUi]),
  );
  const [refreshApiKeys, refreshingApiKeys] = useAsyncAction(d.refreshApiKeys);

  useEffect(() => {
    recordActivationMilestone("onboarding_view");
  }, []);
  useEffect(() => {
    if (hasIssuedApiKey) {
      recordActivationMilestone("key_issued_view");
    }
  }, [hasIssuedApiKey]);
  useEffect(() => {
    if (hasFirstEvent) {
      recordActivationMilestone("first_event_seen");
    }
  }, [hasFirstEvent]);

  return (
    <ApCard className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">Onboarding</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          {subpathUi ? (
            <>
              Static UI on the API host uses a repo-root{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-950">
                .env.lumonox
              </code>{" "}
              file for ingest + Next public keys. Source it before{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-neutral-950">
                npm run build
              </code>
              , then restart the backend if needed.
            </>
          ) : (
            "Put the issued key in your app as LUMONOX_API_KEY and set LUMONOX_INGEST_URL to /ingest on your backend."
          )}
        </p>
        <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
          {onboardingRoleActionCopy(canIssueKeys)}
        </p>
        <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-slate-600 dark:text-neutral-400">
          <li>Confirm backend health: <code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">/health</code> and{" "}
            <code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">/ready</code> return OK.</li>
          <li>Instrument with one call — see sample below — then hit any route once.</li>
          <li>Use the same scope pivot (Overview / Diagnosis / Requests) after data arrives.</li>
        </ul>
      </div>

      <ol className="space-y-3">
        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">1. Session</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">Signed in with magic link.</p>
          <span className="mt-2 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            Done
          </span>
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">2. Ingest key</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            {canIssueKeys
              ? subpathUi
                ? "Issue below only if you want a new token; dashboard auto-syncs .env.lumonox. Rebuild UI after key changes."
                : "Issue, then copy into host env as LUMONOX_API_KEY."
              : "Ask an organization owner or admin to issue or rotate the ingest key."}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={!canIssueKeys || issuingApiKey || refreshingApiKeys}
              onClick={() => void issueApiKey()}
              className="ap-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {issuingApiKey ? "Issuing…" : "Issue key"}
            </button>
            <button
              type="button"
              disabled={issuingApiKey || refreshingApiKeys}
              onClick={() => void refreshApiKeys()}
              className="ap-btn disabled:cursor-not-allowed disabled:opacity-50"
            >
              {refreshingApiKeys ? "Refreshing…" : "Refresh"}
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasIssuedApiKey
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasIssuedApiKey ? "OK" : "…"}
            </span>
          </div>
          {apiKeyPreview ? (
            <code className="mt-2 block break-all rounded bg-slate-100 px-2 py-1 text-xs dark:bg-neutral-950 dark:text-neutral-200">
              {apiKeyPreview}
            </code>
          ) : null}
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">3. First ingest</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            {onboardingFirstIngestGuidance(subpathUi)}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => d.setRefreshToken((t) => t + 1)} className="ap-btn">
              Refresh
            </button>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasFirstEvent
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasFirstEvent ? "OK" : "…"}
            </span>
          </div>
          {!hasFirstEvent ? (
            <p className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
              {onboardingNoDataPrimaryAction(canIssueKeys, subpathUi)}
            </p>
          ) : null}
          <p className="mt-2 text-xs text-slate-500 dark:text-neutral-500">
            {onboardingNoiseControlHint()}
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-relaxed text-emerald-100">
            {`from fastapi import FastAPI
from lumonox import lumonox

app = FastAPI()
lumonox(
    app,
    request_sample_rate=1.0,
    ignore_path_prefixes=("/health", "/ready"),
)`}
          </pre>
        </li>
      </ol>

      <div className="flex flex-col gap-2 border-t border-slate-200 pt-4 dark:border-neutral-700">
        <p className="text-xs text-slate-600 dark:text-neutral-400">
          Open the dashboard anytime in read-only mode. Mark onboarding complete once first ingest is confirmed.
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="ap-btn w-fit"
          >
            Open dashboard (read-only)
          </button>
          <button
            type="button"
            disabled={!hasFirstEvent || continueBusy}
            onClick={async () => {
              setContinueBusy(true);
              try {
                const ok = await d.completeOnboarding();
                if (ok) {
                  router.push("/dashboard");
                } else {
                  setMessage("Could not save onboarding completion. Try refresh, then Continue again.");
                }
              } finally {
                setContinueBusy(false);
              }
            }}
            className="ap-btn-primary w-fit disabled:pointer-events-none disabled:opacity-40"
          >
            {continueBusy ? "Saving…" : "Mark complete and continue"}
          </button>
        </div>
      </div>

      {message ? <p className="text-xs text-slate-600 dark:text-neutral-400">{message}</p> : null}
    </ApCard>
  );
}
