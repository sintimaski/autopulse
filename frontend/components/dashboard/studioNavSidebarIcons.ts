import {
  LayoutGrid,
  LayoutTemplate,
  ListChecks,
  Sparkles,
  Stethoscope,
} from "../../lib/icons";
import type { LucideIcon } from "../../lib/icons";

/** Whitelist Lucide icon names from `GET /dashboard/bootstrap` `studio_nav_pages[].icon`. */
const STUDIO_NAV_ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  "layout-grid": LayoutGrid,
  "layout-template": LayoutTemplate,
  stethoscope: Stethoscope,
  "list-checks": ListChecks,
};

export function resolveStudioNavIcon(icon: string): LucideIcon {
  const key = icon.trim().toLowerCase();
  return STUDIO_NAV_ICONS[key] ?? LayoutGrid;
}
