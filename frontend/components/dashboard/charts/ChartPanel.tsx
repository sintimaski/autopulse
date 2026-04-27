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
      className={`rounded-2xl border border-slate-200/80 bg-white/95 p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 ${
        className ?? ""
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-800 dark:text-neutral-100">{title}</h2>
        {actionHref && actionLabel ? (
          <Link
            href={actionHref}
            className="text-sm font-medium text-sky-700 underline-offset-2 hover:underline dark:text-neutral-300"
          >
            {actionLabel}
          </Link>
        ) : null}
      </div>
      {description ? <p className="mt-1 text-sm text-slate-500 dark:text-neutral-400">{description}</p> : null}
      <div className={description ? "mt-3" : "mt-2"}>{children}</div>
    </article>
  );
}
