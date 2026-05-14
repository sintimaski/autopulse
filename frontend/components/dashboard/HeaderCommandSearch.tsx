"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type LucideIcon, Search } from "lucide-react";
import { Kbd } from "../ui/console/Kbd";
import { DASHBOARD_NAV_SECTIONS } from "./dashboardNavConfig";
import type { DashboardStudioNavPage } from "./dashboardTypes";
import { resolveStudioNavIcon } from "./studioNavSidebarIcons";

type CommandEntry = { href: string; label: string; group: string; Icon: LucideIcon };

/**
 * Header "Jump to anything" command search — filters console + studio routes
 * and navigates on select. Opens with the search field or the ⌘K / Ctrl+K shortcut.
 */
export function HeaderCommandSearch({
  studioNavPages = [],
}: {
  studioNavPages?: readonly DashboardStudioNavPage[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const entries = useMemo<CommandEntry[]>(() => {
    const navEntries = DASHBOARD_NAV_SECTIONS.flatMap((section) =>
      section.items.map((item) => ({
        href: item.href,
        label: item.label,
        group: section.heading ?? "Console",
        Icon: item.Icon,
      })),
    );
    const studioEntries = studioNavPages.map((page) => ({
      href: page.pathname,
      label: page.sidebar_label,
      group: page.nav_section_heading?.trim() || "Studio",
      Icon: resolveStudioNavIcon(page.icon),
    }));
    return [...navEntries, ...studioEntries];
  }, [studioNavPages]);

  const results = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) {
      return entries;
    }
    return entries.filter(
      (entry) =>
        entry.label.toLowerCase().includes(trimmed) || entry.href.toLowerCase().includes(trimmed),
    );
  }, [entries, query]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const navigate = useCallback(
    (href: string) => {
      setOpen(false);
      setQuery("");
      router.push(href);
    },
    [router],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const picked = results[activeIndex];
      if (picked) {
        event.preventDefault();
        navigate(picked.href);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-[20rem]">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400 dark:text-neutral-500"
        aria-hidden
      />
      <input
        ref={inputRef}
        type="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setActiveIndex(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Jump to anything…"
        aria-label="Jump to a console page"
        aria-expanded={open}
        role="combobox"
        aria-controls="header-command-results"
        className="h-8 w-full rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-12 text-[13px] text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-orange-400 focus:bg-white focus:ring-2 focus:ring-orange-500/20 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-200 dark:placeholder:text-neutral-500 dark:focus:bg-neutral-900"
      />
      <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2">
        <Kbd>⌘K</Kbd>
      </span>
      {open ? (
        <div
          id="header-command-results"
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+0.375rem)] z-50 max-h-[60vh] overflow-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          {results.length === 0 ? (
            <p className="px-3 py-4 text-center text-[12px] text-slate-400 dark:text-neutral-500">
              No pages match “{query}”.
            </p>
          ) : (
            results.map((entry, index) => {
              const Icon = entry.Icon;
              const active = index === activeIndex;
              return (
                <button
                  key={entry.href}
                  type="button"
                  role="option"
                  aria-selected={active}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => navigate(entry.href)}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                    active
                      ? "bg-orange-50 text-orange-900 dark:bg-orange-950/40 dark:text-orange-100"
                      : "text-slate-700 dark:text-neutral-200"
                  }`}
                >
                  <Icon className="size-4 shrink-0 text-slate-400 dark:text-neutral-500" aria-hidden />
                  <span className="flex-1 truncate">{entry.label}</span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-slate-400 dark:text-neutral-500">
                    {entry.group}
                  </span>
                </button>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}
