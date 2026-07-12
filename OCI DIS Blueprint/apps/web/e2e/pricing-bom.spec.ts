/* Browser E2E for terminal OCI price synchronization and governed BOM generation. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type ProjectList = { projects: Array<{ id: string }> };
type PriceSourceList = { sources: Array<{ id: string; source_type: string }> };
type PriceJob = { id: string; status: string; snapshot_id: string | null; item_count: number };
type Scenario = { id: string; status: string };
type ScenarioAssistant = { draft: Record<string, unknown>; detected_services: string[] };
type BomJob = { id: string; status: string; bom_snapshot_id: string | null };
type BomSnapshot = { id: string; coverage_pct: number; summary: { line_count: number } };

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

  const scenarioResponse = await request.post(
    `${apiBase}/api/v1/projects/${projectId}/deployment-scenarios`,
    {
      headers: architectHeaders,
      data: { ...assistant.draft, name: "Playwright governed baseline" },
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

  await page.goto(`/projects/${projectId}/bom`);
  await expect(page.getByRole("heading", { name: "BOM & Cost" })).toBeVisible();
  await expect(page.getByLabel("Deployment scenario")).toHaveValue(scenario.id);
  await expect(page.getByRole("heading", { name: "Demand, price and provenance" })).toBeVisible();
  await expect(page.getByRole("button", { name: "XLSX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "JSON" })).toBeVisible();
  await expect(page.getByRole("button", { name: "PDF" })).toBeVisible();
});
