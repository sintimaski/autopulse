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
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 bg-slate-50 px-4 py-16 text-slate-800 dark:bg-neutral-950 dark:text-neutral-100">
      <div className="max-w-md rounded-2xl border border-rose-200/80 bg-white p-6 shadow-sm dark:border-rose-900/40 dark:bg-neutral-900">
        <h1 className="text-lg font-semibold text-rose-800 dark:text-rose-200">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          The dashboard hit an unexpected error. You can try again, or reload the page. If this keeps
          happening, check the browser console and backend logs.
        </p>
        {error?.message ? (
          <p className="mt-3 rounded-md bg-slate-100 p-2 font-mono text-xs text-slate-700 dark:bg-neutral-800 dark:text-neutral-200">
            {error.message}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
            onClick={() => reset()}
          >
            Try again
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-neutral-600 dark:text-neutral-200 dark:hover:bg-neutral-800"
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
