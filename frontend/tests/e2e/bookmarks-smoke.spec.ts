import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("bookmarks page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/bookmarks");
  await expect(page).toHaveURL(/\/lumonox\/ui\/bookmarks/);
  // Scope to #main-content: the AppShell renders its own <h1> page title, so an
  // unscoped "Bookmarks" heading match is ambiguous (strict-mode violation).
  await expect(
    page.locator("#main-content").getByRole("heading", { name: "Bookmarks", exact: true }),
  ).toBeVisible();
});
