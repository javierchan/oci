/* Browser E2E for terminal OCI price synchronization and governed BOM generation. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type PriceSourceList = { sources: Array<{ id: string; source_type: string }> };
type PriceJob = { id: string; status: string; snapshot_id: string | null; item_count: number };
type PriceSnapshot = { id: string; approval_status: string };
type Scenario = { id: string; status: string };
type MetricOption = {
  service_id: string;
  metric_key: string;
  quantity_unit: string;
  source_baseline_quantity: number;
  baseline_quantity: number;
  planning_envelope_quantity: number | null;
  requires_explicit_quantity: boolean;
  default_sku_mapping_id: string;
};
type ScenarioAssistant = {
  draft: Record<string, unknown>;
  detected_services: string[];
  metric_options: MetricOption[];
};
type SelectableProductPage = {
  items: Array<{
    service_id: string;
    product_name: string;
    category: string;
    classification: string;
    readiness: string;
    already_in_scenario: boolean;
  }>;
  page: number;
  page_size: number;
  total: number;
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
type SyntheticJob = {
  id: string;
  status: string;
  project_id: string | null;
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const adminHeaders = { "X-Actor-Id": "pricing-e2e-admin", "X-Actor-Role": "Admin" };
const architectHeaders = { "X-Actor-Id": "pricing-e2e-architect", "X-Actor-Role": "Architect" };

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

async function readSyntheticJob(request: APIRequestContext, jobId: string): Promise<SyntheticJob> {
  const response = await request.get(`${apiBase}/api/v1/admin/synthetic/jobs/${jobId}`, {
    headers: adminHeaders,
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as SyntheticJob;
}

let syntheticJobId: string | null = null;

test.afterEach(async ({ request }) => {
  if (!syntheticJobId) return;
  const jobId = syntheticJobId;
  syntheticJobId = null;
  await expect
    .poll(async () => (await readSyntheticJob(request, jobId)).status, {
      timeout: 120_000,
      intervals: [1_000, 2_000, 5_000],
      message: "isolated pricing fixture should reach a cleanable terminal state",
    })
    .toMatch(/^(completed|failed|cleaned_up)$/);
  const terminal = await readSyntheticJob(request, jobId);
  if (terminal.status !== "cleaned_up") {
    const cleanup = await request.post(`${apiBase}/api/v1/admin/synthetic/jobs/${jobId}/cleanup`, {
      headers: adminHeaders,
    });
    expect(cleanup.ok()).toBe(true);
    expect(((await cleanup.json()) as SyntheticJob).status).toBe("cleaned_up");
  }
});

test("reaches terminal pricing and BOM jobs and renders the governed estimate", async ({ page, request }) => {
  test.setTimeout(240_000);
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
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
  const snapshotId = completedSync.snapshot_id as string;
  const approveCatalogResponse = await request.post(
    `${apiBase}/api/v1/pricing/catalog-snapshots/${snapshotId}/approve`,
    { headers: adminHeaders },
  );
  expect(approveCatalogResponse.ok(), await approveCatalogResponse.text()).toBe(true);
  expect(((await approveCatalogResponse.json()) as PriceSnapshot).approval_status).toBe("approved");

  await page.goto("/admin/pricing");
  await expect(page.getByRole("heading", { name: "OCI Pricing" })).toBeVisible();
  await page.getByRole("tab", { name: "Official Sources" }).click();
  await expect(
    page.getByText("Oracle OCI Public List Pricing", { exact: true }).filter({ visible: true }).first(),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Import Price List + Supplement workbook" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import private Oracle workbook" })).toBeVisible();
  await page.getByRole("tab", { name: "Releases & BOM" }).click();
  await expect(page.getByText(`${completedSync.item_count} items`, { exact: true }).first()).toBeVisible();

  const syntheticResponse = await request.post(`${apiBase}/api/v1/admin/synthetic/jobs`, {
    headers: adminHeaders,
    data: {
      preset_code: "retained-smoke",
      project_name: `Pricing BOM E2E ${Date.now()}`,
    },
  });
  expect(syntheticResponse.status()).toBe(202);
  const synthetic = (await syntheticResponse.json()) as SyntheticJob;
  syntheticJobId = synthetic.id;
  await expect
    .poll(async () => (await readSyntheticJob(request, synthetic.id)).status, {
      timeout: 120_000,
      intervals: [1_000, 2_000, 5_000],
      message: "isolated pricing fixture should reach completed",
    })
    .toBe("completed");
  const completedSynthetic = await readSyntheticJob(request, synthetic.id);
  expect(completedSynthetic.project_id).toMatch(/^[0-9a-f-]{36}$/i);
  const projectId = completedSynthetic.project_id as string;
  const assistantResponse = await request.get(
    `${apiBase}/api/v1/projects/${projectId}/deployment-scenarios/assistant?include_llm=false`,
    { headers: architectHeaders },
  );
  expect(assistantResponse.ok()).toBe(true);
  const assistant = (await assistantResponse.json()) as ScenarioAssistant;
  expect(assistant.detected_services.length).toBeGreaterThan(0);
  expect(assistant.metric_options.length).toBeGreaterThan(0);
  const apiGatewayCalls = assistant.metric_options.find((option) => option.metric_key === "api_gateway_call_millions");
  expect(apiGatewayCalls?.source_baseline_quantity).toBeGreaterThan(0);
  expect(apiGatewayCalls?.source_baseline_quantity).toBeLessThan(1);
  expect(apiGatewayCalls?.baseline_quantity).toBe(apiGatewayCalls?.source_baseline_quantity);
  expect(apiGatewayCalls?.planning_envelope_quantity).toBe(1);
  const dataIntegrationWorkspace = assistant.metric_options.find((option) => option.metric_key === "di_workspace_hours");
  expect(dataIntegrationWorkspace?.requires_explicit_quantity).toBe(true);
  expect(dataIntegrationWorkspace?.baseline_quantity).toBe(0);
  const selectableResponse = await request.get(
    `${apiBase}/api/v1/projects/${projectId}/selectable-products?page=1&page_size=100`,
    { headers: architectHeaders },
  );
  expect(selectableResponse.ok(), await selectableResponse.text()).toBe(true);
  const selectable = (await selectableResponse.json()) as SelectableProductPage;
  const manuallySelectableProduct = selectable.items.find(
    (product) => !assistant.detected_services.includes(product.service_id),
  );
  expect(manuallySelectableProduct, "fixture should expose an approved product outside integration detection").toBeDefined();
  const selectableMetricsResponse = await request.get(
    `${apiBase}/api/v1/projects/${projectId}/selectable-products/${encodeURIComponent(manuallySelectableProduct?.service_id ?? "")}/metric-options`,
    { headers: architectHeaders },
  );
  expect(selectableMetricsResponse.ok(), await selectableMetricsResponse.text()).toBe(true);
  expect(((await selectableMetricsResponse.json()) as MetricOption[]).length).toBeGreaterThan(0);
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
  expect(scenarioResponse.ok(), await scenarioResponse.text()).toBe(true);
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
  await expect(page.getByRole("combobox", { name: "Deployment scenario" })).toContainText(
    scenario.name,
  );
  await expect(page.getByRole("heading", { name: "Demand, commercial variant, price and provenance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "When capacity starts, what drives cost, and where it lands" })).toBeVisible();

  const productSearch = page.getByPlaceholder("Find product, metric, or SKU...");
  await productSearch.fill("B92598");
  const dataIntegrationProduct = page.locator("article").filter({ hasText: "OCI Data Integration" }).first();
  await expect(dataIntegrationProduct).toBeVisible();
  await expect(dataIntegrationProduct.getByRole("button", { name: "Business hours · 160h" })).toBeVisible();
  const workspaceQuantity = dataIntegrationProduct.getByLabel(/workspace hours initial quantity/i);
  await dataIntegrationProduct.getByRole("button", { name: "Always on · 744h" }).click();
  await expect(workspaceQuantity).toHaveValue("744");
  await expect(dataIntegrationProduct.getByText("Always-on assumption", { exact: false })).toBeVisible();
  await dataIntegrationProduct.getByRole("button", { name: "Business hours · 160h" }).click();
  await expect(workspaceQuantity).toHaveValue("160");
  await expect(dataIntegrationProduct.getByText("Always-on assumption", { exact: false })).toHaveCount(0);
  await productSearch.clear();

  const productionPlan = page.getByRole("region", { name: "Production consumption plan" });
  await productionPlan.getByRole("button", { name: "Add OCI product" }).click();
  await productionPlan.getByPlaceholder("Search product, category, or service ID...").fill(
    manuallySelectableProduct?.product_name ?? "",
  );
  await expect(productionPlan.getByText(manuallySelectableProduct?.product_name ?? "", { exact: true })).toBeVisible();
  await productionPlan.getByRole("button", { name: "Add product" }).click();
  const manuallyAddedProduct = productionPlan.locator("article").filter({
    hasText: manuallySelectableProduct?.product_name ?? "",
  });
  await expect(manuallyAddedProduct).toBeVisible();
  await expect(manuallyAddedProduct.getByText("Added", { exact: true })).toBeVisible();
  await manuallyAddedProduct.getByTitle(
    `Remove ${manuallySelectableProduct?.product_name ?? ""} from Production`,
  ).click();
  await expect(manuallyAddedProduct).toHaveCount(0);
  const productReview = productionPlan.getByRole("combobox", {
    name: "Product to review in Production",
  });
  await productReview.click();
  await page.getByRole("option", { name: /^OCI Data Integration/ }).click();
  await expect(productionPlan.locator("article")).toHaveCount(1);
  await expect(productionPlan.locator("article").filter({ hasText: "OCI Data Integration" })).toBeVisible();
  await expect(productionPlan.locator("article").filter({ hasText: "OCI API Gateway" })).toHaveCount(0);
  await productReview.click();
  await page.getByRole("option", { name: /^All products/ }).click();
  await expect(productionPlan.locator("article").filter({ hasText: "OCI API Gateway" })).toBeVisible();

  await page.getByRole("button", { name: "Add environment" }).click();
  const environmentNames = page.getByLabel(/Environment \d+ name/);
  const environmentNameCount = await environmentNames.count();
  const newEnvironmentName = environmentNames.nth(environmentNameCount - 1);
  await newEnvironmentName.fill("");
  await newEnvironmentName.pressSequentially("Disaster Recovery", { delay: 15 });
  await expect(newEnvironmentName).toHaveValue("Disaster Recovery");
  const disasterRecovery = page.getByRole("region", { name: "Disaster Recovery consumption plan" });
  await disasterRecovery.getByRole("button", { name: "Add metric" }).click();
  await disasterRecovery.getByRole("combobox", {
    name: "Product metric to add to Disaster Recovery",
  }).click();
  await page.getByRole("option").first().click();
  await disasterRecovery.getByRole("button", { name: "Add selected metric" }).click();
  await expect(disasterRecovery.locator("article").first()).toBeVisible();
  await page.getByRole("button", { name: "Monthly matrix" }).click();
  const firstMonthlyQuantity = disasterRecovery.locator('input[aria-label$=" month 1"]');
  await firstMonthlyQuantity.fill("3");
  await expect(firstMonthlyQuantity).toHaveValue("3");
  await page.getByRole("button", { name: "Standard" }).click();
  await disasterRecovery.getByTitle("Remove environment").click();

  await expect(page.getByLabel("Monthly cost ramp chart").locator("svg").first()).toBeVisible();
  await expect(page.getByText("Products and activation", { exact: true })).toBeVisible();
  await expect(page.getByText("Top contract drivers", { exact: true })).toBeVisible();
  await expect(page.locator("[data-rollout-monthly-evidence]").first()).toBeVisible();
  await expect(page.getByText("Historical line items have no editable phase definition.", { exact: true })).toHaveCount(0);
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
  expect(browserErrors).toEqual([]);
});
