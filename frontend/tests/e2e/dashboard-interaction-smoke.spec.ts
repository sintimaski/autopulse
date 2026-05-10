import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test.describe("dashboard interaction smoke", () => {
  test("Escape closes sample dialog on widgets showcase", async ({ page }) => {
    await page.goto("/lumonox/ui/dashboard");
    await signInViaDevMagicLink(page);

    await page.goto("/lumonox/ui/widgets-showcase");
    await expect(page.getByRole("heading", { name: "Widgets", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Open sample dialog" }).click();
    await expect(page.getByRole("heading", { name: "Sample dialog" })).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("heading", { name: "Sample dialog" })).toHaveCount(0);
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
