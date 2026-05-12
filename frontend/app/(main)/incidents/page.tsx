"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Old sidebar URL: land on Incident and open the saved-incidents picker. */
export default function IncidentsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/incident/?saved_incidents=1");
  }, [router]);
  return (
    <div className="p-8 text-center text-sm text-slate-600 dark:text-neutral-400">Opening incident workspace…</div>
  );
}
