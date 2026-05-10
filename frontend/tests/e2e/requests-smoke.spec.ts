import { expect, test } from "@playwright/test";

import { signInViaDevMagicLink } from "./authDevMagicLink";

test("requests page loads after sign-in", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/requests");
  await expect(page).toHaveURL(/\/lumonox\/ui\/requests/);
  const heading = page
    .getByRole("heading", { name: "Request evidence flow" })
    .or(page.getByRole("heading", { name: "No request data for this view" }));
  await expect(heading).toBeVisible();
});
