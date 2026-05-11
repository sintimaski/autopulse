import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("widgets gallery loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/w/lx_showcase");
  await expect(page).toHaveURL(/\/lumonox\/ui\/w\/lx_showcase/);
  await expect(
    page.locator("#main-content").getByRole("heading", { name: "Widget layout lab", exact: true }),
  ).toBeVisible();
});
