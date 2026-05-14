import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { redirectTargetPreservingParams } from "../../../lib/redirectPreservingParams";

export const metadata: Metadata = {
  title: "Widgets (redirect)",
};

export default function WidgetsShowcasePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  redirect(redirectTargetPreservingParams("/w/lx_showcase", searchParams));
}
