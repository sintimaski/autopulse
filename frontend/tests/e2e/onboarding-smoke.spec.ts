import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("onboarding page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/onboarding");
  await expect(page).toHaveURL(/\/lumonox\/ui\/onboarding/);
  await expect(page.getByRole("heading", { name: "Onboarding" })).toBeVisible();
});
