/* Unit coverage for contextual-assistant route attachments. */

import { describe, expect, it } from "vitest";

import { buildSupportContextCatalog, deriveSupportRouteContext, sameSupportAttachment } from "./support-context";
import type { Project } from "./types";

const PROJECT_ID = "20a23466-dd52-4d5a-a3f5-1bc66f659c78";
const INTEGRATION_ID = "55d40a1b-bad5-4426-af01-606074e3b857";

describe("contextual support route context", () => {
  it("derives integration identity from the detail route", () => {
    const context = deriveSupportRouteContext(`/projects/${PROJECT_ID}/catalog/${INTEGRATION_ID}`);
    expect(context.pageTitle).toBe("Integration Detail");
    expect(context.projectId).toBe(PROJECT_ID);
    expect(context.integrationId).toBe(INTEGRATION_ID);
    expect(context.attachment.attachment_type).toBe("integration");
  });

  it.each([
    ["map", "topology"],
    ["graph", "topology"],
    ["bom", "bom"],
    ["import", "import"],
  ] as const)("maps %s to %s context", (route, expected) => {
    expect(deriveSupportRouteContext(`/projects/${PROJECT_ID}/${route}`).attachment.attachment_type).toBe(expected);
  });

  it("deduplicates the same pinned App component", () => {
    const current = deriveSupportRouteContext(`/projects/${PROJECT_ID}/bom`).attachment;
    expect(sameSupportAttachment(current, { ...current })).toBe(true);
    expect(sameSupportAttachment(current, deriveSupportRouteContext(`/projects/${PROJECT_ID}/map`).attachment)).toBe(false);
  });

  it("lists global governance and every project workspace as selectable context", () => {
    const project: Project = {
      id: PROJECT_ID,
      name: "Enterprise Integration",
      customer_name: "ACME Inc.",
      owner_id: "architect",
      description: null,
      status: "active",
      project_metadata: null,
      created_at: "2026-07-21T00:00:00Z",
      updated_at: "2026-07-21T00:00:00Z",
    };
    const options = buildSupportContextCatalog(
      [project],
      deriveSupportRouteContext("/projects").attachment,
    );

    expect(options.some((item) => item.attachment.href === "/admin/pricing")).toBe(true);
    expect(options.some((item) => item.label === "Enterprise Integration · Integration Topology")).toBe(true);
    expect(options.some((item) => item.label === "Enterprise Integration · BOM & Cost")).toBe(true);
    expect(options.filter((item) => item.attachment.href === "/projects")).toHaveLength(1);
  });
});
