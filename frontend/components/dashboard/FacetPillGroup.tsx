"use client";

import { StatusPill } from "./StatusPill";

export function FacetPillGroup({
  title,
  values,
}: {
  title: string;
  values: string[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
        {title}
      </span>
      {values.length === 0 ? <StatusPill label="All" /> : values.map((value) => <StatusPill key={value} label={value} />)}
    </div>
  );
}
