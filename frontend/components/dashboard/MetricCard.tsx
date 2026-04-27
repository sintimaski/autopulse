"use client";

export function MetricCard({
  label,
  value,
  helper,
  tone = "neutral",
}: {
  label: string;
  value: string;
  helper?: string;
  tone?: "neutral" | "danger" | "warning";
}) {
  const toneClass =
    tone === "danger"
      ? "text-rose-600 dark:text-rose-300"
      : tone === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : "text-slate-900 dark:text-neutral-100";
  return (
    <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <h3 className="text-sm font-semibold text-slate-600 dark:text-neutral-300">{label}</h3>
      <p className={`mt-2 text-3xl font-bold tabular-nums ${toneClass}`}>{value}</p>
      {helper ? <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{helper}</p> : null}
    </article>
  );
}
