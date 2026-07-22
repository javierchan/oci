import { describe, expect, it } from "vitest";

import { nextPricingAction } from "./pricing-workspace";

const ready = {
  sourceCount: 2,
  sourceValidationPassed: true,
  hasCommercialDocument: true,
  evidenceApproved: true,
  pendingDecisions: 0,
  openExceptions: 0,
  coverageTotal: 444,
  coverageApproved: 444,
  releaseCount: 1,
  approvedMappings: 64,
};

describe("pricing workspace next action", () => {
  it("starts with official evidence when validation has not passed", () => {
    expect(nextPricingAction({ ...ready, sourceValidationPassed: false }).view).toBe("sources");
  });

  it("routes incomplete catalog dispositions to certification", () => {
    expect(nextPricingAction({ ...ready, pendingDecisions: 12 }).view).toBe("decisions");
  });

  it("routes incomplete product capability to the product workspace", () => {
    expect(nextPricingAction({ ...ready, coverageApproved: 120 }).view).toBe("products");
  });

  it("finishes at published releases when all governance signals are ready", () => {
    expect(nextPricingAction(ready)).toMatchObject({
      view: "releases",
      title: "Commercial governance is ready for BOM use",
    });
  });
});
