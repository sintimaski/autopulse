"use client";

/**
 * Inline loading indicator when a slice has no data yet (initial fetch or empty scope).
 */
export function InlineDataSpinner({
  label = "Loading…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 rounded-xl border border-slate-200/90 bg-slate-50/80 px-6 py-10 text-slate-600 dark:border-neutral-700 dark:bg-neutral-900/60 dark:text-neutral-300 ${className}`}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div
        className="h-8 w-8 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600 motion-reduce:animate-none motion-reduce:border-t-transparent dark:border-neutral-600 dark:border-t-sky-400"
        aria-hidden
      />
      <p className="text-center text-sm font-medium">{label}</p>
    </div>
  );
}
