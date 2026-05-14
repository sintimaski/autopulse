"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { recordActivationMilestone } from "../../../lib/activationClientMetrics";
import { useAsyncAction } from "../../../lib/useAsyncAction";
import { ApCard } from "../../ui/ApCard";
import { copyTextToClipboard } from "../clipboard";
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

type IntegrationFramework = "fastapi" | "django";

/**
 * Minimal one-line FastAPI integration. `lumonox(app)` is the SDK's recommended
 * default (see sdk/README.md); `monitor(app)` is the back-compat alias.
 */
export function onboardingFastApiSnippet(): string {
  return `from fastapi import FastAPI
from lumonox import lumonox

app = FastAPI()
lumonox(app)`;
}

/** Minimal Django ASGI integration — opt-in via the `lumonox-sdk[django]` extra. */
export function onboardingDjangoSnippet(): string {
  return `# pip install "lumonox-sdk[django]"
# asgi.py
from django.core.asgi import get_asgi_application
from lumonox.django import monitor, wrap_asgi

monitor()
application = wrap_asgi(get_asgi_application())

# settings.py — add to MIDDLEWARE:
#   "lumonox.django.middleware.LumonoxMiddleware"`;
}

export function onboardingIntegrationSnippet(framework: IntegrationFramework): string {
  return framework === "django" ? onboardingDjangoSnippet() : onboardingFastApiSnippet();
}

