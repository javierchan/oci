/* Focused presentation tests for the governed commercial review queue. */

import { describe, expect, it } from "vitest";

import {
  commercialCandidatePresentation,
  commercialReleaseCoverage,
  commercialReleaseScope,
} from "../lib/types";
import type { CommercialRelease } from "../lib/types";

describe("commercial candidate review presentation", () => {
  it("never presents generated pending work as approved", () => {
    const presentation = commercialCandidatePresentation("pending_review");

    expect(presentation.label).toBe("Generated · review required");
    expect(presentation.tone).toBe("warning");
  });

  it("presents partial releases without hiding excluded App SKUs", () => {
    const release: CommercialRelease = {
      id: "release-1",
      version: "commercial-1",
      status: "approved",
      validation_status: "passed",
      open_exception_count: 0,
      approved_by: "admin",
      approved_at: "2026-07-19T00:00:00Z",
      metadata: {
        part_numbers: ["B92072", "B92598"],
        available_mapping_parts: ["B92072", "B92598", "B88299"],
        excluded_mapping_parts: ["B88299"],
      },
    };

    expect(commercialReleaseScope(release)).toEqual({
      included: 2,
      available: 3,
      excluded: ["B88299"],
      isPartial: true,
    });
  });

  it("separates global catalog, quote-ready, blocked, and BOM-enabled coverage", () => {
    const release: CommercialRelease = {
      id: "release-global",
      version: "commercial-global-1",
      status: "approved",
      validation_status: "passed",
      open_exception_count: 0,
      approved_by: "admin",
      approved_at: "2026-07-19T00:00:00Z",
      metadata: {
        scope: "global_oci_catalog",
        catalog_count: 1182,
        quote_ready_count: 229,
        blocked_count: 953,
        included_mapping_count: 27,
        excluded_mapping_count: 5,
        catalog_part_numbers: ["B92072", "B92598", "B88299", "B88406"],
        quote_ready_part_numbers: ["B92072", "B92598"],
        blocked_part_numbers: ["B88299", "B88406"],
        app_mapping_parts: ["B92072", "B88299"],
      },
    };

    expect(commercialReleaseCoverage(release)).toEqual({
      scope: "global_oci_catalog",
      catalogTotal: 1182,
      quoteReady: 229,
      blocked: 953,
      appBomEnabled: 27,
      excludedMappings: 5,
      blockedParts: ["B88299", "B88406"],
      isGlobal: true,
    });
  });

  it("keeps historical App-scoped release metadata readable", () => {
    const release: CommercialRelease = {
      id: "release-legacy",
      version: "commercial-legacy-1",
      status: "approved",
      validation_status: "passed",
      open_exception_count: 0,
      approved_by: "admin",
      approved_at: "2026-07-19T00:00:00Z",
      metadata: {
        part_numbers: ["B92072", "B92598"],
        available_mapping_parts: ["B92072", "B92598", "B88299"],
        excluded_mapping_parts: ["B88299"],
      },
    };

    expect(commercialReleaseCoverage(release)).toMatchObject({
      scope: "legacy_app_scope",
      catalogTotal: 3,
      quoteReady: 2,
      blocked: 1,
      appBomEnabled: 2,
      excludedMappings: 1,
      isGlobal: false,
    });
  });

  it("labels approval as an explicit review decision", () => {
    const presentation = commercialCandidatePresentation("approved");

    expect(presentation.label).toBe("Explicitly approved");
    expect(presentation.tone).toBe("success");
  });

});
