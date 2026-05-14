export type SortDir = "asc" | "desc" | "none";

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

/** Shorter table cell timestamp (avoids crowding next to service/env). */
export function formatTimestampCompact(value: string): string {
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) {
    return value;
  }
  return d.toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function statusTone(code: number): string {
  if (code >= 500) {
    return "bg-rose-500/15 text-rose-800 ring-rose-500/25 dark:bg-rose-900/40 dark:text-rose-300 dark:ring-rose-700/50";
  }
  if (code >= 400) {
    return "bg-orange-500/12 text-orange-950 ring-orange-500/20 dark:bg-orange-950/45 dark:text-orange-200 dark:ring-orange-500/30";
  }
  return "bg-neutral-200/90 text-neutral-900 ring-neutral-300/70 dark:bg-neutral-800 dark:text-neutral-100 dark:ring-neutral-600/50";
}

export function compareValues(
  a: string | number,
  b: string | number,
  dir: "asc" | "desc",
): number {
  const mul = dir === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") {
    return (a - b) * mul;
  }
  return String(a).localeCompare(String(b), undefined, { sensitivity: "base" }) * mul;
}
