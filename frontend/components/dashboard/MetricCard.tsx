"use client";

export function MetricCard({
  label,
  value,
  helper,
  tone = "neutral",
  onClick,
  tooltip,
}: {
  label: string;
  value: string;
  helper?: string;
  tone?: "neutral" | "danger" | "warning";
  onClick?: () => void;
  tooltip?: string;
}) {
  const toneClass =
    tone === "danger"
      ? "text-rose-600 dark:text-rose-300"
      : tone === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : "text-slate-900 dark:text-neutral-100";
  const toneRing =
    tone === "danger"
      ? "ring-rose-500/25 dark:ring-rose-700/40"
      : tone === "warning"
        ? "ring-amber-500/25 dark:ring-amber-700/40"
        : "ring-sky-500/20 dark:ring-sky-800/30";
  return (
    <article
      title={tooltip}
      onClick={onClick}
      className={`rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ${toneRing} dark:border-neutral-700 dark:bg-neutral-900 dark:shadow-md dark:shadow-black/30 ${
        onClick ? "cursor-pointer transition-transform hover:-translate-y-0.5" : ""
      }`}
    >
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">{label}</h3>
      <p className={`mt-1.5 text-[30px] font-bold leading-none tabular-nums ${toneClass}`}>{value}</p>
      {helper ? <p className="mt-1.5 line-clamp-2 text-xs text-slate-500 dark:text-neutral-400">{helper}</p> : null}
    </article>
  );
}
