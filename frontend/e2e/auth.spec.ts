import { test, expect } from "@playwright/test";

test.describe("Auth", () => {
  test("sign in button visible when not authenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Sign in")).toBeVisible();
  });

  test("no token badge visible when not signed in", async ({ page }) => {
    await page.goto("/");
    const tokenBadge = page.getByText(/\d+ tokens/);
    await expect(tokenBadge).toHaveCount(0);
  });

  test("dashboard not in nav when not signed in", async ({ page }) => {
    await page.goto("/");
    // Dashboard should not appear in navigation
    const navDashboard = page.locator("nav").getByText("Dashboard");
    await expect(navDashboard).toHaveCount(0);
  });
});
