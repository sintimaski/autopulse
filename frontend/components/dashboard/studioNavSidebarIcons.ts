import {
  LayoutGrid,
  LayoutTemplate,
  ListChecks,
  Sparkles,
  Stethoscope,
} from "../../lib/icons";
import type { LucideIcon } from "../../lib/icons";

/**
 * Whitelist of Lucide icon names accepted from `GET /dashboard/bootstrap`
 * `studio_nav_pages[].icon`.
 *
 * This whitelist must stay in sync with the icon values the backend can emit
 * (see `backend/.../studio_nav_pages.py`; today it only emits `"sparkles"`).
 * Any backend icon string not listed here falls back to `LayoutGrid` in
 * `resolveStudioNavIcon` — that fallback is intentional, so an unrecognized or
 * newly added backend value renders a neutral icon instead of crashing. When
 * the backend gains a new icon value, add the matching entry here.
 */
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
