import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--ap-canvas)] px-4 py-10 text-slate-800 dark:text-neutral-100">
      <section className="ap-surface w-full max-w-lg p-8 text-center">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-neutral-400">
          Lumonox
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-neutral-50">
          Page not found
        </h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-neutral-300">
          This route does not exist in the dashboard app. Continue with the overview to diagnose current
          traffic and errors.
        </p>
        <Link href="/dashboard" className="ap-btn-primary mt-5 inline-flex px-4 py-2">
          Go to Dashboard
        </Link>
      </section>
    </main>
  );
}
