"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useDashboardData } from "./DashboardDataContext";

function storageKey(projectId: string): string {
  return `lx-onboarding-nudge-dismissed:${projectId}`;
}

export function OnboardingCompletionNudge() {
  const pathname = usePathname();
  const d = useDashboardData();
  const [dismissed, setDismissed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const projectId = d.sessionProjectId;
  const status = d.onboardingStatus;
  const hasFirstEvent = useMemo(() => {
    if (status?.first_event_received) {
      return true;
    }
    return (d.requests?.total ?? 0) > 0 || (d.overview?.request_count ?? 0) > 0;
  }, [d.overview?.request_count, d.requests?.total, status?.first_event_received]);

  const completed = Boolean(status?.onboarding_completed);

  useEffect(() => {
    queueMicrotask(() => {
      setHydrated(true);
      if (!projectId) {
        return;
      }
      try {
        if (globalThis.localStorage?.getItem(storageKey(projectId)) === "1") {
          setDismissed(true);
        }
      } catch {
        /* ignore */
      }
    });
  }, [projectId]);

  if (!hydrated || (pathname ?? "").startsWith("/onboarding")) {
    return null;
  }
  if (!projectId || dismissed || completed || hasFirstEvent) {
    return null;
  }

  const dismiss = () => {
    try {
      globalThis.localStorage?.setItem(storageKey(projectId), "1");
    } catch {
      /* ignore */
    }
    setDismissed(true);
  };

  return (
    <div className="rounded-lg border border-orange-200/80 bg-orange-50/90 px-3 py-2 text-sm text-orange-950 ring-1 ring-orange-900/5 dark:border-orange-900/50 dark:bg-orange-950/35 dark:text-orange-100">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">Finish onboarding</p>
          <p className="mt-0.5 text-xs text-orange-900/80 dark:text-orange-100/80">
            Issue a key and send your first event. This hides once events arrive.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/onboarding"
            className="rounded-md bg-orange-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-orange-800"
          >
            Open onboarding
          </Link>
          <button
            type="button"
            onClick={dismiss}
            className="rounded-md border border-orange-300 px-2.5 py-1 text-xs font-medium text-orange-900 hover:bg-orange-100 dark:border-orange-800 dark:text-orange-100 dark:hover:bg-orange-900/40"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
