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

test("query explorer job failures preset seeds scoped_events starter query", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/query-explorer?preset=job_failures");
  const editor = page.getByLabel("SQL query for Query Explorer");
  await expect(editor).toBeVisible();
  await expect(editor).toContainText("FROM scoped_events");
  await expect(editor).toContainText("type");
});
