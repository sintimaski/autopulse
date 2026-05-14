"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Wraps an async handler with a `pending` flag and a concurrent-call guard.
 *
 * A second invocation while one is already in flight is ignored — this blocks
 * duplicate requests from rapid double-clicks even before a `disabled` prop has
 * re-rendered. Pair the returned `pending` flag with the button's `disabled`
 * attribute and its label so the user gets a visible loader too.
 */
export function useAsyncAction<A extends unknown[]>(
  action: (...args: A) => unknown | Promise<unknown>,
): readonly [(...args: A) => Promise<void>, boolean] {
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);

  const run = useCallback(
    async (...args: A) => {
      if (inFlight.current) {
        return;
      }
      inFlight.current = true;
      setPending(true);
      try {
        await action(...args);
      } finally {
        inFlight.current = false;
        setPending(false);
      }
    },
    [action],
  );

  return [run, pending] as const;
}
