"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buildApiUrl } from "../../../components/dashboard/dashboardTypes";
import type { DashboardMagicLinkRequestResponse } from "../../../components/dashboard/dashboardTypes";

type RequestState = "idle" | "sending" | "sent" | "signing_in" | "error";

const DEMO_EMAIL = (process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "").trim().toLowerCase() || null;

export function LoginClient() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<RequestState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [ssoMessage, setSsoMessage] = useState<string | null>(null);
  const [ssoLoading, setSsoLoading] = useState(false);

  const requestMagicLink = async (emailOverride?: string) => {
    const trimmed = (emailOverride ?? email).trim();
    if (!trimmed) {
      return;
    }
    setState("sending");
    setMessage(null);
    setDevLink(null);
    try {
      const response = await fetch(buildApiUrl("/dashboard/auth/magic-link/request"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      const raw = await response.text();
      let parsed: unknown = null;
      try {
        parsed = raw ? JSON.parse(raw) : null;
      } catch {
        parsed = null;
      }
      if (!response.ok) {
        const detail =
          parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed
            ? String((parsed as { detail: unknown }).detail)
            : raw.slice(0, 240);
        setState("error");
        setMessage(
          `Request failed (${response.status}). ${detail || "Check the API URL and backend logs."}`,
        );
        return;
      }
      if (!parsed || typeof parsed !== "object" || parsed === null || !("accepted" in parsed)) {
        setState("error");
        setMessage("Unexpected response from server (not JSON). Check the API base URL and backend logs.");
        return;
      }
      const payload = parsed as DashboardMagicLinkRequestResponse;

      // Demo shortcut: when the server exposes dev_token and the email matches the
      // configured demo account, complete verification inline — no email required.
      if (payload.dev_token && DEMO_EMAIL && trimmed.toLowerCase() === DEMO_EMAIL) {
        setState("signing_in");
        try {
          const verifyResponse = await fetch(buildApiUrl("/dashboard/auth/magic-link/verify"), {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: payload.dev_token }),
          });
          if (verifyResponse.ok) {
            router.push("/dashboard");
            router.refresh();
          } else {
            setState("error");
            setMessage("Demo sign-in failed. Please try again.");
          }
        } catch {
          setState("error");
          setMessage("Demo sign-in failed. Please try again.");
        }
        return;
      }

      const showDevHints = process.env.NODE_ENV === "development";
      if (showDevHints && payload.dev_magic_link_url) {
        setDevLink(payload.dev_magic_link_url);
      } else if (showDevHints && payload.dev_token) {
        setDevLink(`Dev token: ${payload.dev_token}`);
      }
      setState("sent");
      setMessage(null);
    } catch (err) {
      const hint =
        err instanceof TypeError
          ? "Network error (wrong API URL, CORS, or server down)."
          : err instanceof Error
            ? err.message
            : String(err);
      setState("error");
      setMessage(`Unable to reach the sign-in API. ${hint}`);
    }
  };

  const oidcLoginUrl = buildApiUrl("/dashboard/auth/oidc/login");

  // OIDC-enabled state is not exposed to the static frontend (the only place
  // it lives — `/dashboard/bootstrap` — requires an authenticated session).
  // So always offer the SSO button, but probe the endpoint first: when OIDC is
  // disabled the backend returns a clean 404 ("OIDC login is disabled"), which
  // we surface as a friendly message instead of navigating to a raw error page.
  const startSso = async () => {
    setSsoLoading(true);
    setSsoMessage(null);
    try {
      const response = await fetch(oidcLoginUrl, {
        method: "GET",
        credentials: "include",
        redirect: "manual",
      });
      // `redirect: "manual"` yields an opaque-redirect response (status 0,
      // type "opaqueredirect") when the endpoint issues its 302 to the IdP.
      if (response.type === "opaqueredirect" || (response.status >= 300 && response.status < 400)) {
        window.location.assign(oidcLoginUrl);
        return;
      }
      if (response.status === 404) {
        setSsoMessage("Single sign-on is not enabled for this deployment. Use the email link above.");
        return;
      }
      let detail = "";
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (body && typeof body.detail === "string") {
          detail = body.detail;
        }
      } catch {
        // No JSON body — fall through to the generic message.
      }
      setSsoMessage(
        detail
          ? `Single sign-on is unavailable: ${detail}`
          : `Single sign-on is unavailable (status ${response.status}).`,
      );
    } catch {
      // Some browsers surface a manual-redirect as a network error rather than
      // an opaque response; fall back to a direct navigation in that case.
      window.location.assign(oidcLoginUrl);
    } finally {
      setSsoLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--ap-canvas)] px-4 py-14 text-slate-800 dark:text-neutral-100">
      <section className="ap-surface w-full max-w-md p-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
          Lumonox
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-neutral-50">
          Sign in to your dashboard
        </h1>

        {state === "signing_in" ? (
          <div className="mt-6 flex items-center gap-3 text-sm text-slate-500 dark:text-neutral-400">
            <div
              className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-orange-400 dark:border-neutral-600 dark:border-t-orange-400 motion-reduce:animate-none"
              aria-hidden="true"
            />
            Signing you into the demo…
          </div>
        ) : state === "sent" ? (
          <div className="mt-4 space-y-4">
            <div
              className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 p-4 text-sm text-emerald-800 dark:text-emerald-100"
              role="status"
              aria-live="polite"
            >
              <p className="font-medium">Check your email</p>
              <p className="mt-1 leading-relaxed">
                If <span className="font-medium">{email.trim()}</span> is allowed for this
                deployment, a sign-in link is on its way. Open it on this device to continue. The
                link expires shortly, so use it soon.
              </p>
            </div>
            {devLink ? (
              <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-100">
                <p className="font-medium">Dev mode</p>
                {devLink.startsWith("Dev token:") ? (
                  <p className="mt-1 break-all font-mono">{devLink}</p>
                ) : (
                  <a
                    className="mt-1 block break-all font-mono underline underline-offset-2"
                    href={devLink}
                  >
                    {devLink}
                  </a>
                )}
              </div>
            ) : null}
            <button
              type="button"
              className="ap-btn w-full px-4 py-2"
              onClick={() => {
                setState("idle");
                setMessage(null);
                setDevLink(null);
              }}
            >
              Use a different email
            </button>
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-neutral-300">
              Enter your email and we will send you a one-time sign-in link. No password required.
            </p>
            <form
              className="mt-5 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void requestMagicLink();
              }}
            >
              <label className="block">
                <span className="sr-only">Email for sign-in link</span>
                <input
                  className="ap-input"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  placeholder="you@example.com"
                  aria-label="Email address"
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <button
                type="submit"
                className="ap-btn-primary w-full px-4 py-2"
                disabled={state === "sending" || !email.trim()}
              >
                {state === "sending" ? "Sending…" : "Send sign-in link"}
              </button>
            </form>
            {message ? (
              <p
                className="mt-4 rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-800 dark:text-rose-100"
                role="alert"
                aria-live="polite"
              >
                {message}
              </p>
            ) : null}
            {DEMO_EMAIL ? (
              <div className="mt-4 border-t border-slate-200/80 pt-4 dark:border-neutral-800">
                <p className="mb-2 text-xs text-slate-500 dark:text-neutral-400">
                  Just exploring? Use the shared demo account — no email required.
                </p>
                <button
                  type="button"
                  className="ap-btn w-full px-4 py-2"
                  disabled={state === "sending"}
                  onClick={() => {
                    setEmail(DEMO_EMAIL);
                    void requestMagicLink(DEMO_EMAIL);
                  }}
                >
                  Try the demo
                </button>
              </div>
            ) : null}
          </>
        )}

        <div className="mt-6 border-t border-slate-200/80 pt-5 dark:border-neutral-800">
          <button
            type="button"
            className="ap-btn w-full px-4 py-2"
            onClick={() => void startSso()}
            disabled={ssoLoading}
          >
            {ssoLoading ? "Connecting…" : "Sign in with SSO"}
          </button>
          {ssoMessage ? (
            <p
              className="mt-3 text-xs leading-relaxed text-slate-500 dark:text-neutral-400"
              role="status"
              aria-live="polite"
            >
              {ssoMessage}
            </p>
          ) : null}
        </div>
      </section>
    </main>
  );
}
