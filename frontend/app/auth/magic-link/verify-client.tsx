"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { buildApiUrl } from "../../../components/dashboard/dashboardTypes";

export function MagicLinkVerifyClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [message, setMessage] = useState("Verifying your magic link…");

  const token = useMemo(() => (searchParams.get("token") ?? "").trim(), [searchParams]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!token) {
        if (!cancelled) {
          setStatus("error");
          setMessage("Missing token. Open the full link from your email.");
        }
        return;
      }
      try {
        const response = await fetch(buildApiUrl("/dashboard/auth/magic-link/verify"), {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!response.ok) {
          throw new Error(`verify failed (${response.status})`);
        }
        await response.json();
        let destination = "/dashboard";
        try {
          const onboardingResponse = await fetch(buildApiUrl("/dashboard/auth/onboarding-status"), {
            credentials: "include",
          });
          if (onboardingResponse.ok) {
            const onboardingPayload = (await onboardingResponse.json()) as {
              first_event_received?: boolean;
              onboarding_completed?: boolean;
            };
            if (onboardingPayload.onboarding_completed !== true) {
              destination = "/onboarding";
            }
          }
        } catch {
          // Keep fallback destination as dashboard.
        }
        if (!cancelled) {
          setStatus("success");
          setMessage("Signed in. Redirecting…");
        }
        setTimeout(() => {
          router.replace(destination);
          router.refresh();
        }, 150);
      } catch {
        if (!cancelled) {
          setStatus("error");
          setMessage("Invalid or expired link. Request a new sign-in email.");
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [router, token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-14 text-slate-100">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-slate-950/60 backdrop-blur">
        <p className="text-sm font-medium uppercase tracking-widest text-slate-400/90">AutoPulse</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Dashboard sign in</h1>
        <p
          className="mt-3 text-sm leading-relaxed text-slate-300"
          role="status"
          aria-live="polite"
        >
          {message}
        </p>
        <div className="mt-5">
          {status === "verifying" ? (
            <div
              className="h-9 w-9 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400 motion-reduce:animate-none motion-reduce:border-t-transparent"
              role="status"
              aria-live="polite"
              aria-label="Verifying magic link"
            />
          ) : status === "success" ? (
            <div
              className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
              role="status"
            >
              Signed in.
            </div>
          ) : (
            <button
              type="button"
              onClick={() => router.replace("/dashboard")}
              className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-slate-950"
            >
              Back to dashboard
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
