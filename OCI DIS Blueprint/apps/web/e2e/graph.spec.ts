/* Playwright coverage for risk-aware topology investigation, export, and responsive fallback. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type ProjectSummary = { id: string };
type ProjectList = { projects: ProjectSummary[] };
type GraphSummary = {
  nodes: Array<{ id: string; label: string }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    integration_count: number;
    risk_qa_status: string;
    risk_score: number;
  }>;
  meta: {
    integration_count: number;
    business_process_families: string[];
    brands: string[];
  };
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

async function findProjectWithTopology(request: APIRequestContext): Promise<{ projectId: string; graph: GraphSummary }> {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects/`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  let bestMatch: { projectId: string; graph: GraphSummary } | null = null;

  for (const project of projects.projects) {
    const graphResponse = await request.get(`${apiBase}/api/v1/catalog/${project.id}/graph`);
    if (!graphResponse.ok()) {
      continue;
    }
    const graph = (await graphResponse.json()) as GraphSummary;
    if (graph.nodes.length >= 3 && graph.edges.filter((edge) => edge.risk_qa_status !== "OK").length >= 2) {
      if (!bestMatch || graph.meta.integration_count > bestMatch.graph.meta.integration_count) {
        bestMatch = { projectId: project.id, graph };
      }
    }
  }
  if (bestMatch) {
    return bestMatch;
  }
  throw new Error("E2E requires one project with at least three systems and two risk dependency paths");
}

test("investigates, re-weights, exports, and navigates the desktop topology", async ({ page, request }) => {
  const { projectId, graph } = await findProjectWithTopology(request);
  const focusNode = graph.nodes[0];
  const focusEdge = graph.edges[0];
  const riskEdges = graph.edges
    .filter((edge) => edge.risk_qa_status !== "OK")
    .sort((left, right) => right.risk_score - left.risk_score);

  await page.setViewportSize({ width: 1280, height: 720 });

  await page.goto(`/projects/${projectId}/map`);
  await expect(page.getByText("Governed topology", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Integration system dependency topology")).toBeVisible();
  await expect(page.locator("main").getByText(`${graph.nodes.length} systems`, { exact: true }).first()).toBeVisible();
  const topologyPulse = page.getByTestId("topology-pulse");
  await expect(topologyPulse).toBeVisible();
  await expect(topologyPulse.getByText(`${graph.nodes.length} systems`, { exact: true })).toBeVisible();
  await expect(topologyPulse.getByText("Payload / execution", { exact: true })).toBeVisible();
  await expect(topologyPulse.getByText("Ranked path load", { exact: true })).toBeVisible();
  const rankedPath = topologyPulse.locator('button[title*="payload per execution"]').first();
  await rankedPath.hover();
  await expect(page.locator('[data-pulse-highlighted="true"]')).toHaveCount(1);
  await rankedPath.click();
  await expect(page.locator("main aside h2")).toBeVisible();
  await page.getByRole("button", { name: "Close topology detail panel" }).click();
  const processFilter = page.getByRole("combobox", {
    name: "Filter by business process family",
    exact: true,
  });
  await expect(processFilter).toBeVisible();
  await expect(page.getByLabel("Filter by brand")).toBeVisible();

  if (graph.meta.business_process_families.length > 0) {
    const processFamily = graph.meta.business_process_families[0];
    const processResponse = page.waitForResponse((response) =>
      response.url().includes("business_process_family=") && response.ok(),
    );
    await processFilter.click();
    await page.getByRole("option", { name: processFamily, exact: true }).click();
    await processResponse;
    await expect(processFilter).toHaveValue(processFamily);
    await page.getByRole("button", { name: "Clear filters (1)" }).click();
  }

  if (graph.meta.brands.length > 0) {
    const brand = graph.meta.brands[0];
    const brandResponse = page.waitForResponse((response) => response.url().includes("brand=") && response.ok());
    await page.getByLabel("Filter by brand").selectOption(brand);
    await brandResponse;
    await expect(page.getByLabel("Filter by brand")).toHaveValue(brand);
    await page.getByRole("button", { name: "Clear filters (1)" }).click();
  }

  const focusInput = page.getByLabel("Focus system");
  await focusInput.click();
  await expect(page.getByRole("listbox", { name: "Focus options" })).toBeVisible();
  await focusInput.fill(focusNode.label);
  await page.getByRole("option", { name: focusNode.label, exact: true }).click();
  await expect(page.getByRole("heading", { name: focusNode.label, exact: true })).toBeVisible();
  await expect(topologyPulse.getByText(focusNode.label, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Domains", exact: true })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Close topology detail panel" }).click();
  await page.getByRole("button", { name: /^Needs Review/ }).click();
  await page.getByRole("button", { name: "Clear filters (1)" }).click();

  const startReview = page.getByRole("button", { name: "Start review" });
  await expect(startReview).toBeEnabled();
  await startReview.click();
  await expect(page.getByRole("heading", { name: `${riskEdges[0].source} → ${riskEdges[0].target}` })).toBeVisible();
  const reviewHeading = page.locator("main aside h2");
  const firstReviewHeading = await reviewHeading.textContent();
  expect(firstReviewHeading).toBeTruthy();
  await page.getByRole("button", { name: "Review next" }).click();
  await expect(reviewHeading).not.toHaveText(firstReviewHeading ?? "");
  await expect(page.getByText(`1 of ${riskEdges.length} reviewed in this session`, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close topology detail panel" }).click();

  await page.getByLabel("Edge weight metric").selectOption("payload");
  await page.getByRole("button", { name: "Map legend", exact: true }).click();
  await expect(page.getByText("Thickness = Payload / hour", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Process color" }).click();
  await expect(page.getByRole("button", { name: "Process color" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Color = process family", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Flow", exact: true }).click();
  await expect(page.getByText("SYSTEMS OF RECORD", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "All paths", exact: true }).click();

  await page.getByRole("button", { name: `${focusEdge.source} to ${focusEdge.target}`, exact: false }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: `${focusEdge.source} → ${focusEdge.target}` })).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze dependency path", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close topology detail panel" }).click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export topology as PNG" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^integration-map-.+\.png$/);
  await download.delete();
});

test("provides a useful mobile dependency explorer", async ({ page, request }) => {
  const { projectId, graph } = await findProjectWithTopology(request);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(`/projects/${projectId}/map`);

  await expect(page.getByRole("heading", { name: "Dependency explorer" })).toBeVisible();
  await expect(page.getByText(`${graph.nodes.length} systems · ${graph.edges.length} paths · ${graph.meta.integration_count} integrations`)).toBeVisible();
  await expect(page.getByLabel("Topology Pulse insights")).toBeVisible();
  await expect(page.getByText("Payload / execution", { exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Triage/ })).toBeVisible();
  await page.getByRole("tab", { name: /^Systems/ }).click();
  await page.getByLabel("Search topology").fill(graph.nodes[0].label);
  await expect(page.getByRole("link", { name: graph.nodes[0].label, exact: false })).toBeVisible();
});
