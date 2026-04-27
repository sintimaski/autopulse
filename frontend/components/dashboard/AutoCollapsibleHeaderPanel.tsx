"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { ChevronDown, ChevronRight, FilterX, SlidersHorizontal } from "../../lib/icons";

type AutoCollapsibleHeaderPanelProps = {
  children: ReactNode;
  enabled?: boolean;
  compactLabel?: string;
  onResetFilters?: () => void;
};

export function AutoCollapsibleHeaderPanel({
  children,
  enabled = true,
  compactLabel = "Server scope",
  onResetFilters,
}: AutoCollapsibleHeaderPanelProps) {
  const expandedRef = useRef<HTMLDivElement>(null);
  const compactRef = useRef<HTMLDivElement>(null);
  const thresholdRef = useRef(0);
  const [showCompact, setShowCompact] = useState(false);
  const [compactOpen, setCompactOpen] = useState(false);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      return;
    }

    const updateThresholdFromDOM = () => {
      const expandedHeight = expandedRef.current?.offsetHeight ?? 0;
      const compactHeight = compactRef.current?.offsetHeight ?? 0;
      thresholdRef.current = Math.max(0, expandedHeight - compactHeight);
    };

    const applyScrollToCompact = () => {
      const reached = window.scrollY > thresholdRef.current;
      setShowCompact((prev) => (prev === reached ? prev : reached));
      if (!reached) {
        setCompactOpen(false);
      }
    };

    const runSync = () => {
      updateThresholdFromDOM();
      applyScrollToCompact();
    };

    runSync();

    const onScroll = () => applyScrollToCompact();
    const onResize = () => runSync();

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);

    const expandedEl = expandedRef.current;
    const compactEl = compactRef.current;
    const resizeObserver =
      typeof ResizeObserver !== "undefined" && expandedEl
        ? new ResizeObserver(() => runSync())
        : null;
    if (resizeObserver && expandedEl) {
      resizeObserver.observe(expandedEl);
      if (compactEl) {
        resizeObserver.observe(compactEl);
      }
    }

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      resizeObserver?.disconnect();
    };
  }, [enabled]);

  return (
    <div className="border-t border-slate-200/80 dark:border-neutral-800">
      <div ref={expandedRef} className="px-4 pb-3 pt-3 sm:px-6">
        {children}
      </div>

      <div
        className={`fixed inset-x-0 top-0 z-40 pl-[var(--dashboard-sidebar-width,14rem)] ${showCompact ? "block" : "hidden"}`}
      >
        <div
          ref={compactRef}
          role="button"
          tabIndex={0}
          onClick={() => setCompactOpen((prev) => !prev)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setCompactOpen((prev) => !prev);
            }
          }}
          onMouseEnter={() => setCompactOpen(true)}
          onMouseLeave={() => setCompactOpen(false)}
          aria-expanded={compactOpen}
          aria-label={compactLabel}
          title={compactLabel}
          className="flex h-20 w-full items-center justify-between border-y border-slate-200/90 bg-white/95 px-4 text-left text-sm font-semibold text-slate-700 backdrop-blur transition-colors hover:bg-white dark:border-neutral-800 dark:bg-neutral-900/95 dark:text-neutral-200 dark:hover:bg-neutral-900 sm:px-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:focus-visible:ring-neutral-500/50"
        >
          <span className="flex items-center gap-2">
            <SlidersHorizontal className="size-5 shrink-0 text-slate-600 dark:text-neutral-300" aria-hidden />
            <span className="sr-only">{compactLabel}</span>
          </span>
          <span className="flex items-center gap-2">
            {onResetFilters ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onResetFilters();
                }}
                title="Reset filters"
                aria-label="Reset filters"
                className="inline-flex shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white p-2 text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700 dark:focus-visible:ring-neutral-500/50"
              >
                <FilterX className="size-4" aria-hidden />
              </button>
            ) : null}
            {compactOpen ? (
              <ChevronDown className="size-5 shrink-0 text-slate-500 dark:text-neutral-400" aria-hidden />
            ) : (
              <ChevronRight className="size-5 shrink-0 text-slate-500 dark:text-neutral-400" aria-hidden />
            )}
          </span>
        </div>
        {compactOpen ? (
          <div
            onMouseEnter={() => setCompactOpen(true)}
            onMouseLeave={() => setCompactOpen(false)}
            className="border-b border-slate-200/90 bg-white/95 px-4 pb-3 pt-2 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/95 sm:px-6"
          >
            {children}
          </div>
        ) : null}
      </div>
    </div>
  );
}
