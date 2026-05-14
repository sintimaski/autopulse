"use client";

import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";
import type { LucideIcon } from "lucide-react";

type PanelProps = {
  /** Panel title shown in the header row. Omit (with no actions) to render a chrome-less surface. */
  title?: ReactNode;
  /** Secondary line under the title. */
  subtitle?: ReactNode;
  /** Leading icon next to the title. */
  icon?: LucideIcon;
  /** Right-aligned header controls (buttons, tabs, badges). */
  actions?: ReactNode;
  /** Optional footer row (legends, hints, counts). */
  footer?: ReactNode;
  /** Tighter header padding for compact panels. */
  dense?: boolean;
  children: ReactNode;
  className?: string;
  /** Applied to the body wrapper — pass padding here (body is unpadded by default). */
  bodyClassName?: string;
};

/**
 * Shared console panel chrome — title row + actions + body + optional footer.
 * Mirrors the Lumonox design bundle's `Panel`; the universal wrapper for charts,
 * tables and forms across the console.
 */
export function Panel({
  title,
  subtitle,
  icon: Icon,
  actions,
  footer,
  dense = false,
  children,
  className,
  bodyClassName,
}: PanelProps) {
  const hasHeader = Boolean(title || actions);
  return (
    <section
      className={cn(
        "flex flex-col overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04]",
        "dark:border-neutral-800 dark:bg-neutral-900 dark:shadow-md dark:shadow-black/30 dark:ring-white/[0.05]",
        className,
      )}
    >
      {hasHeader ? (
        <header
          className={cn(
            "flex items-center gap-2 border-b border-slate-200/80 bg-slate-50/70 dark:border-neutral-800 dark:bg-neutral-950/40",
            dense ? "px-3 py-1.5" : "px-3.5 py-2.5",
          )}
        >
          {Icon ? (
            <Icon className="size-3.5 shrink-0 text-slate-400 dark:text-neutral-500" aria-hidden />
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col">
            {title ? (
              <h3 className="truncate text-[13px] font-semibold tracking-tight text-slate-800 dark:text-neutral-100">
                {title}
              </h3>
            ) : null}
            {subtitle ? (
              <p className="truncate text-[11px] text-slate-400 dark:text-neutral-500">{subtitle}</p>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
        </header>
      ) : null}
      <div className={cn("min-h-0 flex-1", bodyClassName)}>{children}</div>
      {footer ? (
        <footer className="flex items-center justify-between gap-2 border-t border-slate-200/80 bg-slate-50/70 px-3 py-1.5 text-[11px] text-slate-400 dark:border-neutral-800 dark:bg-neutral-950/40 dark:text-neutral-500">
          {footer}
        </footer>
      ) : null}
    </section>
  );
}
