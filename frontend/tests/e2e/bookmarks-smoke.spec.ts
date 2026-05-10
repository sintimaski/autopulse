import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("bookmarks page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/bookmarks");
  await expect(page).toHaveURL(/\/lumonox\/ui\/bookmarks/);
  await expect(page.getByRole("heading", { name: "Bookmarks" })).toBeVisible();
});
