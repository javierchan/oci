/* Playwright smoke coverage for the admin synthetic landing and detail pages. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type CreatedSyntheticJob = {
  id: string;
  preset_code: string;
  status: string;
  project_id?: string | null;
  catalog_target?: number;
  result_summary?: Record<string, unknown> | null;
  validation_results?: Record<string, unknown> | null;
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const adminHeaders = {
  "X-Actor-Id": "playwright-e2e",
  "X-Actor-Role": "admin",
};

async function readJob(request: APIRequestContext, jobId: string): Promise<CreatedSyntheticJob> {
  const response = await request.get(`${apiBase}/api/v1/admin/synthetic/jobs/${jobId}`, {
    headers: adminHeaders,
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as CreatedSyntheticJob;
}

test.describe("Admin synthetic smoke", () => {
  test.describe.configure({ mode: "serial" });

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

  test("submits an ephemeral smoke job and validates terminal cleanup", async ({ page, request }) => {
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

    await expect
      .poll(async () => (await readJob(request, created.id)).status, {
        timeout: 120_000,
        intervals: [1_000, 2_000, 5_000],
        message: "ephemeral synthetic job should reach its cleaned_up terminal state",
      })
      .toBe("cleaned_up");

    const terminal = await readJob(request, created.id);
    expect(terminal.project_id).toBeNull();
    expect(terminal.validation_results?.meets_catalog_target).toBe(true);
    expect(terminal.result_summary?.cleanup_removed_paths).toBeInstanceOf(Array);
  });

  test("validates critical project surfaces from a retained terminal job", async ({ page, request }) => {
    test.setTimeout(180_000);
    const createResponse = await request.post(`${apiBase}/api/v1/admin/synthetic/jobs`, {
      headers: adminHeaders,
      data: { preset_code: "retained-smoke" },
    });
    expect(createResponse.status()).toBe(202);
    const created = (await createResponse.json()) as CreatedSyntheticJob;

    try {
      await expect
        .poll(async () => (await readJob(request, created.id)).status, {
          timeout: 120_000,
          intervals: [1_000, 2_000, 5_000],
          message: "retained synthetic job should reach completed",
        })
        .toBe("completed");

      const terminal = await readJob(request, created.id);
      expect(terminal.project_id).toMatch(/^[0-9a-f-]{36}$/i);
      expect(terminal.validation_results?.meets_catalog_target).toBe(true);
      expect(Number(terminal.validation_results?.catalog_count)).toBeGreaterThanOrEqual(terminal.catalog_target ?? 17);
      const projectId = terminal.project_id as string;

      const catalogResponse = await request.get(
        `${apiBase}/api/v1/catalog/${projectId}?page=1&page_size=1`,
      );
      expect(catalogResponse.ok()).toBe(true);
      const catalog = (await catalogResponse.json()) as { integrations: Array<{ id: string }> };
      expect(catalog.integrations).toHaveLength(1);
      const integrationId = catalog.integrations[0].id;

      await page.goto(`/projects/${projectId}`);
      await expect(page.getByRole("heading", { name: terminal.result_summary?.project_name as string })).toBeVisible();
      await expect(page.getByText("Service rules", { exact: true })).toBeVisible();
      await expect(page.getByText("service-rules-", { exact: false })).toBeVisible();

      await page.goto(`/projects/${projectId}/catalog`);
      await expect(page.getByText("Catalog Grid", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Show Preview" }).click();
      await expect(page.getByRole("tab", { name: "Canvas" })).toBeVisible();
      await page.getByRole("tab", { name: "Canvas" }).click();
      await expect(page.getByText("Core tools", { exact: true })).toBeVisible();

      await page.goto(`/projects/${projectId}/catalog/${integrationId}`);
      await expect(page.getByRole("heading", { name: "Design the payload route end to end" })).toBeVisible();

      await page.goto(`/projects/${projectId}/graph`);
      await expect(page.getByLabel("Integration system dependency topology")).toBeVisible();

      await page.goto("/admin/services");
      await expect(page.getByRole("heading", { name: "Service Product Library" })).toBeVisible();

      await page.goto("/admin/assumptions");
      await expect(page.getByRole("heading", { name: "Assumptions" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Open Service Product Library" })).toBeVisible();
    } finally {
      const current = await readJob(request, created.id);
      if (current.status === "completed") {
        const cleanup = await request.post(
          `${apiBase}/api/v1/admin/synthetic/jobs/${created.id}/cleanup`,
          { headers: adminHeaders },
        );
        expect(cleanup.ok()).toBe(true);
        expect(((await cleanup.json()) as CreatedSyntheticJob).status).toBe("cleaned_up");
      }
    }
  });
});
