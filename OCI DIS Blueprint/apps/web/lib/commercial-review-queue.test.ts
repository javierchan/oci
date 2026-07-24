import { describe, expect, it } from "vitest";

import {
  commercialReviewEntityLabel,
  commercialReviewPriorityPresentation,
  commercialReviewWorkflowLabel,
  toDateTimeLocal,
} from "@/lib/commercial-review-queue";

describe("commercial review queue presentation", () => {
  it("uses explicit operational labels without implying approval", () => {
    expect(commercialReviewEntityLabel("mapping_candidate")).toBe("SKU mapping");
    expect(commercialReviewWorkflowLabel("waiting_evidence")).toBe(
      "Waiting for evidence",
    );
    expect(commercialReviewWorkflowLabel("in_progress")).not.toContain("Approved");
  });

  it("distinguishes every deterministic priority tier", () => {
    expect(commercialReviewPriorityPresentation("urgent").label).toBe("Urgent");
    expect(commercialReviewPriorityPresentation("high").label).toBe("High");
    expect(commercialReviewPriorityPresentation("normal").label).toBe("Normal");
    expect(commercialReviewPriorityPresentation("low").label).toBe("Low");
  });

  it("returns a browser-local datetime control value", () => {
    expect(toDateTimeLocal(null)).toBe("");
    expect(toDateTimeLocal("invalid")).toBe("");
    expect(toDateTimeLocal("2026-07-23T12:30:00Z")).toMatch(
      /^2026-07-23T\d{2}:30$/,
    );
  });
});
