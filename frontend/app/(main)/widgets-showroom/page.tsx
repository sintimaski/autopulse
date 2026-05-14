import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { redirectTargetPreservingParams } from "../../../lib/redirectPreservingParams";

export const metadata: Metadata = {
  title: "Widgets (redirect)",
};

/** Legacy URL — merged into `/w/lx_showcase`. */
export default function WidgetsShowroomRedirectPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  redirect(redirectTargetPreservingParams("/w/lx_showcase", searchParams));
}
