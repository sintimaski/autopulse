"use client";

/** Shared ring used by dashboard loading surfaces (charts, cards, session). */
export const dashboardSpinnerRingClassName =
  "shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600 motion-reduce:animate-none motion-reduce:border-t-transparent dark:border-neutral-600 dark:border-t-sky-400";

type CardSpinnerSize = "embed" | "compact" | "section";

/**
 * Card-framed loading state with an explicit spinner (preferred over page-wide or pulse-only placeholders).
 */
export function CardSpinner({
  label = "Loading…",
  description,
  className = "",
  size = "section",
}: {
  label?: string;
  description?: string;
  className?: string;
  size?: CardSpinnerSize;
}) {
  const shell =
    size === "embed"
      ? "rounded-xl border border-slate-200/80 bg-slate-50/60 dark:border-neutral-700 dark:bg-neutral-900/50"
      : size === "compact"
        ? "rounded-xl border border-slate-200/90 bg-white px-4 py-6 text-slate-600 shadow-sm dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300"
        : "rounded-xl border border-slate-200/90 bg-slate-50/80 px-6 py-10 text-slate-600 shadow-sm dark:border-neutral-700 dark:bg-neutral-900/60 dark:text-neutral-300";

  const spinnerClass =
    size === "embed" ? "h-6 w-6" : size === "compact" ? "h-7 w-7" : "h-8 w-8";
  const titleClass =
    size === "embed"
      ? "text-center text-xs font-medium text-slate-600 dark:text-neutral-400"
      : "text-center text-sm font-medium";

  const embedSizing = size === "embed" ? "w-full" : "";

  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 ${shell} ${embedSizing} ${className}`}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className={`${spinnerClass} ${dashboardSpinnerRingClassName}`} aria-hidden />
      <p className={titleClass}>{label}</p>
      {description && size !== "embed" ? (
        <p className="max-w-md text-center text-xs text-slate-500 dark:text-neutral-500">{description}</p>
      ) : null}
    </div>
  );
}
