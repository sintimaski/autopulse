import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Widgets (redirect)",
};

/** Legacy URL — merged into `/widgets-showcase`. */
export default function WidgetsShowroomRedirectPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams ?? {})) {
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, item);
      }
    } else if (typeof value === "string") {
      params.set(key, value);
    }
  }
  const qs = params.toString();
  redirect(qs ? `/widgets-showcase?${qs}` : "/widgets-showcase");
}
