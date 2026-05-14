import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("alerts page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/alerts");
  await expect(page).toHaveURL(/\/lumonox\/ui\/alerts/);
  await expect(page.getByRole("heading", { name: "Error rate" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Alert rules" })).toBeVisible();
});
