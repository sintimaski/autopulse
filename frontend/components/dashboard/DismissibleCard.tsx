"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useDashboardData } from "./DashboardDataContext";

/**
 * Wrap any non-critical info / hint card so users can hide it for a project.
 *
 * Dismissal is persisted in ``localStorage`` and scoped per-project so a dismissal on
 * one project does not silence the same hint on another. Hydrates client-side (the
 * default during SSR / first paint is "shown" so the card appears, then it disappears
 * once we've checked storage) — matches the pattern in ``OnboardingCompletionNudge``.
 *
 * Pass a stable ``storageKeyBase`` per hint (e.g. ``"lx-operator-reliability-hint"``).
 */
export function DismissibleCard({
  storageKeyBase,
  children,
  ariaLabel,
}: {
  storageKeyBase: string;
  children: ReactNode;
  /** Optional override for the visible Dismiss button's accessible name. */
  ariaLabel?: string;
}) {
  const d = useDashboardData();
  const projectId = d.sessionProjectId;
  const [dismissed, setDismissed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      setHydrated(true);
      if (!projectId) {
        return;
      }
      try {
        if (globalThis.localStorage?.getItem(`${storageKeyBase}:${projectId}`) === "1") {
          setDismissed(true);
        }
      } catch {
        /* localStorage can throw in private mode — fall through and show the card. */
      }
    });
  }, [projectId, storageKeyBase]);

  if (!hydrated || dismissed || !projectId) {
    return hydrated && dismissed ? null : <>{children}</>;
  }

  const dismiss = () => {
    try {
      globalThis.localStorage?.setItem(`${storageKeyBase}:${projectId}`, "1");
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  return (
    <div className="relative">
      {children}
      <button
        type="button"
        onClick={dismiss}
        aria-label={ariaLabel ?? "Dismiss this hint"}
        className="absolute right-1.5 top-1.5 inline-flex h-5 w-5 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-200/70 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 dark:text-neutral-500 dark:hover:bg-neutral-700/70 dark:hover:text-neutral-100"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="h-3 w-3"
          aria-hidden
        >
          <path d="M4.28 3.22a.75.75 0 0 0-1.06 1.06L6.94 8l-3.72 3.72a.75.75 0 1 0 1.06 1.06L8 9.06l3.72 3.72a.75.75 0 0 0 1.06-1.06L9.06 8l3.72-3.72a.75.75 0 0 0-1.06-1.06L8 6.94 4.28 3.22Z" />
        </svg>
      </button>
    </div>
  );
}
