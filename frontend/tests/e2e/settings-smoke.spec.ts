import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("settings page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/settings");
  await expect(page).toHaveURL(/\/lumonox\/ui\/settings/);
  await expect(page.getByRole("heading", { name: "Retention policy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Appearance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "API key lifecycle" })).toBeVisible();

  const lightTheme = page.getByRole("radio", { name: "Light" });
  if (await lightTheme.isEnabled()) {
    await lightTheme.click();
    await expect(
      page.getByText(/Theme saved\.|Failed to save theme\./),
    ).toBeVisible({ timeout: 15_000 });
  }
});
