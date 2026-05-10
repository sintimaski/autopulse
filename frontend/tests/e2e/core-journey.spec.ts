import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("sign-in, overview, and diagnosis load", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/dashboard");
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Errors & Diagnosis" })).toBeVisible();

  await page.goto("/lumonox/ui/diagnosis");
  await expect(page).toHaveURL(/\/lumonox\/ui\/diagnosis/);
  await expect(page.getByRole("link", { name: "Errors & Diagnosis" })).toBeVisible();
});
