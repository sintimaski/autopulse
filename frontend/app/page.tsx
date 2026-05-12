"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { CardSpinner } from "../components/ui/CardSpinner";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => {
    const search = typeof window !== "undefined" ? window.location.search : "";
    router.replace(search ? `/dashboard${search}` : "/dashboard");
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--ap-canvas)] px-4 py-10">
      <CardSpinner label="Opening dashboard…" size="compact" className="max-w-sm" />
    </div>
  );
}
