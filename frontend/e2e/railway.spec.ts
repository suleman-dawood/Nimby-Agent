import { test, expect } from "@playwright/test";

const RAILWAY_URL = "https://frontend-service-production-122c.up.railway.app";

test.describe("Railway Frontend", () => {
  test("home page loads without errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto(RAILWAY_URL);
    await page.waitForTimeout(5000);
    await page.screenshot({ path: "screenshots/railway-home.png" });

    const title = await page.title();
    console.log("Title:", title);
    console.log("Errors:", errors);

    expect(title).toContain("Nimby Agent");
    // Allow Google OAuth error but nothing else critical
    const criticalErrors = errors.filter(e => !e.includes("client_id") && !e.includes("google"));
    expect(criticalErrors).toHaveLength(0);
  });

  test("brief page loads on Railway", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto(`${RAILWAY_URL}/brief/PP-2023-2828`);
    await page.waitForTimeout(10000);
    await page.screenshot({ path: "screenshots/railway-brief.png" });

    const body = await page.textContent("body");
    console.log("Has PP:", body?.includes("PP-2023-2828"));
    console.log("Errors:", errors);
  });
});
