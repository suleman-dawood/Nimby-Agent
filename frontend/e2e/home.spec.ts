import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test("loads with title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Nimby Agent/);
  });

  test("shows header with NSW branding", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Planning Proposals", { exact: true })).toBeVisible();
    await expect(page.getByText("NSW")).toBeVisible();
  });

  test("shows sign in when not authenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Sign in")).toBeVisible();
  });

  test("has navigation links", async ({ page }) => {
    await page.goto("/");
    // Use NavLink labels in sidebar
    await expect(page.locator(".mantine-NavLink-label", { hasText: "Search" })).toBeVisible();
    await expect(page.locator(".mantine-NavLink-label", { hasText: "Results" })).toBeVisible();
    await expect(page.locator(".mantine-NavLink-label", { hasText: "About" })).toBeVisible();
  });

  test("dashboard link hidden when not signed in", async ({ page }) => {
    await page.goto("/");
    const dashboard = page.getByText("Dashboard");
    await expect(dashboard).toHaveCount(0);
  });
});
