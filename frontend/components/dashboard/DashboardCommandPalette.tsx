"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DASHBOARD_NAV_SECTIONS } from "./dashboardNavConfig";
import { logicalDashboardLocationHref } from "./dashboardRoutePath";

type PaletteEntry = { href: string; label: string; group: string };

function buildPaletteEntries(): PaletteEntry[] {
  const out: PaletteEntry[] = [];
  for (const section of DASHBOARD_NAV_SECTIONS) {
    const group = section.heading ?? (section.id === "primary" ? "Core" : section.id);
    for (const item of section.items) {
      out.push({ href: item.href, label: item.label, group });
    }
  }
  out.push({ href: "/onboarding", label: "Onboarding", group: "Workspace" });
  return out;
}

export function DashboardCommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const entries = useMemo(() => buildPaletteEntries(), []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return entries;
    }
    return entries.filter(
      (e) =>
        e.label.toLowerCase().includes(q) ||
        e.href.toLowerCase().includes(q) ||
        e.group.toLowerCase().includes(q),
    );
  }, [entries, query]);

  const selectedIndex = Math.min(activeIndex, Math.max(0, filtered.length - 1));

  const navigateTo = useCallback(
    (href: string) => {
      router.push(logicalDashboardLocationHref(href));
      setOpen(false);
      setQuery("");
      setActiveIndex(0);
    },
    [router],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setQuery("");
        setActiveIndex(0);
        setOpen((prev) => !prev);
        return;
      }
      if (!open) {
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setQuery("");
        setActiveIndex(0);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" && filtered.length > 0) {
        e.preventDefault();
        const pick = filtered[selectedIndex];
        if (pick) {
          navigateTo(pick.href);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, navigateTo, open, selectedIndex]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const id = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
    return () => window.cancelAnimationFrame(id);
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center px-3 pt-[12vh] sm:pt-[18vh]">
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/50 backdrop-blur-[1px] dark:bg-black/55"
        aria-label="Close command palette"
        onClick={() => {
          setOpen(false);
          setQuery("");
          setActiveIndex(0);
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Go to page"
        className="relative z-[201] w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-neutral-700 dark:bg-neutral-900"
      >
        <div className="border-b border-slate-200 px-3 py-2 dark:border-neutral-700">
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            placeholder="Jump to page…"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none ring-sky-500/30 focus:ring-2 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <p className="mt-1 text-[11px] text-slate-500 dark:text-neutral-500">
            <kbd className="rounded bg-slate-200/80 px-1 font-mono text-[10px] dark:bg-neutral-800">⌘K</kbd> /{" "}
            <kbd className="rounded bg-slate-200/80 px-1 font-mono text-[10px] dark:bg-neutral-800">Ctrl+K</kbd>{" "}
            toggles · arrows + enter
          </p>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto py-1" role="listbox" aria-label="Pages">
          {filtered.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-slate-500 dark:text-neutral-400">No matches</li>
          ) : (
            filtered.map((item, idx) => {
              const active = idx === selectedIndex;
              return (
                <li key={`${item.href}-${item.label}`} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={`flex w-full flex-col gap-0.5 px-4 py-2.5 text-left text-sm transition-colors ${
                      active
                        ? "bg-sky-600 text-white dark:bg-sky-700"
                        : "text-slate-800 hover:bg-slate-100 dark:text-neutral-100 dark:hover:bg-neutral-800"
                    }`}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => navigateTo(item.href)}
                  >
                    <span className="font-medium">{item.label}</span>
                    <span
                      className={`text-xs ${active ? "text-white/85" : "text-slate-500 dark:text-neutral-400"}`}
                    >
                      {item.group} · {item.href}
                    </span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
