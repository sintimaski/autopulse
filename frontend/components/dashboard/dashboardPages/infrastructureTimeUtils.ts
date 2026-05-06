/** Prefer UTC for zone-less API timestamps so comparisons match bucket/point ranges. */
export function parseDashboardInstantMs(raw: string): number {
  const t = raw.trim();
  if (!t) return Number.NaN;
  if (/z$|[+-]\d{2}:?\d{2}$/i.test(t)) {
    return Date.parse(t);
  }
  return Date.parse(`${t}Z`);
}

export function timestampsCrossCalendarDay(firstMs: number, lastMs: number): boolean {
  const a = new Date(firstMs);
  const b = new Date(lastMs);
  return (
    a.getFullYear() !== b.getFullYear() ||
    a.getMonth() !== b.getMonth() ||
    a.getDate() !== b.getDate()
  );
}

/** X-axis category labels for host resources (and status fallback) — span-aware so dense samples are not all "HH:MM". */
export function formatHostChartAxisLabelSingle(
  ms: number,
  spanMs: number,
  crossesCalendarDay: boolean,
): string {
  const d = new Date(ms);
  if (spanMs >= 1000 * 60 * 60 * 48 || crossesCalendarDay) {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (spanMs >= 1000 * 60 * 60 * 24) {
    return d.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  }
  if (spanMs >= 1000 * 60 * 60) {
    return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function buildHostChartAxisLabels(timestamps: string[]): string[] {
  if (!timestamps.length) {
    return [];
  }
  const msList = timestamps.map((t) => parseDashboardInstantMs(t));
  const finite = msList.filter((n): n is number => Number.isFinite(n));
  const sorted = [...finite].sort((a, b) => a - b);
  const spanMs = sorted.length >= 2 ? Math.max(0, sorted[sorted.length - 1]! - sorted[0]!) : 0;
  const crossesDay =
    sorted.length >= 2 ? timestampsCrossCalendarDay(sorted[0]!, sorted[sorted.length - 1]!) : false;

  const out: string[] = [];
  let prev = "";
  for (let i = 0; i < timestamps.length; i++) {
    const n = msList[i];
    if (!Number.isFinite(n)) {
      const raw = timestamps[i]?.trim() || "—";
      out.push(raw);
      prev = raw;
      continue;
    }
    let lab = formatHostChartAxisLabelSingle(n, spanMs, crossesDay);
    if (lab === prev) {
      lab = new Date(n).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }
    if (lab === prev) {
      lab = new Date(n).toISOString().replace("T", " ").slice(0, 23);
    }
    out.push(lab);
    prev = lab;
  }
  return out;
}
