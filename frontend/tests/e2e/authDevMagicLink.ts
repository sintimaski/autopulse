import { expect, type Page } from "@playwright/test";

const dashboardEmail = process.env.E2E_DASHBOARD_EMAIL || "e2e@example.com";

/** Dev-only: request magic link and complete verify flow (requires `DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN`). */
export async function signInViaDevMagicLink(page: Page): Promise<void> {
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
