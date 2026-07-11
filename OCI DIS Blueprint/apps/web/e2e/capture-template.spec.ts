/* Playwright coverage for the governed offline-capture workbook download. */

import { expect, test } from "@playwright/test";

type ProjectSummary = {
  id: string;
};

type ProjectList = {
  projects: ProjectSummary[];
};

type CaptureTemplateMetadata = {
  template_version: string;
  filename: string;
  pattern_count: number;
  service_product_count: number;
  capture_row_limit: number;
};

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

test("downloads the governed offline-capture workbook from Import", async ({ page, request }) => {
  const projectsResponse = await request.get(`${apiBase}/api/v1/projects?page=1&page_size=1`);
  expect(projectsResponse.ok()).toBe(true);
  const projects = (await projectsResponse.json()) as ProjectList;
  expect(projects.projects, "the production E2E environment must contain a project").not.toHaveLength(0);

  const metadataResponse = await request.get(`${apiBase}/api/v1/exports/template/metadata`);
  expect(metadataResponse.ok()).toBe(true);
  const metadata = (await metadataResponse.json()) as CaptureTemplateMetadata;

  await page.goto(`/projects/${projects.projects[0].id}/import`);

  await expect(page.getByText(`Template v${metadata.template_version}`, { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      `${metadata.pattern_count} patterns · ${metadata.service_product_count} OCI services · ${metadata.capture_row_limit} capture rows`,
      { exact: true },
    ),
  ).toBeVisible();

  const downloadLink = page.getByRole("link", { name: "Download Template (.xlsx)", exact: true });
  await expect(downloadLink).toHaveAttribute(
    "href",
    `${apiBase}/api/v1/exports/template/xlsx`,
  );

  const downloadPromise = page.waitForEvent("download");
  await downloadLink.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(metadata.filename);
  await download.delete();
});
