import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("widgets showcase loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/widgets-showcase");
  await expect(page).toHaveURL(/\/lumonox\/ui\/widgets-showcase/);
  await expect(page.getByRole("heading", { name: "Widgets", exact: true })).toBeVisible();
});
