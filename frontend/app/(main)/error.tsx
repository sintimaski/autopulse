"use client";

import { useEffect } from "react";

export default function MainError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 bg-[var(--ap-canvas)] px-4 py-16 text-slate-800 dark:text-neutral-100">
      <div className="ap-surface max-w-md border-rose-200/80 p-6 dark:border-rose-900/50">
        <h1 className="text-lg font-semibold text-rose-800 dark:text-rose-200">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          The dashboard hit an unexpected error. Try again or reload the page. If it persists, check the
          browser console and backend logs.
        </p>
        {error?.message ? (
          <p className="mt-3 rounded-lg border border-slate-200/80 bg-slate-50/80 p-2 font-mono text-xs text-slate-700 dark:border-neutral-700 dark:bg-neutral-950/60 dark:text-neutral-200">
            {error.message}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="ap-btn-primary px-4 py-2" onClick={() => reset()}>
            Try again
          </button>
          <button
            type="button"
            className="ap-btn border-neutral-600 bg-transparent px-4 py-2 hover:bg-neutral-800/80 dark:hover:bg-neutral-800/80"
            onClick={() => {
              window.location.reload();
            }}
          >
            Reload page
          </button>
        </div>
      </div>
    </div>
  );
}
