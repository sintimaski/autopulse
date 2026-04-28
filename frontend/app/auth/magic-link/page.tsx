import { Suspense } from "react";

import { MagicLinkVerifyClient } from "./verify-client";

export default function MagicLinkVerifyPage() {
  // `useSearchParams()` requires a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <MagicLinkVerifyClient />
    </Suspense>
  );
}
