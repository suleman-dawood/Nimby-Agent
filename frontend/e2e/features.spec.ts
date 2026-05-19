import { test, expect } from "@playwright/test";

test.describe("Brief Page Features", () => {
  const testPP = "PP-2025-2427";

  test("has Download PDF button", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("Download PDF")).toBeVisible();
  });

  test("has Share link button", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("Share link")).toBeVisible();
  });

  test("has Back to results button", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("Back to results")).toBeVisible();
  });
});

test.describe("Results Page Features", () => {
  test("shows compare button on PP cards", async ({ page }) => {
    // Set search data in sessionStorage
    await page.goto("/");
    await page.evaluate(() => {
      sessionStorage.setItem("nimby_search", JSON.stringify({
        lat: -33.8688, lng: 151.2093, address: "Sydney NSW",
        results: [
          { pp_number: "PP-2025-2427", title: "Test 1", stage: "Under Exhibition", distance_km: 5, council: "Test", geo_source: "geocoded" },
          { pp_number: "PP-2024-4996", title: "Test 2", stage: "Under Exhibition", distance_km: 8, council: "Test", geo_source: "geocoded" },
        ],
        policy_results: [], lga: "Sydney",
      }));
    });
    await page.goto("/results");
    await expect(page.getByText("Compare").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Timeline API", () => {
  // These endpoints are on polish-and-features branch, not yet on Railway master
  test.skip();
  test("returns timeline for valid PP", async ({ request }) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api-service-production-6a0d.up.railway.app";
    const res = await request.get(`${apiBase}/api/briefs/PP-2025-2427/timeline`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.pp_number).toBe("PP-2025-2427");
    expect(data.events.length).toBeGreaterThan(0);
    // Should have at least a scraped event
    const types = data.events.map((e: { event_type: string }) => e.event_type);
    expect(types).toContain("scraped");
  });
});

test.describe("PDF Export API", () => {
  // These endpoints are on polish-and-features branch, not yet on Railway master
  test.skip();
  test("returns PDF for valid PP", async ({ request }) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api-service-production-6a0d.up.railway.app";
    const res = await request.get(`${apiBase}/api/briefs/PP-2025-2427/export-pdf`);
    expect(res.ok()).toBeTruthy();
    expect(res.headers()["content-type"]).toContain("application/pdf");
  });
});

test.describe("Worker Status API", () => {
  test("returns system stats", async ({ request }) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api-service-production-6a0d.up.railway.app";
    const res = await request.get(`${apiBase}/api/admin/worker-status`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.total_pps).toBeGreaterThan(200);
    expect(data.total_briefs).toBeGreaterThan(100);
    expect(data.geocoded).toBeGreaterThan(200);
    expect(data.stages).toBeDefined();
  });
});
