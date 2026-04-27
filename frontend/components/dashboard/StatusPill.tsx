"use client";

export function StatusPill({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "danger" | "warning" | "success";
}) {
  const classes =
    tone === "danger"
      ? "bg-rose-100 text-rose-700 dark:bg-rose-900/50 dark:text-rose-300"
      : tone === "warning"
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
        : tone === "success"
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
          : "bg-slate-100 text-slate-700 dark:bg-neutral-800 dark:text-neutral-200";
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${classes}`}>{label}</span>;
}
