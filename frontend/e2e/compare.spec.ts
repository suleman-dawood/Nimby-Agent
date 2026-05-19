import { test, expect } from "@playwright/test";

test.describe("Compare Page", () => {
  test("shows instructions when no PPs selected", async ({ page }) => {
    await page.goto("/compare");
    await expect(page.getByText("Compare Proposals")).toBeVisible();
    await expect(page.getByText("Use ?pp1=")).toBeVisible();
  });

  test("loads comparison with two valid PPs", async ({ page }) => {
    await page.goto("/compare?pp1=PP-2025-2427&pp2=PP-2024-4996");
    await expect(page.getByText("Compare Proposals")).toBeVisible({ timeout: 15000 });
    // Should show comparison grid
    await expect(page.getByText("Zoning")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Max Height")).toBeVisible();
    await expect(page.getByText("Bushfire Prone")).toBeVisible();
  });

  test("shows both PP numbers in headers", async ({ page }) => {
    await page.goto("/compare?pp1=PP-2025-2427&pp2=PP-2024-4996");
    await expect(page.getByText("PP-2025-2427 Summary")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("PP-2024-4996 Summary")).toBeVisible();
  });

  test("shows summary cards for both PPs", async ({ page }) => {
    await page.goto("/compare?pp1=PP-2025-2427&pp2=PP-2024-4996");
    await expect(page.getByText("PP-2025-2427 Summary")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("PP-2024-4996 Summary")).toBeVisible();
  });
});
