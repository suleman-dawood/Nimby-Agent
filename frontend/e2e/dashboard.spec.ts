import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("redirects to home when not authenticated", async ({ page }) => {
    await page.goto("/dashboard");
    // Should redirect to home page
    await page.waitForURL("/", { timeout: 5000 });
    expect(page.url()).toContain("/");
  });
});
