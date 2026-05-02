import type { ReactNode } from "react";

type DashboardScopeFacetShellProps = {
  children: ReactNode;
  /** Extra classes on the inner fill (padding, etc.) */
  innerClassName?: string;
};

/** Thin orange→purple rim; tweak colors via `--ap-scope-*` in `app/globals.css`. */
export function DashboardScopeFacetShell({ children, innerClassName }: DashboardScopeFacetShellProps) {
  const inner = innerClassName?.trim() ?? "";
  return (
    <div className="ap-scope-facet-shell">
      <div className={inner ? `ap-scope-facet-shell__inner ${inner}` : "ap-scope-facet-shell__inner"}>{children}</div>
    </div>
  );
}
