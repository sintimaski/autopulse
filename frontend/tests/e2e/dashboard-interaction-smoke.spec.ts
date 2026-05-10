import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test.describe("dashboard interaction smoke", () => {
  test("studio widget page renders layout lab widgets", async ({ page }) => {
    await page.goto("/lumonox/ui/dashboard");
    await signInViaDevMagicLink(page);

    await page.goto("/lumonox/ui/w/lx_showcase");
    await expect(page.getByRole("heading", { name: "Widget layout lab", exact: true })).toBeVisible();
    await expect(page.getByText("Ingest throughput (window)", { exact: true })).toBeVisible({
      timeout: 25_000,
    });
  });

  test("diagnosis URL query syncs into sticky scope summary", async ({ page }) => {
    await page.goto("/lumonox/ui/dashboard");
    await signInViaDevMagicLink(page);

    await page.goto("/lumonox/ui/diagnosis?window_minutes=30&path_contains=/checkout");
    await expect(page).toHaveURL(/\/lumonox\/ui\/diagnosis/);

    await expect(page.getByText("Last 30m", { exact: true }).first()).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText(/path \/checkout/).first()).toBeVisible();
  });
});
