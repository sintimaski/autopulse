"use client";

import { ApCard } from "../../ui/ApCard";

/**
 * Operator-facing copy for SDK noise controls (no server-side toggle yet — aligns with DEVELOPMENT.md sampling guidance).
 */
export function SettingsSdkNoiseSection() {
  return (
    <ApCard className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">SDK noise controls</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">
          Reduce health-check traffic and high-volume routes before they hit ingest. Configure in code or environment
          variables on the instrumented app.
        </p>
      </div>
      <ul className="list-inside list-disc space-y-1 text-xs text-slate-600 dark:text-neutral-300">
        <li>
          <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-950">LUMONOX_IGNORE_PATH_PREFIXES</code> —
          comma-separated path prefixes (default in SDK often includes <code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">/health</code>,{" "}
          <code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">/ready</code>).
        </li>
        <li>
          <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-neutral-950">LUMONOX_REQUEST_SAMPLE_RATE</code> —{" "}
          <code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">0.0</code>–<code className="rounded bg-slate-100 px-1 dark:bg-neutral-950">1.0</code>{" "}
          for probabilistic request capture (errors still surface from 5xx paths).
        </li>
      </ul>
      <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-relaxed text-emerald-100">
        {`from lumonox import lumonox

lumonox(
    app,
    request_sample_rate=0.25,
    ignore_path_prefixes=("/health", "/ready", "/metrics"),
)`}
      </pre>
      <p className="text-xs text-slate-500 dark:text-neutral-400">
        See <code className="rounded bg-slate-100 px-1 dark:bg-neutral-800">sdk/README.md</code> and the root README environment tables for the full list.
      </p>
    </ApCard>
  );
}
