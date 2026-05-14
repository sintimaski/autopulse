"use client";

import type { ReactNode } from "react";

import { cn } from "../../../lib/cn";

/** Keyboard key chip — kept in its own module so header chrome doesn't pull all console controls. */
export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-b-2 border-slate-300 bg-slate-50 px-1 font-mono text-[10px] font-medium text-slate-500 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-400",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
