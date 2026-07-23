/* Playwright coverage for the persistent, session-isolated App support assistant. */

import { expect, test } from "@playwright/test";

type ProjectList = {
  projects: Array<{
    id: string;
    name: string;
    status: string;
    project_metadata: Record<string, unknown> | null;
  }>;
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

function selectPersistentProject(projects: ProjectList["projects"]) {
  const activeProjects = projects.filter((candidate) => candidate.status === "active");
  return (
    activeProjects.find(
      (candidate) => candidate.project_metadata?.seed_type === "synthetic-enterprise",
    ) ??
    activeProjects.find(
      (candidate) => !String(candidate.project_metadata?.seed_type ?? "").startsWith("synthetic-smoke"),
    )
  );
}

test("keeps contextual support available and bounded across App navigation", async ({ page, request }) => {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects/`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  // Other specs create and delete smoke projects concurrently. Use the retained
  // enterprise fixture so assistant persistence cannot race fixture cleanup.
  const project = selectPersistentProject(projects.projects);
  expect(project).toBeDefined();
  if (!project) throw new Error("E2E requires one persistent active project");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projects/${project.id}`);
  await page.getByRole("button", { name: "Open OCI DIS App Assistant", exact: true }).click();

  const assistant = page.getByRole("dialog", { name: "OCI DIS App Assistant", exact: true });
  await expect(assistant).toBeVisible();
  await expect(
    assistant.getByText("General App help · context: Project Dashboard", { exact: true }),
  ).toBeVisible();
  await assistant.getByRole("button", { name: "Add context", exact: true }).click();
  const currentContextGroup = assistant.getByText("Current view", { exact: true }).locator("..");
  await currentContextGroup.getByRole("button").click();
  await expect(assistant.getByRole("button", { name: "Add context (1)", exact: true })).toBeVisible();
  await expect(assistant.getByTitle("Remove Project Dashboard context")).toBeVisible();
  await assistant.getByRole("button", { name: "Close context picker", exact: true }).click();

  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  await input.fill("What is the weather today?");
  await assistant.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    assistant.getByText("That request is outside OCI DIS Architect's scope", { exact: false }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(assistant.getByText("BOM & Cost", { exact: false })).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "BOM & Cost", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project.id}/bom$`));
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();
  await expect(
    assistant.getByText("General App help · context: BOM & Cost", { exact: true }),
  ).toBeVisible();

  const addContextBox = await assistant.getByRole("button", { name: "Add context", exact: true }).boundingBox();
  const sendBox = await assistant.getByRole("button", { name: "Send message", exact: true }).boundingBox();
  expect(addContextBox).not.toBeNull();
  expect(sendBox).not.toBeNull();
  expect((addContextBox?.x ?? 0) + (addContextBox?.width ?? 0)).toBeLessThanOrEqual(sendBox?.x ?? 0);

  await assistant.getByRole("button", { name: "Clear assistant history", exact: true }).click();
  const clearDialog = page.getByRole("alertdialog", { name: "Clear assistant history?", exact: true });
  await expect(clearDialog).toBeVisible();
  await clearDialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();

  await assistant.getByRole("button", { name: "Clear assistant history", exact: true }).click();
  await clearDialog.getByRole("button", { name: "Clear history", exact: true }).click();
  await expect(clearDialog).toBeHidden();
  await expect(assistant.getByText("Hi. What are you working through?", { exact: true })).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toHaveCount(0);
  await expect(assistant.getByRole("button", { name: "Clear assistant history", exact: true })).toBeDisabled();

  await page.reload();
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText("Hi. What are you working through?", { exact: true })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  const box = await assistant.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(844);
  await expect(assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true })).toBeVisible();
});

test("resolves an unambiguous project dossier from a global App route", async ({ page, request }) => {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects/`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  const activeProjects = projects.projects.filter((candidate) => candidate.status === "active");
  test.skip(activeProjects.length !== 1, "This continuity check requires exactly one active project.");
  const [project] = activeProjects;

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/admin/agents");
  await page.getByRole("button", { name: "Open OCI DIS App Assistant", exact: true }).click();

  const assistant = page.getByRole("dialog", { name: "OCI DIS App Assistant", exact: true });
  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  const send = assistant.getByRole("button", { name: "Send message", exact: true });

  await input.fill("¿Cuántos proyectos tenemos en la App?");
  await send.click();
  await expect(assistant.getByRole("link", { name: "Projects", exact: true })).toBeVisible({ timeout: 60_000 });

  await input.fill("¿Cuál es el precio total de este proyecto?");
  await send.click();
  await expect(assistant.getByRole("link", { name: "BOM & Cost", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(assistant.getByRole("link", { name: project.name, exact: true })).toBeVisible();
  await expect(assistant).toContainText(/USD|no tiene un BOM calculado/);
  await expect(assistant).not.toContainText("Open the relevant workspace or add its context");
});
