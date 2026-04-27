"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

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
  const [showCompact, setShowCompact] = useState(false);
  const [compactOpen, setCompactOpen] = useState(false);
  const [thresholdPx, setThresholdPx] = useState(0);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      return;
    }

    const recalculateThreshold = () => {
      const expandedHeight = expandedRef.current?.offsetHeight ?? 0;
      const compactHeight = compactRef.current?.offsetHeight ?? 0;
      setThresholdPx(Math.max(0, expandedHeight - compactHeight));
    };

    recalculateThreshold();
    window.addEventListener("resize", recalculateThreshold);

    const onScroll = () => {
      const reached = window.scrollY > thresholdPx;
      setShowCompact((prev) => (prev === reached ? prev : reached));
      if (!reached) {
        setCompactOpen(false);
      }
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", recalculateThreshold);
    };
  }, [enabled, thresholdPx]);

  return (
    <div className="border-t border-slate-200/80 dark:border-neutral-800">
      <div ref={expandedRef} className="px-4 pb-3 pt-3 sm:px-6">
        {children}
      </div>

      <div className={`fixed inset-x-0 top-0 z-40 pl-56 ${showCompact ? "block" : "hidden"}`}>
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
          className="flex h-20 w-full items-center justify-between border-y border-slate-200/90 bg-white/95 px-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/95 dark:text-neutral-300 sm:px-6"
        >
          <span>{compactLabel}</span>
          <span className="flex items-center gap-3">
            {onResetFilters ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onResetFilters();
                }}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-medium normal-case tracking-normal text-slate-700 hover:bg-slate-100 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
              >
                Reset filters
              </button>
            ) : null}
            <span aria-hidden>{compactOpen ? "▾" : "▸"}</span>
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
