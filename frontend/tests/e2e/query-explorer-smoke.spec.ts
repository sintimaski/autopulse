import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("query explorer page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/query-explorer");
  await expect(page).toHaveURL(/\/lumonox\/ui\/query-explorer/);
  await expect(
    page.locator("#main-content").getByRole("heading", { name: "Query Explorer" }),
  ).toBeVisible();
  await expect(page.getByLabel("SQL query for Query Explorer")).toBeVisible();
});
