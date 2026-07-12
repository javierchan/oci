/* Browser coverage for contextual AI launchers, Catalog badges, and frequency-code governance. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type ProjectList = { projects: Array<{ id: string }> };
type CatalogPage = { integrations: Array<{ id: string }>; total: number };
type Graph = {
  nodes: Array<{ label: string }>;
  edges: Array<{ source: string; target: string }>;
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

async function findProjectIntegration(
  request: APIRequestContext,
): Promise<{ projectId: string; integrationId: string }> {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  let best: { projectId: string; integrationId: string; total: number } | null = null;
  for (const project of projects.projects) {
    const catalogResponse = await request.get(`${apiBase}/api/v1/catalog/${project.id}?page=1&page_size=1`);
    if (!catalogResponse.ok()) continue;
    const catalog = (await catalogResponse.json()) as CatalogPage;
    if (catalog.total > 0 && catalog.integrations[0]) {
      if (!best || catalog.total > best.total) {
        best = { projectId: project.id, integrationId: catalog.integrations[0].id, total: catalog.total };
      }
    }
  }
  if (best) return { projectId: best.projectId, integrationId: best.integrationId };
  throw new Error("E2E requires a project with at least one integration");
}

test("uses one geometry for Catalog labels", async ({ page, request }) => {
  const { projectId } = await findProjectIntegration(request);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projects/${projectId}/catalog`);

  const firstRow = page.locator("tbody tr").first();
  const badges = firstRow.locator(".catalog-badge");
  await expect(badges).toHaveCount(3);
  const dimensions = await badges.evaluateAll((elements) =>
    elements.map((element) => {
      const style = window.getComputedStyle(element);
      return { height: element.getBoundingClientRect().height, radius: style.borderRadius };
    }),
  );
  expect(new Set(dimensions.map((item) => item.height)).size).toBe(1);
  expect(new Set(dimensions.map((item) => item.radius))).toEqual(new Set(["6px"]));
});

test("opens both integration and current-canvas reviews with live provider status", async ({ page, request }) => {
  const { projectId, integrationId } = await findProjectIntegration(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/projects/${projectId}/catalog/${integrationId}`);

  await page.getByRole("button", { name: "Review integration", exact: true }).click();
  const integrationReviewBoard = page.getByLabel("Governed AI review");
  await expect(integrationReviewBoard).toBeVisible();
  await expect(integrationReviewBoard.getByText("Provider status", { exact: true })).toBeVisible();
  await expect(integrationReviewBoard.getByText("governed deterministic evidence", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Close AI review" }).click();

  const canvasReview = page.getByRole("button", { name: "Review current canvas", exact: true });
  await expect(canvasReview).toBeEnabled();
  await canvasReview.click();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
  await expect(page.getByText("Integration review", { exact: true })).toBeVisible();
});

test("opens system and dependency-path reviews with their selected graph context", async ({ page, request }) => {
  const { projectId } = await findProjectIntegration(request);
  const graphResponse = await request.get(`${apiBase}/api/v1/catalog/${projectId}/graph`);
  expect(graphResponse.ok()).toBe(true);
  const graph = (await graphResponse.json()) as Graph;
  const node = graph.nodes[0];
  const edge = graph.edges.find(
    (candidate) => candidate.source === node.label || candidate.target === node.label,
  );
  expect(edge, "focused system must have an adjacent dependency path").toBeTruthy();
  if (!edge) throw new Error("Focused system has no adjacent dependency path");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projects/${projectId}/graph`);
  const focusInput = page.getByLabel("Focus system");
  await focusInput.click();
  await focusInput.fill(node.label);
  await page.getByRole("option", { name: node.label, exact: true }).click();
  await page.getByRole("button", { name: "Analyze system", exact: true }).click();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
  await expect(page.getByText(`Graph node: ${node.label}`, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close AI review" }).click();
  await page.getByRole("button", { name: "Close topology detail panel" }).click();

  await page.getByRole("button", { name: "All paths", exact: true }).click();
  await page.getByRole("button", { name: `${edge.source} to ${edge.target}`, exact: false }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Analyze dependency path", exact: true }).click();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
  await expect(page.getByText(`Graph edge: ${edge.source} → ${edge.target}`, { exact: true })).toBeVisible();
});

test("shows only active FQNN records and rejects a non-standard code in the editor", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/admin/dictionaries/FREQUENCY");

  await expect(page.getByText("16 visible · 16 total", { exact: true })).toBeVisible();
  const codes = await page.getByTestId("dictionary-code").allTextContents();
  expect(codes).toHaveLength(16);
  expect(codes.every((code) => /^FQ\d{2}$/.test(code))).toBe(true);

  await page.getByRole("button", { name: "New Option" }).click();
  await page.getByLabel("Frequency Code").fill("FREQ-17");
  await page.getByLabel("Value").fill("Every 3 hours");
  await page.getByRole("button", { name: "Create Option" }).click();
  await expect(page.getByText("Frequency code must use FQNN format, for example FQ17.")).toBeVisible();
});
