import { Suspense } from "react";

import { CardSpinner } from "../../../components/ui/CardSpinner";

import { MagicLinkVerifyClient } from "./verify-client";

export default function MagicLinkVerifyPage() {
  // `useSearchParams()` requires a Suspense boundary in the App Router.
  return (
    <Suspense
      fallback={
        <div className="dark flex min-h-screen items-center justify-center bg-slate-950 px-4 py-14">
          <CardSpinner label="Preparing sign-in…" size="compact" className="max-w-md" />
        </div>
      }
    >
      <MagicLinkVerifyClient />
    </Suspense>
  );
}
