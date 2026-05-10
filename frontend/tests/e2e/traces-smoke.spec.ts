import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("traces page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/traces");
  await expect(page).toHaveURL(/\/lumonox\/ui\/traces/);
  await expect(page.getByRole("heading", { name: "Full tracing (OTLP)" })).toBeVisible();
});
