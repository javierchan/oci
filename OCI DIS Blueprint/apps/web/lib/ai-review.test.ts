/* Regression coverage for human-readable architecture review evidence. */

import { describe, expect, it } from "vitest";

import { formatAiReviewDriftValue, isAiReviewLayoutMetadataOnlyDrift } from "./ai-review";

describe("formatAiReviewDriftValue", () => {
  it("summarizes historical canvas JSON as governed overlays", () => {
    const value = JSON.stringify({
      v: 3,
      coreToolKeys: ["OCI Streaming", "OIC Gen3"],
      overlayKeys: ["OCI Events"],
      nodes: [],
      edges: [],
    });

    expect(formatAiReviewDriftValue("additional_tools_overlays", value)).toBe("OCI Events");
  });

  it("preserves ordinary evidence values", () => {
    expect(formatAiReviewDriftValue("selected_pattern", "#02")).toBe("#02");
    expect(formatAiReviewDriftValue("core_tools", null)).toBe("Not set");
  });

  it("identifies historical canvas layout changes without governed overlay drift", () => {
    const planned = JSON.stringify({
      v: 3,
      overlayKeys: ["OCI Events"],
      nodes: [{ instanceId: "n1", x: 200, y: 120 }],
    });
    const actual = JSON.stringify({
      v: 4,
      overlayKeys: ["OCI Events"],
      nodes: [{ instanceId: "n1", x: 322, y: 217 }],
      endpointPositions: { source: { x: 40, y: 232 } },
    });

    expect(isAiReviewLayoutMetadataOnlyDrift("additional_tools_overlays", planned, actual)).toBe(true);
  });

  it("keeps a real overlay change actionable", () => {
    const planned = JSON.stringify({ v: 3, overlayKeys: ["OCI Events"] });
    const actual = JSON.stringify({ v: 4, overlayKeys: ["OCI API Gateway"] });

    expect(isAiReviewLayoutMetadataOnlyDrift("additional_tools_overlays", planned, actual)).toBe(false);
  });
});
