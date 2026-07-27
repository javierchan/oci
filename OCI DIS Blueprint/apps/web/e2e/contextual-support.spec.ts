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

type ProviderStatus = {
  api_key_configured: boolean;
  project_configured: boolean;
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
  const providerResponse = await request.get(`${apiBase}/api/v1/agents/provider-status`);
  expect(providerResponse.ok()).toBe(true);
  const providerStatus = (await providerResponse.json()) as ProviderStatus;
  const providerConfigured = providerStatus.api_key_configured && providerStatus.project_configured;

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
    assistant.getByText("OCI-grounded · context: Project Dashboard", { exact: true }),
  ).toBeVisible();
  await expect(assistant.getByText("Conversation memory", { exact: false })).toHaveCount(0);
  await assistant.getByRole("button", { name: "Add context", exact: true }).click();
  const currentContextGroup = assistant.getByText("Current view", { exact: true }).locator("..");
  await currentContextGroup.getByRole("button").click();
  await expect(assistant.getByRole("button", { name: "Add context (1)", exact: true })).toBeVisible();
  await expect(assistant.getByTitle("Remove Project Dashboard context")).toBeVisible();
  await assistant.getByRole("button", { name: "Close context picker", exact: true }).click();

  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  await input.fill("What is the weather today?");
  await assistant.getByRole("button", { name: "Send message", exact: true }).click();
  if (providerConfigured) {
    const redirectedMessage = assistant.locator(
      '[data-support-message-role="assistant"][data-support-message-status="completed"]',
    );
    await expect(redirectedMessage).toBeVisible({ timeout: 30_000 });
    await expect(redirectedMessage).toContainText(/OCI DIS|integration|architecture|pricing|BOM/i);
    expect(await redirectedMessage.getByRole("link").count()).toBeGreaterThan(0);
  } else {
    const failedMessage = assistant.locator(
      '[data-support-message-role="assistant"][data-support-message-status="failed"]',
    );
    await expect(failedMessage).toBeVisible({ timeout: 30_000 });
    await expect(failedMessage.getByRole("alert")).toContainText("Assistant response failed");
    await expect(failedMessage.locator("a")).toHaveCount(0);
  }
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Add context (1)", exact: true })).toBeVisible();
  await expect(assistant.getByTitle("Remove Project Dashboard context")).toBeVisible();

  await page.getByRole("link", { name: "BOM & Cost", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project.id}/bom$`));
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();
  await expect(
    assistant.getByText(
      providerConfigured
        ? "OCI-grounded · context: BOM & Cost"
        : "Last response failed · no fallback used",
      { exact: true },
    ),
  ).toBeVisible();

  const addContextBox = await assistant.getByRole("button", { name: "Add context (1)", exact: true }).boundingBox();
  const sendBox = await assistant.getByRole("button", { name: "Send message", exact: true }).boundingBox();
  expect(addContextBox).not.toBeNull();
  expect(sendBox).not.toBeNull();
  expect((addContextBox?.x ?? 0) + (addContextBox?.width ?? 0)).toBeLessThanOrEqual(sendBox?.x ?? 0);

  await page.reload();
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Add context (1)", exact: true })).toBeVisible();
  await expect(assistant.getByTitle("Remove Project Dashboard context")).toBeVisible();

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
  await expect(assistant.getByRole("button", { name: "Add context", exact: true })).toBeVisible();
  await expect(assistant.getByTitle("Remove Project Dashboard context")).toHaveCount(0);
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

test("answers a global project inventory question with real OCI synthesis", async ({ page, request }) => {
  const providerResponse = await request.get(`${apiBase}/api/v1/agents/provider-status`);
  expect(providerResponse.ok()).toBe(true);
  const providerStatus = (await providerResponse.json()) as ProviderStatus;
  test.skip(
    !providerStatus.api_key_configured || !providerStatus.project_configured,
    "A real OCI provider response requires the governed key mount and Project OCID.",
  );

  const projectsResponse = await request.get(`${apiBase}/api/v1/projects/`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  const activeProjects = projects.projects.filter((candidate) => candidate.status === "active");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/admin/agents");
  await page.getByRole("button", { name: "Open OCI DIS App Assistant", exact: true }).click();

  const assistant = page.getByRole("dialog", { name: "OCI DIS App Assistant", exact: true });
  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  const send = assistant.getByRole("button", { name: "Send message", exact: true });

  await input.fill("¿Cuántos proyectos tenemos en la App?");
  await send.click();
  await expect(assistant.getByRole("link", { name: "Projects", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(assistant).toContainText(String(activeProjects.length));
});

test("resolves an unambiguous project dossier from a global App route", async ({ page, request }) => {
  const providerResponse = await request.get(`${apiBase}/api/v1/agents/provider-status`);
  expect(providerResponse.ok()).toBe(true);
  const providerStatus = (await providerResponse.json()) as ProviderStatus;
  test.skip(
    !providerStatus.api_key_configured || !providerStatus.project_configured,
    "A real OCI provider response requires the governed key mount and Project OCID.",
  );

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
  await input.fill("¿Cuál es el precio total de este proyecto?");
  await send.click();
  await expect(assistant.getByRole("link", { name: "BOM & Cost", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(assistant.getByRole("link", { name: project.name, exact: true })).toBeVisible();
  await expect(assistant).toContainText(/USD|no tiene un BOM calculado/);
  await expect(assistant).not.toContainText("Open the relevant workspace or add its context");
});

test("fails closed for an in-scope question when OCI is not configured", async ({ page, request }) => {
  const providerResponse = await request.get(`${apiBase}/api/v1/agents/provider-status`);
  expect(providerResponse.ok()).toBe(true);
  const providerStatus = (await providerResponse.json()) as ProviderStatus;
  test.skip(
    providerStatus.api_key_configured && providerStatus.project_configured,
    "This contract applies only to the provider-free baseline CI environment.",
  );

  const projectsResponse = await request.get(`${apiBase}/api/v1/projects/`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  const project = selectPersistentProject(projects.projects);
  expect(project).toBeDefined();
  if (!project) throw new Error("E2E requires one persistent active project");

  await page.goto(`/projects/${project.id}`);
  await page.getByRole("button", { name: "Open OCI DIS App Assistant", exact: true }).click();
  const assistant = page.getByRole("dialog", { name: "OCI DIS App Assistant", exact: true });
  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  await input.fill("How should I review this project?");
  await assistant.getByRole("button", { name: "Send message", exact: true }).click();

  const failedMessage = assistant.locator(
    '[data-support-message-role="assistant"][data-support-message-status="failed"]',
  );
  await expect(failedMessage).toBeVisible({ timeout: 60_000 });
  await expect(failedMessage.getByRole("alert")).toContainText("Assistant response failed");
  await expect(
    assistant.getByText("Last response failed · no fallback used", { exact: true }),
  ).toBeVisible();
  await expect(failedMessage.locator("a")).toHaveCount(0);
});
