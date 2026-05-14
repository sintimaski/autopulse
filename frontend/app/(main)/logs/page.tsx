import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { redirectTargetPreservingParams } from "../../../lib/redirectPreservingParams";

export const metadata: Metadata = {
  title: "Logs (redirect)",
};

export default function LogsPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  redirect(redirectTargetPreservingParams("/requests", searchParams));
}
