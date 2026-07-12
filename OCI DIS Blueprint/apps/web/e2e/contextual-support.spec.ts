/* Playwright coverage for the persistent, session-isolated App support assistant. */

import { expect, test } from "@playwright/test";

type ProjectList = { projects: Array<{ id: string; status: string }> };

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

test("keeps contextual support available and bounded across App navigation", async ({ page, request }) => {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  const project = projects.projects.find((candidate) => candidate.status === "active") ?? projects.projects[0];
  expect(project).toBeDefined();
  if (!project) throw new Error("E2E requires one project");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projects/${project.id}`);
  await page.getByRole("button", { name: "Open OCI DIS App Assistant", exact: true }).click();

  const assistant = page.getByRole("dialog", { name: "OCI DIS App Assistant", exact: true });
  await expect(assistant).toBeVisible();
  await assistant.getByRole("button", { name: "Attach view", exact: true }).click();
  await expect(assistant.getByRole("button", { name: "Attached", exact: true })).toBeDisabled();

  const input = assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true });
  await input.fill("What is the weather today?");
  await assistant.getByRole("button", { name: "Send", exact: true }).click();
  await expect(assistant.getByText("I can only help with OCI DIS Architect", { exact: false })).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "BOM & Cost", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project.id}/bom$`));
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText("What is the weather today?", { exact: true })).toBeVisible();
  await expect(assistant.getByText("Context: BOM & Cost", { exact: true })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  const box = await assistant.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(844);
  await expect(assistant.getByRole("textbox", { name: "Ask OCI DIS App Assistant", exact: true })).toBeVisible();
});
