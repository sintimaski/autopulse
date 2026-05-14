import { redirect } from "next/navigation";

import { redirectTargetPreservingParams } from "../../../lib/redirectPreservingParams";

/** Legacy URL — studio widgets live under `/w/...`. */
export default function WidgetsPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  redirect(redirectTargetPreservingParams("/w/lx_showcase", searchParams));
}
