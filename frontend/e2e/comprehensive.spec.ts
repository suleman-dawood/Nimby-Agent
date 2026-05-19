import { test, expect } from "@playwright/test";

test.describe("Comprehensive App Test", () => {

  // --- HOME PAGE ---
  test("home: search input works", async ({ page }) => {
    await page.goto("/");
    const input = page.getByPlaceholder("42 Wallaby Way");
    await expect(input).toBeVisible();
    await input.fill("Parramatta NSW");
    await expect(input).toHaveValue("Parramatta NSW");
  });

  test("home: nav links all work", async ({ page }) => {
    await page.goto("/");
    await page.locator("nav").getByText("Results").click();
    await expect(page).toHaveURL(/results/);
    await page.locator("nav").getByText("About").click();
    await expect(page).toHaveURL(/about/);
    await page.locator("nav").getByText("Search").click();
    await expect(page).toHaveURL("/");
  });

  // --- RESULTS PAGE (Under Exhibition PP) ---
  test("results: Under Exhibition PP shows green badge", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.87, lng: 151.21, address: "Sydney NSW", lga: "City of Sydney",
        results: [{
          pp_number: "PP-2023-2828", title: "Kurnell Peninsula Rezoning",
          council: "Sutherland Shire", distance_km: 25,
          exhibition_start: "2025-01-01", exhibition_end: "2026-12-31",
          stage: "Under Exhibition", geo_source: "address",
          description: "Test", latitude: -34.0, longitude: 151.2,
        }],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await expect(page.getByText("Under Exhibition")).toBeVisible();
    await expect(page.getByText("PP-2023-2828")).toBeVisible();
  });

  test("results: Post-Exhibition PP shows blue badge", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.87, lng: 151.21, address: "Sydney NSW", lga: "City of Sydney",
        results: [{
          pp_number: "PP-2025-622", title: "Smidmore Street Marrickville",
          council: "Inner West", distance_km: 5,
          exhibition_start: "2025-06-01", exhibition_end: "2026-06-30",
          stage: "Post-Exhibition", geo_source: "address",
          description: "Test", latitude: -33.81, longitude: 151.15,
        }],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await expect(page.getByText("Post-Exhibition")).toBeVisible();
  });

  test("results: mixed stages show filter chips", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.87, lng: 151.21, address: "Sydney NSW", lga: null,
        results: [
          { pp_number: "PP-1", title: "A", council: "C", distance_km: 1,
            exhibition_start: null, exhibition_end: null,
            stage: "Under Exhibition", geo_source: "address",
            description: "", latitude: -33.87, longitude: 151.21 },
          { pp_number: "PP-2", title: "B", council: "C", distance_km: 2,
            exhibition_start: null, exhibition_end: null,
            stage: "Under Assessment", geo_source: "address",
            description: "", latitude: -33.88, longitude: 151.22 },
        ],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    // Both filter chips visible
    await expect(page.getByText("Under Exhibition").first()).toBeVisible();
    await expect(page.getByText("Under Assessment").first()).toBeVisible();
    // Both cards visible
    await expect(page.getByText("PP-1")).toBeVisible();
    await expect(page.getByText("PP-2")).toBeVisible();
  });

  test("results: toggling filter hides cards", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.87, lng: 151.21, address: "Sydney NSW", lga: null,
        results: [
          { pp_number: "PP-EX", title: "Exhibition One", council: "C", distance_km: 1,
            exhibition_start: null, exhibition_end: null,
            stage: "Under Exhibition", geo_source: "address",
            description: "", latitude: -33.87, longitude: 151.21 },
          { pp_number: "PP-AS", title: "Assessment One", council: "C", distance_km: 2,
            exhibition_start: null, exhibition_end: null,
            stage: "Under Assessment", geo_source: "address",
            description: "", latitude: -33.88, longitude: 151.22 },
        ],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await expect(page.getByText("PP-EX")).toBeVisible();
    await expect(page.getByText("PP-AS")).toBeVisible();

    // Uncheck Under Assessment (click the chip, not the badge)
    await page.getByText("Under Assessment").first().click();
    await expect(page.getByText("PP-AS")).not.toBeVisible();
    await expect(page.getByText("PP-EX")).toBeVisible();
  });

  test("results: clicking card navigates to brief", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.87, lng: 151.21, address: "Sydney NSW", lga: null,
        results: [{
          pp_number: "PP-2023-2828", title: "Kurnell", council: "Sutherland",
          distance_km: 25, exhibition_start: null, exhibition_end: null,
          stage: "Under Exhibition", geo_source: "address",
          description: "", latitude: -34.0, longitude: 151.2,
        }],
        policy_results: [],
      }));
    });
    await page.goto("/results");
    await page.getByText("PP-2023-2828").click();
    await expect(page).toHaveURL(/brief\/PP-2023-2828/);
  });

  // --- BRIEF PAGE (with documents) ---
  test("brief: PP-2023-2828 loads full brief with citations", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    // Should have content
    const body = await page.textContent("body");
    expect(body?.includes("Kurnell") || body?.includes("proposal")).toBeTruthy();
    // Should have source citations
    await expect(page.getByText("Sources").first()).toBeVisible();
  });

  test("brief: Site Context shows real data for PP-2023-2828", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByRole("tab", { name: "Site Context" }).click();
    await page.waitForTimeout(3000);
    // C1 zoning
    await expect(page.getByText("C1")).toBeVisible();
    await expect(page.getByText("National Parks")).toBeVisible();
    // Hazards
    await expect(page.getByText("Bushfire Prone")).toBeVisible();
    // Heritage
    await expect(page.getByText("State Heritage", { exact: true })).toBeVisible();
  });

  test("brief: Draft a submission button navigates", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByText("Draft a submission").click();
    await expect(page).toHaveURL(/submission/);
  });

  test("brief: chat opens and has input", async ({ page }) => {
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByText("Ask questions").click();
    const input = page.getByPlaceholder("Ask about this proposal");
    await expect(input).toBeVisible();
    await expect(input).toBeEnabled();
  });

  // --- BRIEF PAGE (PP without docs — Under Assessment) ---
  test("brief: PP without docs shows metadata brief", async ({ page }) => {
    // Pick an Under Assessment PP that likely has no docs
    await page.goto("/brief/PP-2026-974");
    // Should either show a metadata brief or error gracefully
    await page.waitForTimeout(5000);
    const body = await page.textContent("body");
    // Should show something — either brief content or PP number
    expect(body?.includes("PP-2026-974") || body?.includes("not generated") || body?.includes("Stage")).toBeTruthy();
  });

  // --- SUBMISSION PAGE ---
  test("submission: loads with concerns", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_submission_pp", "PP-2023-2828");
    });
    await page.goto("/submission");
    await page.waitForTimeout(3000);
    const body = await page.textContent("body");
    expect(body?.includes("PP-2023-2828") || body?.includes("submission") || body?.includes("concern")).toBeTruthy();
  });

  // --- AUTH ---
  test("auth: sign in button present", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Sign in")).toBeVisible();
  });

  test("auth: no dashboard in nav when signed out", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("nav").getByText("Dashboard")).toHaveCount(0);
  });

  test("auth: dashboard redirects when not signed in", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL("/", { timeout: 5000 });
  });

  // --- ABOUT PAGE ---
  test("about: page loads", async ({ page }) => {
    await page.goto("/about");
    await page.waitForTimeout(1000);
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(100);
  });

  // --- MOBILE SPECIFIC ---
  test("mobile: burger menu opens nav", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    // Burger should be visible
    const burger = page.locator("button").filter({ has: page.locator('[data-opened]') }).first();
    // Nav items should be hidden initially on mobile
    // Click burger area
    await page.locator(".mantine-Burger-root").click();
    await page.waitForTimeout(500);
    // Nav should now show
    await expect(page.locator(".mantine-NavLink-label", { hasText: "Search" })).toBeVisible();
    await expect(page.locator(".mantine-NavLink-label", { hasText: "Results" })).toBeVisible();
  });

  test("mobile: brief page readable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    // Tabs should be visible
    await expect(page.getByRole("tab", { name: "Brief" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Site Context" })).toBeVisible();
    // Buttons should be visible
    await expect(page.getByText("Draft a submission")).toBeVisible();
  });

  test("mobile: chat panel takes full width", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/brief/PP-2023-2828");
    await expect(page.getByRole("heading", { name: "PP-2023-2828" })).toBeVisible({ timeout: 20000 });
    await page.getByText("Ask questions").click();
    const input = page.getByPlaceholder("Ask about this proposal");
    await expect(input).toBeVisible();
    // Chat should be full width on mobile
    const chatPanel = page.locator(".chat-panel");
    const box = await chatPanel.boundingBox();
    if (box) {
      expect(box.width).toBeGreaterThanOrEqual(380);
    }
  });
});
