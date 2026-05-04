import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

/**
 * Default dashboard section surface — uses `.ap-surface` tokens from `app/globals.css`.
 */
export function ApCard({
  children,
  className,
  padding = "md",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  /** Padding variant */
  padding?: "none" | "sm" | "md" | "lg";
} & React.HTMLAttributes<HTMLDivElement>) {
  const pad =
    padding === "none"
      ? ""
      : padding === "sm"
        ? "p-3 sm:p-4"
        : padding === "lg"
          ? "p-6 sm:p-8"
          : "p-5";
  return (
    <section
      className={cn("ap-surface", pad, className)}
      {...rest}
    >
      {children}
    </section>
  );
}
