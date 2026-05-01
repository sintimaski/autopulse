/**
 * Shared dashboard “raised card” surfaces: darker cool gray with a slight sky tint (light),
 * deep slate with the same hint (dark).
 */
export const dashboardCardFill =
  "border border-slate-300/70 bg-gradient-to-br from-slate-200/95 via-slate-300/75 to-sky-300/30 dark:border-slate-700/80 dark:bg-gradient-to-br dark:from-slate-900 dark:via-slate-800 dark:to-sky-950/30";

export const dashboardPanelP5 = `rounded-2xl ${dashboardCardFill} p-5 shadow-sm ring-1 ring-slate-900/[0.05] dark:ring-white/[0.05]`;

export const dashboardPanelCompact = `rounded-2xl ${dashboardCardFill} px-3 py-2.5 shadow-sm ring-1 ring-slate-900/[0.05] dark:ring-white/[0.05]`;
