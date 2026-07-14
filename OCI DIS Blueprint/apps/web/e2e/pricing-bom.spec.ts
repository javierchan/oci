/* Browser E2E for terminal OCI price synchronization and governed BOM generation. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type ProjectList = { projects: Array<{ id: string }> };
type PriceSourceList = { sources: Array<{ id: string; source_type: string }> };
type PriceJob = { id: string; status: string; snapshot_id: string | null; item_count: number };
type Scenario = { id: string; status: string };
type MetricOption = {
  service_id: string;
  metric_key: string;
  quantity_unit: string;
  baseline_quantity: number;
  default_sku_mapping_id: string;
};
type ScenarioAssistant = {
  draft: Record<string, unknown>;
  detected_services: string[];
  metric_options: MetricOption[];
};
type BomJob = { id: string; status: string; bom_snapshot_id: string | null };
type BomSnapshot = {
  id: string;
  coverage_pct: number;
  first_active_period: number | null;
  steady_state_period: number | null;
  ramp_deferred_amount: number;
  monthly_series: Array<{ period_index: number; total: number }>;
  summary: { line_count: number };
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const adminHeaders = { "X-Actor-Id": "pricing-e2e-admin", "X-Actor-Role": "Admin" };
const architectHeaders = { "X-Actor-Id": "pricing-e2e-architect", "X-Actor-Role": "Architect" };

async function findPricableProject(
  request: APIRequestContext,
): Promise<{ projectId: string; assistant: ScenarioAssistant }> {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  for (const project of projects.projects) {
    const response = await request.get(
      `${apiBase}/api/v1/projects/${project.id}/deployment-scenarios/assistant?include_llm=false`,
      { headers: architectHeaders },
    );
    if (!response.ok()) continue;
    const assistant = (await response.json()) as ScenarioAssistant;
    if (assistant.detected_services.length > 0) return { projectId: project.id, assistant };
  }
  throw new Error("Pricing E2E requires a project with a technical snapshot");
}

async function readPriceJob(request: APIRequestContext, jobId: string): Promise<PriceJob> {
  const response = await request.get(`${apiBase}/api/v1/pricing/sync-jobs/${jobId}`, {
    headers: adminHeaders,
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as PriceJob;
}

async function readBomJob(request: APIRequestContext, projectId: string, jobId: string): Promise<BomJob> {
  const response = await request.get(`${apiBase}/api/v1/projects/${projectId}/bom-jobs/${jobId}`, {
    headers: architectHeaders,
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as BomJob;
}

test("reaches terminal pricing and BOM jobs and renders the governed estimate", async ({ page, request }) => {
  test.setTimeout(150_000);
  const sourcesResponse = await request.get(`${apiBase}/api/v1/pricing/sources`, { headers: adminHeaders });
  expect(sourcesResponse.ok()).toBe(true);
  const sources = (await sourcesResponse.json()) as PriceSourceList;
  const publicSource = sources.sources.find((source) => source.source_type === "public_list");
  expect(publicSource).toBeDefined();

  const syncResponse = await request.post(`${apiBase}/api/v1/pricing/sync-jobs`, {
    headers: adminHeaders,
    data: { source_id: publicSource?.id, currency: "USD" },
  });
  expect(syncResponse.status()).toBe(202);
  const syncJob = (await syncResponse.json()) as PriceJob;
  await expect
    .poll(async () => (await readPriceJob(request, syncJob.id)).status, {
      timeout: 90_000,
      intervals: [1_000, 2_000, 5_000],
    })
    .toBe("completed");
  const completedSync = await readPriceJob(request, syncJob.id);
  expect(completedSync.snapshot_id).toMatch(/^[0-9a-f-]{36}$/i);
  expect(completedSync.item_count).toBeGreaterThan(0);

  await page.goto("/admin/pricing");
  await expect(page.getByRole("heading", { name: "OCI Pricing" })).toBeVisible();
  await expect(page.getByText("Oracle OCI Public List Pricing", { exact: true })).toBeVisible();
  await expect(page.getByText(`${completedSync.item_count} items`, { exact: true }).first()).toBeVisible();

  const { projectId, assistant } = await findPricableProject(request);
  expect(assistant.metric_options.length).toBeGreaterThan(0);
  const quantityPhases = (scale: number, startMonth: number) => assistant.metric_options.map((option) => ({
    service_id: option.service_id,
    metric_key: option.metric_key,
    sku_mapping_id: option.default_sku_mapping_id,
    start_month: startMonth,
    end_month: 12,
    start_multiplier: 1,
    end_multiplier: 1,
    interpolation: "step",
    start_quantity: option.baseline_quantity * scale,
    end_quantity: option.baseline_quantity * scale,
    quantity_unit: option.quantity_unit,
    monthly_quantities: [],
    rationale: "Playwright explicit-unit rollout",
  }));

  const scenarioResponse = await request.post(
    `${apiBase}/api/v1/projects/${projectId}/deployment-scenarios`,
    {
      headers: architectHeaders,
      data: {
        ...assistant.draft,
        name: "Playwright phased rollout",
        start_date: "2026-01-01",
        contract_months: 12,
        consumption_model: "explicit_units",
        environments: [
          {
            name: "Production",
            active_hours_month: 744,
            demand_share: 1,
            ha_multiplier: 1,
            dr_role: "primary",
            phases: quantityPhases(1, 3),
          },
          {
            name: "QA",
            active_hours_month: 240,
            demand_share: 1,
            ha_multiplier: 1,
            dr_role: "none",
            phases: quantityPhases(0.2, 1),
          },
        ],
      },
    },
  );
  expect(scenarioResponse.ok()).toBe(true);
  const scenario = (await scenarioResponse.json()) as Scenario;
  const approveResponse = await request.post(
    `${apiBase}/api/v1/projects/${projectId}/deployment-scenarios/${scenario.id}/approve`,
    { headers: architectHeaders },
  );
  expect(approveResponse.ok()).toBe(true);
  expect(((await approveResponse.json()) as Scenario).status).toBe("approved");

  const bomResponse = await request.post(`${apiBase}/api/v1/projects/${projectId}/bom-jobs`, {
    headers: architectHeaders,
    data: { scenario_id: scenario.id },
  });
  expect(bomResponse.status()).toBe(202);
  const bomJob = (await bomResponse.json()) as BomJob;
  await expect
    .poll(async () => (await readBomJob(request, projectId, bomJob.id)).status, {
      timeout: 90_000,
      intervals: [500, 1_000, 2_000],
    })
    .toBe("completed");
  const completedBom = await readBomJob(request, projectId, bomJob.id);
  expect(completedBom.bom_snapshot_id).toMatch(/^[0-9a-f-]{36}$/i);

  const snapshotResponse = await request.get(
    `${apiBase}/api/v1/projects/${projectId}/bom-snapshots/${completedBom.bom_snapshot_id}`,
    { headers: architectHeaders },
  );
  expect(snapshotResponse.ok()).toBe(true);
  const snapshot = (await snapshotResponse.json()) as BomSnapshot;
  expect(snapshot.summary.line_count).toBeGreaterThan(0);
  expect(snapshot.coverage_pct).toBeGreaterThan(0);
  expect(snapshot.monthly_series).toHaveLength(12);
  expect(snapshot.first_active_period).toBe(1);
  expect(snapshot.steady_state_period).toBe(3);
  expect(snapshot.ramp_deferred_amount).toBeGreaterThan(0);
  expect(snapshot.monthly_series[0].total).toBeLessThan(snapshot.monthly_series[2].total);

  await page.goto(`/projects/${projectId}/bom`);
  await expect(page.getByRole("heading", { name: "BOM & Cost" })).toBeVisible();
  await expect(page.getByLabel("Deployment scenario")).toHaveValue(scenario.id);
  await expect(page.getByRole("heading", { name: "Demand, commercial variant, price and provenance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "When capacity starts, what drives cost, and where it lands" })).toBeVisible();

  await page.getByRole("button", { name: "Add environment" }).click();
  const environmentNames = page.getByLabel(/Environment \d+ name/);
  const environmentNameCount = await environmentNames.count();
  const newEnvironmentName = environmentNames.nth(environmentNameCount - 1);
  await newEnvironmentName.fill("");
  await newEnvironmentName.pressSequentially("Disaster Recovery", { delay: 15 });
  await expect(newEnvironmentName).toHaveValue("Disaster Recovery");
  const disasterRecovery = page.getByRole("region", { name: "Disaster Recovery consumption plan" });
  await disasterRecovery.getByRole("button", { name: "Add product metric" }).click();
  const productSelect = disasterRecovery.getByRole("combobox", { name: "Product" });
  await expect(productSelect).not.toHaveValue("");
  await page.getByRole("button", { name: "Monthly matrix" }).click();
  const firstMonthlyQuantity = disasterRecovery.locator('input[aria-label$=" month 1"]');
  await firstMonthlyQuantity.fill("3");
  await expect(firstMonthlyQuantity).toHaveValue("3");
  await page.getByRole("button", { name: "Standard" }).click();
  await disasterRecovery.getByTitle("Remove environment").click();

  await expect(page.getByLabel("Monthly cost ramp chart").locator("svg").first()).toBeVisible();
  await expect(page.getByText("Products and activation", { exact: true })).toBeVisible();
  await expect(page.getByText("Top contract drivers", { exact: true })).toBeVisible();
  const productMode = page.getByRole("group", { name: "Group monthly consumption" }).getByRole("button", { name: "Product" });
  await productMode.click();
  await expect(productMode).toHaveAttribute("aria-pressed", "true");
  const firstDriver = page.getByRole("button", { name: /^Inspect / }).first();
  await firstDriver.click();
  await expect(firstDriver).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Selected Product", { exact: true })).toBeVisible();
  const secondProduct = page.locator("button[data-rollout-product]").nth(1);
  await secondProduct.click();
  await expect(secondProduct).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("Timing effect compares this rollout", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "XLSX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "JSON" })).toBeVisible();
  await expect(page.getByRole("button", { name: "PDF" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "BOM & Cost" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Monthly matrix" })).toBeVisible();
  await page.getByRole("tab", { name: "Inspector" }).click();
  await expect(page.getByText("Selected Product", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
});
