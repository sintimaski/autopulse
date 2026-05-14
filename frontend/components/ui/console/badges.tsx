"use client";

import { cn } from "../../../lib/cn";
import {
  Check,
  Info,
  type LucideIcon,
  Minus,
  OctagonAlert,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

export type ConsoleTone = "healthy" | "warning" | "danger" | "info" | "neutral" | "accent";

const TONE_STYLE: Record<ConsoleTone, { pill: string; icon: LucideIcon }> = {
  healthy: {
    pill: "bg-emerald-500/12 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    icon: Check,
  },
  warning: {
    pill: "bg-amber-500/14 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
    icon: TriangleAlert,
  },
  danger: {
    pill: "bg-rose-500/14 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
    icon: OctagonAlert,
  },
  info: {
    pill: "bg-sky-500/14 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
    icon: Info,
  },
  neutral: {
    pill: "bg-slate-500/12 text-slate-600 dark:bg-neutral-500/15 dark:text-neutral-300",
    icon: Minus,
  },
  accent: {
    pill: "bg-orange-500/12 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
    icon: Sparkles,
  },
};

/** Semantic status pill — colour is always paired with an icon (never colour-alone). */
export function StatusPill({
  tone = "neutral",
  icon,
  children,
  className,
}: {
  tone?: ConsoleTone;
  /** Override the default tone icon. */
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}) {
  const style = TONE_STYLE[tone];
  const Icon = icon ?? style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        style.pill,
        className,
      )}
    >
      <Icon className="size-3 shrink-0" aria-hidden />
      {children}
    </span>
  );
}

const METHOD_COLOR: Record<string, string> = {
  GET: "text-sky-600 ring-sky-500/40 dark:text-sky-300",
  POST: "text-emerald-600 ring-emerald-500/40 dark:text-emerald-300",
  PUT: "text-amber-600 ring-amber-500/40 dark:text-amber-300",
  PATCH: "text-violet-600 ring-violet-500/40 dark:text-violet-300",
  DELETE: "text-rose-600 ring-rose-500/40 dark:text-rose-300",
};

/** Monospace HTTP method badge. */
export function MethodBadge({ method, className }: { method: string; className?: string }) {
  const upper = method.toUpperCase();
  const color = METHOD_COLOR[upper] ?? "text-slate-500 ring-slate-400/40 dark:text-neutral-400";
  return (
    <span
      className={cn(
        "inline-flex min-w-[2.75rem] items-center justify-center rounded px-1 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 ring-inset",
        color,
        className,
      )}
    >
      {upper}
    </span>
  );
}

/** HTTP status code chip — colour follows the status class. */
export function StatusCode({ code, className }: { code: number; className?: string }) {
  const color =
    code >= 500
      ? "bg-rose-500/12 text-rose-700 dark:text-rose-300"
      : code >= 400
        ? "bg-amber-500/14 text-amber-800 dark:text-amber-300"
        : code >= 300
          ? "bg-sky-500/14 text-sky-700 dark:text-sky-300"
          : "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold tabular-nums",
        color,
        className,
      )}
    >
      {code}
    </span>
  );
}

const DOT_SHAPE: Record<ConsoleTone, { color: string; shape: string }> = {
  healthy: { color: "bg-emerald-500", shape: "rounded-full" },
  warning: { color: "bg-amber-500", shape: "rotate-45 rounded-[1px]" },
  danger: { color: "bg-rose-500", shape: "rounded-[1px]" },
  info: { color: "bg-sky-500", shape: "rounded-full" },
  neutral: { color: "bg-slate-400 dark:bg-neutral-500", shape: "rounded-full" },
  accent: { color: "bg-orange-500", shape: "rounded-full" },
};

/** Severity indicator — pairs colour with shape so it never relies on colour alone. */
export function SeverityDot({
  tone = "neutral",
  size = 8,
  className,
}: {
  tone?: ConsoleTone;
  size?: number;
  className?: string;
}) {
  const style = DOT_SHAPE[tone];
  return (
    <span
      aria-hidden
      className={cn("inline-block shrink-0", style.color, style.shape, className)}
      style={{ width: size, height: size }}
    />
  );
}
