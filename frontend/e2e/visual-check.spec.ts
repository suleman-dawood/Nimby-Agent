import { test, expect } from "@playwright/test";

const DESKTOP = { width: 1280, height: 800 };
const MOBILE = { width: 390, height: 844 };

test.describe("Visual Check — Desktop", () => {
  test.use({ viewport: DESKTOP });

  test("home page", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/desktop-home.png", fullPage: true });
    await expect(page.getByText("Nimby Agent", { exact: true })).toBeVisible();
  });

  test("results page with data", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.8688, lng: 151.2093, address: "Sydney NSW",
        lga: "City of Sydney",
        results: [
          { pp_number: "PP-2023-2828", title: "Kurnell Rezoning Proposal", council: "Sutherland Shire",
            distance_km: 25, exhibition_start: "2025-01-01", exhibition_end: "2026-12-31",
            stage: "Under Exhibition", geo_source: "address", description: "Test",
            latitude: -34.0, longitude: 151.2 },
          { pp_number: "PP-2025-622", title: "20 Smidmore Street Marrickville", council: "Inner West",
            distance_km: 5, exhibition_start: "2025-06-01", exhibition_end: "2026-06-30",
            stage: "Post-Exhibition", geo_source: "address", description: "Test",
            latitude: -33.81, longitude: 151.15 },
        ],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/desktop-results.png", fullPage: true });
    await expect(page.getByText("Sydney NSW")).toBeVisible();
    await expect(page.getByText("PP-2023-2828")).toBeVisible();
  });

  test("brief page with tabs", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.screenshot({ path: "screenshots/desktop-brief.png", fullPage: true });

    // Check tabs exist
    await expect(page.getByRole("tab", { name: "Brief" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Site Context" })).toBeVisible();
  });

  test("site context tab", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByRole("tab", { name: "Site Context" }).click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "screenshots/desktop-site-context.png", fullPage: true });
  });

  test("chat panel", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByText("Ask questions").click();
    await expect(page.getByPlaceholder("Ask about this proposal")).toBeVisible();
    await page.screenshot({ path: "screenshots/desktop-chat.png", fullPage: true });
  });

  test("about page", async ({ page }) => {
    await page.goto("/about");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: "screenshots/desktop-about.png", fullPage: true });
  });
});

test.describe("Visual Check — Mobile", () => {
  test.use({ viewport: MOBILE });

  test("home page mobile", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/mobile-home.png", fullPage: true });
    await expect(page.getByText("Nimby Agent", { exact: true })).toBeVisible();
  });

  test("results page mobile", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.8688, lng: 151.2093, address: "Sydney NSW",
        lga: "City of Sydney",
        results: [
          { pp_number: "PP-2023-2828", title: "Kurnell Rezoning", council: "Sutherland",
            distance_km: 25, exhibition_start: "2025-01-01", exhibition_end: "2026-12-31",
            stage: "Under Exhibition", geo_source: "address", description: "Test",
            latitude: -34.0, longitude: 151.2 },
        ],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/mobile-results.png", fullPage: true });
  });

  test("brief page mobile", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.screenshot({ path: "screenshots/mobile-brief.png", fullPage: true });
  });

  test("chat panel mobile", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByText("Ask questions").click();
    await expect(page.getByPlaceholder("Ask about this proposal")).toBeVisible();
    await page.screenshot({ path: "screenshots/mobile-chat.png", fullPage: true });
  });
});
