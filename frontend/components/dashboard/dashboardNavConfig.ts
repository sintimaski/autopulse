import {
  Bell,
  Bookmark,
  ClipboardList,
  History,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
  Stethoscope,
} from "../../lib/icons";
import type { LucideIcon } from "../../lib/icons";

export type DashboardNavItem = { href: string; label: string; Icon: LucideIcon };

export type DashboardNavSection = {
  id: string;
  /** Section label in expanded sidebar; omit for the top diagnosis-first group. */
  heading: string | null;
  items: readonly DashboardNavItem[];
};

/**
 * Console IA: core diagnosis paths first, then workspace tools, then advanced analytics.
 * Keep aligned with the MVP “fast diagnosis” goal in root DEVELOPMENT.md.
 */
export const DASHBOARD_NAV_SECTIONS: readonly DashboardNavSection[] = [
  {
    id: "primary",
    heading: null,
    items: [
      { href: "/dashboard", label: "Overview", Icon: LayoutDashboard },
      { href: "/diagnosis", label: "Errors & Diagnosis", Icon: Stethoscope },
      { href: "/requests", label: "Requests", Icon: ScrollText },
      { href: "/incident", label: "Incident", Icon: ClipboardList },
      { href: "/bookmarks", label: "Bookmarks", Icon: Bookmark },
      { href: "/alerts", label: "Alerts", Icon: Bell },
    ],
  },
  {
    id: "advanced",
    heading: "Advanced",
    items: [
      { href: "/query-explorer", label: "Query Explorer", Icon: ListChecks },
      { href: "/traces", label: "Traces (OTLP)", Icon: History },
    ],
  },
  {
    id: "settings",
    heading: null,
    items: [{ href: "/settings", label: "Settings", Icon: Settings }],
  },
] as const;

export function dashboardNavHrefs(): readonly string[] {
  return DASHBOARD_NAV_SECTIONS.flatMap((section) => section.items.map((item) => item.href));
}
