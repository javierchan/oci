/* Playwright smoke coverage for the admin synthetic landing and detail pages. */

import { expect, test } from "@playwright/test";

type CreatedSyntheticJob = {
  id: string;
  preset_code: string;
  status: string;
};

test.describe("Admin synthetic smoke", () => {
  test("renders the landing page with governed presets", async ({ page }) => {
    await page.goto("/admin/synthetic");

    await expect(page.getByRole("heading", { name: "Synthetic Lab" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Synthetic generation jobs" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Synthetic Job" })).toBeVisible();

    const presetSelect = page.locator("select").first();
    await expect(presetSelect).toBeVisible();
    await expect(presetSelect.locator("option")).toContainText([
      "Enterprise Reference",
      "Ephemeral Smoke Validation",
      "Retained Smoke Validation",
    ]);
  });

  test("submits an ephemeral smoke job and opens its detail page", async ({ page }) => {
    await page.goto("/admin/synthetic");

    const presetSelect = page.locator("select").first();
    await presetSelect.selectOption("ephemeral-smoke");
    await expect(page.getByText("Smoke validation preset.", { exact: false })).toBeVisible();

    const createButton = page.getByRole("button", { name: "Create Synthetic Job" });
    await expect(createButton).toBeEnabled();

    const [createResponse] = await Promise.all([
      page.waitForResponse((response) => {
        return (
          response.url().includes("/api/v1/admin/synthetic/jobs") &&
          response.request().method() === "POST" &&
          response.status() === 202
        );
      }),
      createButton.click(),
    ]);

    const created = (await createResponse.json()) as CreatedSyntheticJob;
    expect(created.id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(created.preset_code).toBe("ephemeral-smoke");
    expect(created.status).toBe("pending");

    await expect(page.getByRole("link", { name: created.id })).toBeVisible();

    await page.goto(`/admin/synthetic/${created.id}`);

    await expect(page.getByRole("heading", { name: "Synthetic Job Detail" })).toBeVisible();
    await expect(page.getByText(created.id)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Normalized Inputs" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Execution Results" })).toBeVisible();
  });
});
