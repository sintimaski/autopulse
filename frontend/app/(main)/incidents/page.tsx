"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Old sidebar URL: land on Incident and open the saved-incidents picker. */
export default function IncidentsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    const search = typeof window !== "undefined" ? window.location.search : "";
    const params = new URLSearchParams(search);
    params.set("saved_incidents", "1");
    router.replace(`/incident/?${params.toString()}`);
  }, [router]);
  return (
    <div className="p-8 text-center text-sm text-slate-600 dark:text-neutral-400">Opening incident workspace…</div>
  );
}
