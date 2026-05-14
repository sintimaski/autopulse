"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../../../lib/cn";
import { type LucideIcon, X } from "lucide-react";
import type { ConsoleTone } from "./badges";

/* ---------------- Tabs ---------------- */

export type ConsoleTab = {
  value: string;
  label: string;
  icon?: LucideIcon;
  count?: number;
};

export function Tabs({
  tabs,
  active,
  onChange,
  variant = "pill",
  className,
}: {
  tabs: ConsoleTab[];
  active: string;
  onChange: (value: string) => void;
  variant?: "pill" | "underline";
  className?: string;
}) {
  if (variant === "underline") {
    return (
      <div
        role="tablist"
        className={cn("flex items-center gap-4 border-b border-slate-200/80 dark:border-neutral-800", className)}
      >
        {tabs.map((tab) => {
          const selected = tab.value === active;
          const Icon = tab.icon;
          return (
            <button
              key={tab.value}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(tab.value)}
              className={cn(
                "-mb-px flex items-center gap-1.5 border-b-2 px-1 py-2 text-[13px] transition-colors",
                selected
                  ? "border-orange-500 font-semibold text-slate-900 dark:text-neutral-100"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-800 dark:text-neutral-400 dark:hover:text-neutral-200",
              )}
            >
              {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
              {tab.label}
              {tab.count != null ? (
                <span className="text-[11px] font-normal text-slate-400 dark:text-neutral-500">{tab.count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg bg-slate-100 p-0.5 dark:bg-neutral-800/80",
        className,
      )}
    >
      {tabs.map((tab) => {
        const selected = tab.value === active;
        const Icon = tab.icon;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors",
              selected
                ? "bg-white text-slate-900 shadow-sm dark:bg-neutral-950 dark:text-neutral-100"
                : "text-slate-500 hover:text-slate-800 dark:text-neutral-400 dark:hover:text-neutral-200",
            )}
          >
            {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
            {tab.label}
            {tab.count != null ? (
              <span className={cn("text-[11px]", selected ? "text-slate-400 dark:text-neutral-500" : "text-slate-400 dark:text-neutral-500")}>
                {tab.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/* ---------------- Toggle ---------------- */

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-2.5",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40",
          checked
            ? "border-orange-500 bg-orange-500"
            : "border-slate-300 bg-slate-200 dark:border-neutral-600 dark:bg-neutral-700",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-3.5 rounded-full bg-white shadow-sm transition-[left] dark:bg-neutral-100",
            checked ? "left-[1.125rem]" : "left-0.5",
          )}
        />
      </button>
      {label || description ? (
        <span className="flex flex-col">
          {label ? <span className="text-[13px] text-slate-700 dark:text-neutral-200">{label}</span> : null}
          {description ? (
            <span className="text-[11px] text-slate-400 dark:text-neutral-500">{description}</span>
          ) : null}
        </span>
      ) : null}
    </label>
  );
}

/* ---------------- Chip ---------------- */

const CHIP_TONE: Record<"default" | "accent" | "muted", string> = {
  default: "border-slate-200 bg-white text-slate-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200",
  accent: "border-orange-300/70 bg-orange-50 text-orange-800 dark:border-orange-800/70 dark:bg-orange-950/40 dark:text-orange-200",
  muted: "border-slate-200/70 bg-slate-50 text-slate-500 dark:border-neutral-800 dark:bg-neutral-950/60 dark:text-neutral-400",
};

export function Chip({
  children,
  icon: Icon,
  tone = "default",
  onRemove,
  className,
}: {
  children: ReactNode;
  icon?: LucideIcon;
  tone?: "default" | "accent" | "muted";
  onRemove?: () => void;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px]",
        CHIP_TONE[tone],
        className,
      )}
    >
      {Icon ? <Icon className="size-3 shrink-0" aria-hidden /> : null}
      {children}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="-mr-0.5 inline-flex text-current/70 hover:text-current"
        >
          <X className="size-3" aria-hidden />
        </button>
      ) : null}
    </span>
  );
}

/* ---------------- Kbd (re-exported from its own module for hot-path imports) ---------------- */

export { Kbd } from "./Kbd";

/* ---------------- Banner ---------------- */

const BANNER_TONE: Record<ConsoleTone | "success", { wrap: string; fg: string }> = {
  info: { wrap: "border-sky-500/30 bg-sky-500/8", fg: "text-sky-600 dark:text-sky-300" },
  warning: { wrap: "border-amber-500/35 bg-amber-500/10", fg: "text-amber-600 dark:text-amber-300" },
  danger: { wrap: "border-rose-500/35 bg-rose-500/10", fg: "text-rose-600 dark:text-rose-300" },
  healthy: { wrap: "border-emerald-500/30 bg-emerald-500/8", fg: "text-emerald-600 dark:text-emerald-300" },
  success: { wrap: "border-emerald-500/30 bg-emerald-500/8", fg: "text-emerald-600 dark:text-emerald-300" },
  accent: { wrap: "border-orange-500/30 bg-orange-500/8", fg: "text-orange-600 dark:text-orange-300" },
  neutral: { wrap: "border-slate-300/60 bg-slate-500/5", fg: "text-slate-500 dark:text-neutral-400" },
};

export function Banner({
  tone = "info",
  icon: Icon,
  title,
  children,
  action,
  onClose,
  className,
}: {
  tone?: ConsoleTone | "success";
  icon?: LucideIcon;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  onClose?: () => void;
  className?: string;
}) {
  const style = BANNER_TONE[tone];
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3 py-2 text-[12px]",
        style.wrap,
        className,
      )}
    >
      {Icon ? <Icon className={cn("mt-0.5 size-3.5 shrink-0", style.fg)} aria-hidden /> : null}
      <div className="min-w-0 flex-1">
        {title ? <div className="font-semibold text-slate-800 dark:text-neutral-100">{title}</div> : null}
        {children ? <div className="text-slate-600 dark:text-neutral-300">{children}</div> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss"
          className="shrink-0 text-slate-400 hover:text-slate-600 dark:text-neutral-500 dark:hover:text-neutral-300"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}

/* ---------------- SectionHeader ---------------- */

export function SectionHeader({
  title,
  subtitle,
  icon: Icon,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      {Icon ? <Icon className="size-4 shrink-0 text-slate-400 dark:text-neutral-500" aria-hidden /> : null}
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-semibold tracking-tight text-slate-800 dark:text-neutral-100">{title}</div>
        {subtitle ? (
          <div className="text-[11px] text-slate-400 dark:text-neutral-500">{subtitle}</div>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
    </div>
  );
}

/* ---------------- ConsoleButton ---------------- */

type ConsoleButtonProps = {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "xs" | "sm" | "md";
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  children?: ReactNode;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & { className?: string };

const BTN_VARIANT: Record<NonNullable<ConsoleButtonProps["variant"]>, string> = {
  primary:
    "border-orange-500 bg-orange-500 text-white hover:bg-orange-600 dark:border-orange-500 dark:bg-orange-500 dark:text-orange-50 dark:hover:bg-orange-600",
  secondary:
    "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700",
  ghost:
    "border-transparent bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100",
  danger:
    "border-rose-300 bg-transparent text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-300 dark:hover:bg-rose-950/40",
  outline:
    "border-slate-200 bg-transparent text-slate-700 hover:bg-slate-50 dark:border-neutral-700 dark:text-neutral-100 dark:hover:bg-neutral-800",
};

const BTN_SIZE: Record<NonNullable<ConsoleButtonProps["size"]>, string> = {
  xs: "h-6 gap-1 px-2 text-[11px]",
  sm: "h-7 gap-1.5 px-2.5 text-[12px]",
  md: "h-8 gap-1.5 px-3 text-[13px]",
};

export function ConsoleButton({
  variant = "secondary",
  size = "md",
  icon: Icon,
  iconRight: IconRight,
  children,
  className,
  type = "button",
  ...rest
}: ConsoleButtonProps) {
  const iconSize = size === "md" ? "size-4" : "size-3.5";
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-lg border font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 disabled:cursor-not-allowed disabled:opacity-50",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        className,
      )}
      {...rest}
    >
      {Icon ? <Icon className={iconSize} aria-hidden /> : null}
      {children}
      {IconRight ? <IconRight className={iconSize} aria-hidden /> : null}
    </button>
  );
}
