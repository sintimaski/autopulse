"use client";

import { useEffect, useState } from "react";

import {
  Activity,
  Bell,
  Boxes,
  Clock,
  Database,
  Filter,
  Gauge,
  KeyRound,
  type LucideIcon,
  Palette,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Panel } from "../../ui/console";

export type SettingsTabId = "project" | "operator";

export type SettingsNavItem = { id: string; label: string; icon: LucideIcon };

/**
 * Section nav items per Settings tab. Order matches the section render order
 * in `SettingsContent` for each tab.
 */
export const SETTINGS_NAV_BY_TAB: Record<SettingsTabId, readonly SettingsNavItem[]> = {
  project: [
    { id: "active-project", label: "Active project", icon: Boxes },
    { id: "api-keys", label: "Ingest API keys", icon: KeyRound },
    { id: "alert-delivery", label: "Alert delivery", icon: Bell },
    { id: "retention", label: "Retention", icon: Clock },
    { id: "sdk", label: "SDK noise", icon: Filter },
    { id: "exclude-traffic", label: "Exclude traffic", icon: ShieldCheck },
    { id: "members", label: "Members & roles", icon: Users },
    { id: "appearance", label: "Appearance", icon: Palette },
  ],
  operator: [
    { id: "event-plane", label: "Event plane", icon: Database },
    { id: "system-diagnostics", label: "System diagnostics", icon: Gauge },
    { id: "internal-metrics", label: "Internal metrics", icon: Activity },
  ],
} as const;

export function settingsSectionAnchorId(id: string): string {
  return `settings-nav-${id}`;
}

/**
 * Sticky section navigation for the Settings page — scrolls to each section
 * in the active tab and tracks the section currently in view.
 */
export function SettingsSectionNav({ activeTab }: { activeTab: SettingsTabId }) {
  const navItems = SETTINGS_NAV_BY_TAB[activeTab];
  const [active, setActive] = useState<string>(navItems[0]?.id ?? "");

  // The tab can switch out from under a stale `active` id; fall back to the
  // first section of the current tab until the observer picks the live one.
  const activeItem = navItems.some((item) => item.id === active)
    ? active
    : (navItems[0]?.id ?? "");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible?.target.id) {
          const match = navItems.find(
            (item) => settingsSectionAnchorId(item.id) === visible.target.id,
          );
          if (match) {
            setActive(match.id);
          }
        }
      },
      { rootMargin: "-96px 0px -55% 0px", threshold: 0 },
    );
    for (const item of navItems) {
      const element = document.getElementById(settingsSectionAnchorId(item.id));
      if (element) {
        observer.observe(element);
      }
    }
    return () => observer.disconnect();
  }, [navItems]);

  // Selecting a nav item must update `aria-current` immediately — the
  // IntersectionObserver may be unavailable, or may not have observed the
  // target yet, so we can't rely on it as the only source of the active id.
  const selectSection = (id: string) => setActive(id);

  return (
    <Panel icon={Settings} title="Settings" dense className="lg:sticky lg:top-4">
      <nav aria-label="Settings sections" className="flex flex-col gap-0.5 p-1.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.id === activeItem;
          return (
            <a
              key={item.id}
              href={`#${settingsSectionAnchorId(item.id)}`}
              onClick={() => selectSection(item.id)}
              aria-current={isActive ? "true" : undefined}
              className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-[12px] transition-colors ${
                isActive
                  ? "bg-orange-50 font-medium text-orange-800 dark:bg-orange-950/40 dark:text-orange-200"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-neutral-400 dark:hover:bg-neutral-800/60 dark:hover:text-neutral-100"
              }`}
            >
              <Icon className="size-3.5 shrink-0" aria-hidden />
              {item.label}
            </a>
          );
        })}
      </nav>
    </Panel>
  );
}
