/* Playwright coverage for complete Dashboard product representation and action consistency. */

import { expect, test, type APIRequestContext } from "@playwright/test";

type ProjectList = { projects: Array<{ id: string; name: string; status: string }> };
type DashboardList = { snapshots: Array<{ snapshot_id: string }> };
type ProductFootprint = {
  captured_product_count: number;
  represented_product_count: number;
  rows_with_products: number;
  total_rows: number;
  products: Array<{ tool_key: string; service_id: string | null }>;
};
type DashboardSnapshot = { charts: { product_footprint: ProductFootprint } };

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

async function findDashboardWithProducts(
  request: APIRequestContext,
): Promise<{ projectId: string; footprint: ProductFootprint }> {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  let best: { projectId: string; footprint: ProductFootprint } | null = null;

  for (const project of projects.projects) {
    const listResponse = await request.get(`${apiBase}/api/v1/dashboard/${project.id}/snapshots`);
    if (!listResponse.ok()) continue;
    const list = (await listResponse.json()) as DashboardList;
    if (!list.snapshots[0]) continue;
    const snapshotResponse = await request.get(
      `${apiBase}/api/v1/dashboard/${project.id}/snapshots/${list.snapshots[0].snapshot_id}`,
    );
    if (!snapshotResponse.ok()) continue;
    const snapshot = (await snapshotResponse.json()) as DashboardSnapshot;
    if (snapshot.charts.product_footprint.captured_product_count > 0) {
      const candidate = { projectId: project.id, footprint: snapshot.charts.product_footprint };
      if (!best || candidate.footprint.total_rows > best.footprint.total_rows) {
        best = candidate;
      }
    }
  }
  if (best) return best;
  throw new Error("E2E requires one Dashboard snapshot with captured products");
}

test("represents every captured product and standardizes Dashboard actions", async ({ page, request }) => {
  const { projectId, footprint } = await findDashboardWithProducts(request);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projects/${projectId}`);

  await expect(page.getByRole("region", { name: "Every product used in the architecture" })).toBeVisible();
  await expect(page.getByText(`${footprint.represented_product_count} of ${footprint.captured_product_count} represented`)).toBeVisible();
  await expect(page.getByText(`${footprint.rows_with_products} of ${footprint.total_rows} rows covered`)).toBeVisible();
  for (const product of footprint.products) {
    await expect(page.getByRole("heading", { name: product.tool_key, exact: true })).toBeVisible();
  }

  const actions = ["Export brief", "Catalog", "Map", "Recalculate", "Review project"];
  const heights: number[] = [];
  for (const action of actions) {
    const control = page.getByRole("main").getByRole(
      action === "Recalculate" || action === "Review project" ? "button" : "link",
      { name: action, exact: true },
    );
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    heights.push(box?.height ?? 0);
    await expect(control).toHaveCSS("border-radius", "8px");
  }
  expect(new Set(heights).size).toBe(1);

  await page.getByRole("button", { name: "Review project", exact: true }).click();
  const reviewBoard = page.getByLabel("Governed AI review");
  await expect(reviewBoard).toBeVisible();
  await expect(reviewBoard.getByText("Provider status", { exact: true })).toBeVisible();
  await expect(reviewBoard.getByText("governed deterministic evidence", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Close AI review" }).click();

  await page.getByRole("complementary").getByRole("button", { name: "Open command palette" }).click();
  const commandPalette = page.getByRole("dialog", { name: "Command palette" });
  await expect(commandPalette).toBeVisible();
  const commandSearch = commandPalette.getByPlaceholder("Type a command, route, or workflow...");
  await expect(commandSearch).toBeFocused();
  await commandSearch.fill("Catalog");
  await expect(commandPalette.getByRole("link", { name: /Catalog/ })).toBeVisible();
  await commandSearch.fill("Run AI review");
  await commandPalette.getByRole("button", { name: /Run AI review/ }).click();
  await expect(commandPalette).toBeHidden();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
  await expect(page.getByText("Project review", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close AI review" }).click();

  const governedProduct = footprint.products.find((product) => product.service_id !== null);
  expect(governedProduct).toBeDefined();
  await page.getByRole("link", { name: "Product evidence", exact: true }).first().click();
  await expect(page).toHaveURL(new RegExp(`/admin/services/${governedProduct?.service_id}$`));
});

test("launches a real project review from the workspace command palette", async ({ page, request }) => {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  const activeProject = projects.projects.find((project) => project.status === "active");
  expect(activeProject).toBeDefined();
  if (!activeProject) throw new Error("E2E requires one active project");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/projects");
  await page.getByRole("complementary").getByRole("button", { name: "Open command palette" }).click();
  const commandPalette = page.getByRole("dialog", { name: "Command palette" });
  const commandSearch = commandPalette.getByPlaceholder("Type a command, route, or workflow...");
  await commandSearch.fill(activeProject.name);
  const reviewCommand = commandPalette.getByRole("button", { name: new RegExp(`Review ${activeProject.name}`) });
  await expect(reviewCommand).toBeEnabled();
  await reviewCommand.click();

  await expect(commandPalette).toBeHidden();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
  await expect(page.getByText("Project review", { exact: true })).toBeVisible();
});

test("keeps product coverage and actions usable on mobile", async ({ page, request }) => {
  const { projectId, footprint } = await findDashboardWithProducts(request);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/projects/${projectId}`);

  await expect(page.getByText(`${footprint.represented_product_count} of ${footprint.captured_product_count} represented`)).toBeVisible();
  await expect(page.getByRole("button", { name: "Recalculate", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review project", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: footprint.products.at(-1)?.tool_key ?? "", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  const mobileNavigation = page.getByRole("dialog", { name: "Workspace navigation" });
  await mobileNavigation.getByRole("button", { name: "Open command palette", exact: true }).click();
  await expect(mobileNavigation).toBeHidden();
  const commandPalette = page.getByRole("dialog", { name: "Command palette" });
  await commandPalette.getByPlaceholder("Type a command, route, or workflow...").fill("Run AI review");
  await commandPalette.getByRole("button", { name: /Run AI review/ }).click();
  await expect(page.getByLabel("Governed AI review")).toBeVisible();
});
