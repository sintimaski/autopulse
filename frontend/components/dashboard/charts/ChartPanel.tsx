"use client";

import Link from "next/link";
import type { ReactNode } from "react";

type ChartPanelProps = {
  title: string;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
  children: ReactNode;
  className?: string;
};

export function ChartPanel({
  title,
  description,
  actionHref,
  actionLabel,
  children,
  className,
}: ChartPanelProps) {
  return (
    <article
      className={`rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.05] dark:border-neutral-700 dark:bg-neutral-900 dark:shadow-md dark:shadow-black/30 dark:ring-white/[0.06] ${
        className ?? ""
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-wide text-slate-800 dark:text-neutral-100">{title}</h2>
        {actionHref && actionLabel ? (
          <Link
            href={actionHref}
            className="text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
          >
            {actionLabel}
          </Link>
        ) : null}
      </div>
      {description ? <p className="mt-1 text-xs text-slate-500 dark:text-neutral-400">{description}</p> : null}
      <div className={description ? "mt-3" : "mt-2"}>{children}</div>
    </article>
  );
}
