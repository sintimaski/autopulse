import type { ReactNode } from "react";

type DashboardScopeFacetShellProps = {
  children: ReactNode;
  /** Extra classes on the inner fill (padding, etc.) */
  innerClassName?: string;
  /** Extra classes on the outer rim wrapper (e.g. `sticky top-0 z-30`). */
  className?: string;
};

/** Thin orange→purple rim; tweak colors via `--ap-scope-*` in `app/globals.css`. */
export function DashboardScopeFacetShell({ children, innerClassName, className }: DashboardScopeFacetShellProps) {
  const inner = innerClassName?.trim() ?? "";
  const outer = ["ap-scope-facet-shell", className?.trim() ?? ""].filter(Boolean).join(" ");
  return (
    <div className={outer}>
      <div className={inner ? `ap-scope-facet-shell__inner ${inner}` : "ap-scope-facet-shell__inner"}>{children}</div>
    </div>
  );
}
