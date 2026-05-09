import { expect, test, type Page } from "@playwright/test";

const dashboardEmail = process.env.E2E_DASHBOARD_EMAIL || "e2e@example.com";

async function signInViaDevMagicLink(page: Page) {
  const response = await page.request.post("/dashboard/auth/magic-link/request", {
    data: { email: dashboardEmail },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { dev_token?: string };
  const token = String(payload.dev_token || "").trim();
  expect(token.length).toBeGreaterThan(0);
  await page.goto(`/lumonox/ui/auth/magic-link?token=${encodeURIComponent(token)}`);
  await page.waitForURL(/\/lumonox\/ui\/(dashboard|onboarding)/, { timeout: 15_000 });
}

test("sign-in, overview, and diagnosis load", async ({ page }) => {
  await page.goto("/lumonox/ui/dashboard");
  await signInViaDevMagicLink(page);

  await page.goto("/lumonox/ui/dashboard");
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Errors & Diagnosis" })).toBeVisible();

  await page.goto("/lumonox/ui/diagnosis");
  await expect(page).toHaveURL(/\/lumonox\/ui\/diagnosis/);
  await expect(page.getByRole("link", { name: "Errors & Diagnosis" })).toBeVisible();
});
