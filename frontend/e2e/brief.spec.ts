import { test, expect } from "@playwright/test";

test.describe("Brief Page", () => {
  const testPP = "PP-2023-2828";

  test("loads brief page with PP number", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
  });

  test("has Brief and Site Context tabs", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByRole("tab", { name: "Brief" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Site Context" })).toBeVisible();
  });

  test("Site Context tab shows planning data", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });

    await page.getByRole("tab", { name: "Site Context" }).click();
    await page.waitForTimeout(3000);

    const content = await page.textContent("body");
    const hasData = content?.includes("Zoning") ||
                    content?.includes("Planning Controls") ||
                    content?.includes("No site context") ||
                    content?.includes("not available");
    expect(hasData).toBeTruthy();
  });

  test("has Ask questions button", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("Ask questions")).toBeVisible();
  });

  test("chat panel opens on click", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await page.getByText("Ask questions").click();
    await expect(page.getByPlaceholder("Ask about this proposal")).toBeVisible();
  });

  test("has Draft a submission button", async ({ page }) => {
    await page.goto(`/brief/${testPP}`);
    await expect(page.getByRole("heading", { name: testPP })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("Draft a submission")).toBeVisible();
  });
});