export function OnboardingContent() {
  const router = useRouter();
  const d = useDashboardData();
  const canIssueKeys = canManageIngestApiKeys(d.sessionMembershipRole);
  const subpathUi = isApiSubpathDashboard();
  const [message, setMessage] = useState<string | null>(null);
  const [continueBusy, setContinueBusy] = useState(false);
  const [framework, setFramework] = useState<IntegrationFramework>("fastapi");
  const [snippetCopied, setSnippetCopied] = useState(false);
  const [keyCopied, setKeyCopied] = useState(false);
  const status = d.onboardingStatus;
  const sessionReady = status?.session_authenticated ?? d.hasDashboardSession;
  const hasIssuedApiKey = status?.ingest_key_ready ?? (d.apiKeys.length > 0 || Boolean(d.lastIssuedApiKey));
  const hasFirstEvent =
    status?.first_event_received ?? ((d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0);

  const apiKeyPreview = useMemo(() => {
    if (d.lastIssuedApiKey) return d.lastIssuedApiKey;
    if (d.apiKeys[0]) return `${d.apiKeys[0].key_id} (existing)`;
    return null;
  }, [d.apiKeys, d.lastIssuedApiKey]);
  const snippet = onboardingIntegrationSnippet(framework);

  // Loader + double-submit guard for the key actions (mirrors Settings).
  const [issueApiKey, issuingApiKey] = useAsyncAction(
    useCallback(async () => {
      try {
        const ok = await d.issueApiKey();
        // Pull the authoritative onboarding status so the step pill reflects reality.
        await d.refreshOnboardingStatus();
        setMessage(
          ok
            ? subpathUi
              ? "Issued — .env.lumonox synced automatically. Rebuild UI + restart host."
              : "Issued — copy into host env and restart app."
            : "Issue failed — check you still have owner/admin access, then retry.",
        );
      } catch {
        setMessage("Issue failed — network error reaching the dashboard API. Retry shortly.");
      }
    }, [d, subpathUi, setMessage]),
  );
  const [refreshIngestKey, refreshingApiKeys] = useAsyncAction(
    useCallback(async () => {
      try {
        await d.refreshApiKeys();
        await d.refreshOnboardingStatus();
      } catch {
        setMessage("Could not refresh key status — network error. Retry shortly.");
      }
    }, [d, setMessage]),
  );
  const [refreshFirstIngest, refreshingFirstIngest] = useAsyncAction(
    useCallback(async () => {
      d.setRefreshToken((t) => t + 1);
      try {
        await d.refreshOnboardingStatus();
      } catch {
        /* status fetch is best-effort; the request bundle still refreshes */
      }
    }, [d]),
  );

  const copySnippet = useCallback(async () => {
    const ok = await copyTextToClipboard(snippet);
    setSnippetCopied(ok);
    if (ok) {
      window.setTimeout(() => setSnippetCopied(false), 2000);
    }
  }, [snippet]);

  const copyKey = useCallback(async () => {
    if (!d.lastIssuedApiKey) return;
    const ok = await copyTextToClipboard(d.lastIssuedApiKey);
    setKeyCopied(ok);
    if (ok) {
      window.setTimeout(() => setKeyCopied(false), 2000);
    }
  }, [d.lastIssuedApiKey]);

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
          <span
            aria-label={sessionReady ? "Session ready" : "Session not established"}
            className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
              sessionReady
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
            }`}
          >
            {sessionReady ? "Done" : "Sign in"}
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
              onClick={() => void refreshIngestKey()}
              className="ap-btn disabled:cursor-not-allowed disabled:opacity-50"
            >
              {refreshingApiKeys ? "Refreshing…" : "Refresh"}
            </button>
            <span
              aria-label={hasIssuedApiKey ? "Ingest key ready" : "Waiting for ingest key"}
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasIssuedApiKey
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasIssuedApiKey ? "OK" : "Pending"}
            </span>
          </div>
          {apiKeyPreview ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="block flex-1 break-all rounded bg-slate-100 px-2 py-1 text-xs dark:bg-neutral-950 dark:text-neutral-200">
                {apiKeyPreview}
              </code>
              {d.lastIssuedApiKey ? (
                <button
                  type="button"
                  onClick={() => void copyKey()}
                  className="ap-btn shrink-0 text-xs"
                  aria-label="Copy issued ingest key"
                >
                  {keyCopied ? "Copied" : "Copy key"}
                </button>
              ) : null}
            </div>
          ) : null}
        </li>

        <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
          <p className="text-sm font-semibold text-slate-800 dark:text-neutral-100">3. First ingest</p>
          <p className="mt-1 text-xs text-slate-600 dark:text-neutral-400">
            {onboardingFirstIngestGuidance(subpathUi)}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={refreshingFirstIngest}
              onClick={() => void refreshFirstIngest()}
              className="ap-btn disabled:cursor-not-allowed disabled:opacity-50"
            >
              {refreshingFirstIngest ? "Refreshing…" : "Refresh"}
            </button>
            <span
              aria-label={hasFirstEvent ? "First event received" : "Waiting for first event"}
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                hasFirstEvent
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {hasFirstEvent ? "OK" : "Pending"}
            </span>
          </div>
          {!hasFirstEvent ? (
            <p className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
              {onboardingNoDataPrimaryAction(canIssueKeys, subpathUi)}
            </p>
          ) : null}

          <div className="mt-3">
            <div
              role="group"
              aria-label="Integration framework"
              className="inline-flex overflow-hidden rounded-lg border border-slate-200 text-xs dark:border-neutral-700"
            >
              {(["fastapi", "django"] as const).map((fw) => (
                <button
                  key={fw}
                  type="button"
                  aria-pressed={framework === fw}
                  onClick={() => setFramework(fw)}
                  className={`px-3 py-1 font-medium transition-colors ${
                    framework === fw
                      ? "bg-slate-800 text-white dark:bg-neutral-200 dark:text-neutral-900"
                      : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800"
                  }`}
                >
                  {fw === "fastapi" ? "FastAPI" : "Django"}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void copySnippet()}
              className="ap-btn ml-2 text-xs"
              aria-label="Copy integration snippet"
            >
              {snippetCopied ? "Copied" : "Copy snippet"}
            </button>
          </div>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-relaxed text-emerald-100">
            {snippet}
          </pre>

          <details className="mt-2 text-xs text-slate-600 dark:text-neutral-400">
            <summary className="cursor-pointer select-none font-medium text-slate-700 dark:text-neutral-300">
              Reduce noise later (optional)
            </summary>
            <p className="mt-1">{onboardingNoiseControlHint()}</p>
          </details>
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
                  // The backend rejects completion until at least one event is received.
                  await d.refreshOnboardingStatus();
                  setMessage(
                    "Could not save onboarding completion — Lumonox needs at least one received event first. Send a request, Refresh step 3, then continue.",
                  );
                }
              } catch {
                setMessage("Could not save onboarding completion — network error. Retry shortly.");
              } finally {
                setContinueBusy(false);
              }
            }}
            className="ap-btn-primary w-fit disabled:pointer-events-none disabled:opacity-40"
          >
            {continueBusy ? "Saving…" : "Mark complete and continue"}
          </button>
        </div>
        {!hasFirstEvent ? (
          <p className="text-xs text-slate-500 dark:text-neutral-500">
            Send one request from your app and Refresh step 3 to enable “Mark complete”.
          </p>
        ) : null}
      </div>

      {message ? (
        <p role="status" aria-live="polite" className="text-xs text-slate-600 dark:text-neutral-400">
          {message}
        </p>
      ) : null}
    </ApCard>
  );
}
