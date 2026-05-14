"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { ChevronRight, type LucideIcon } from "lucide-react";
// Direct file import (not the `console` barrel) keeps the hot /dashboard chunk
// from pulling every primitive — see scripts/checkRouteBundleBudgets.mjs.
import { Panel } from "../../ui/console/Panel";

type ChartPanelProps = {
  title: string;
  description?: string;
  /** Leading icon in the panel header. */
  icon?: LucideIcon;
  /** Legacy convenience action — renders a header link. Prefer `actions` for richer controls. */
  actionHref?: string;
  actionLabel?: string;
  /** Arbitrary header controls (tabs, buttons) rendered after the legacy action link. */
  actions?: ReactNode;
  /** Optional footer row (legends, hints). */
  footer?: ReactNode;
  /** Tighter chrome for compact panels. */
  dense?: boolean;
  children: ReactNode;
  className?: string;
  /** Override body padding (defaults to comfortable panel padding). */
  bodyClassName?: string;
};

/**
 * Chart/section panel — wraps the shared console `Panel` chrome so every chart
 * surface shares one title row, action slot and footer treatment.
 */
export function ChartPanel({
  title,
  description,
  icon,
  actionHref,
  actionLabel,
  actions,
  footer,
  dense = false,
  children,
  className,
  bodyClassName,
}: ChartPanelProps) {
  const legacyAction =
    actionHref && actionLabel ? (
      <Link
        href={actionHref}
        className="inline-flex items-center gap-0.5 text-[12px] font-medium text-orange-700 hover:underline dark:text-orange-300"
      >
        {actionLabel}
        <ChevronRight className="size-3.5" aria-hidden />
      </Link>
    ) : null;
  const headerActions =
    legacyAction || actions ? (
      <>
        {legacyAction}
        {actions}
      </>
    ) : undefined;
  return (
    <Panel
      title={title}
      subtitle={description}
      icon={icon}
      actions={headerActions}
      footer={footer}
      dense={dense}
      className={className}
      bodyClassName={bodyClassName ?? "p-3.5"}
    >
      {children}
    </Panel>
  );
}
