import { test, expect } from "@playwright/test";

test.describe("Results Page", () => {
  test("shows no results message without search data", async ({ page }) => {
    await page.goto("/results");
    await expect(page.getByText("Search for an address first")).toBeVisible();
  });

  test("shows results with stored search data", async ({ page }) => {
    // Inject search data into sessionStorage before navigating
    await page.goto("/");
    await page.evaluate(() => {
      const searchData = {
        lat: -33.8688,
        lng: 151.2093,
        address: "Sydney NSW",
        lga: "City of Sydney",
        results: [
          {
            pp_number: "PP-2023-2828",
            title: "Test Proposal",
            council: "Test Council",
            distance_km: 5.0,
            exhibition_start: "2025-01-01",
            exhibition_end: "2026-12-31",
            stage: "Under Exhibition",
            geo_source: "address",
            description: "Test",
            latitude: -33.87,
            longitude: 151.21,
          },
        ],
        policy_results: [],
      };
      sessionStorage.setItem("nimby_search", JSON.stringify(searchData));
    });

    await page.goto("/results");

    // Should show the address
    await expect(page.getByText("Sydney NSW")).toBeVisible({ timeout: 10000 });
    // Should show PP card
    await expect(page.getByText("PP-2023-2828")).toBeVisible();
    // Should show stage badge
    await expect(page.getByText("Under Exhibition")).toBeVisible();
  });
});
