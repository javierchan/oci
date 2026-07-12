/* Unit coverage for contextual-assistant route attachments. */

import { describe, expect, it } from "vitest";

import { deriveSupportRouteContext, sameSupportAttachment } from "./support-context";

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
    ["graph", "topology"],
    ["bom", "bom"],
    ["import", "import"],
  ] as const)("maps %s to %s context", (route, expected) => {
    expect(deriveSupportRouteContext(`/projects/${PROJECT_ID}/${route}`).attachment.attachment_type).toBe(expected);
  });

  it("deduplicates the same pinned App component", () => {
    const current = deriveSupportRouteContext(`/projects/${PROJECT_ID}/bom`).attachment;
    expect(sameSupportAttachment(current, { ...current })).toBe(true);
    expect(sameSupportAttachment(current, deriveSupportRouteContext(`/projects/${PROJECT_ID}/graph`).attachment)).toBe(false);
  });
});
