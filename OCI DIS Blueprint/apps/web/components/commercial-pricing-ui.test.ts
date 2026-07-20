/* Focused presentation tests for the governed commercial review queue. */

import { describe, expect, it } from "vitest";

import {
  commercialCandidatePresentation,
  commercialReleaseCoverage,
  commercialReleaseScope,
  filterCommercialCandidates,
} from "../lib/types";
import type { CommercialCandidate, CommercialRelease } from "../lib/types";

const candidates: CommercialCandidate[] = [
  {
    id: "candidate-1",
    part_number: "B95701",
    service_id: "AUTONOMOUS_DATABASE",
    family_key: "ecpu_per_hour",
    classification: "measured",
    confidence: 0.98,
    status: "pending_review",
    generator_version: "commercial-product-factory-1.2.0",
    rule_status: "ready_for_review",
    rule_fixture_status: "passed",
    identity: {
      display_name: "Oracle Autonomous AI Lakehouse - ECPU",
      service_category: "Oracle Data Management Cloud Services",
      product_hierarchy: ["Section 1 - Universal Credits", "Oracle Autonomous Database"],
      product_paths: [["Section 1 - Universal Credits", "Oracle Autonomous Database"]],
      official_location_count: 1,
      structured_product: {},
    },
    commercial_term: {
      service_name: "Oracle Autonomous AI Lakehouse - ECPU",
      metric_name: "ECPU Per Hour",
      price_type: "HOUR",
      commercial_prices: [],
      additional_information: "Partial ECPU hours are billed per second.",
      notes: null,
      source_sheet: "Oracle PaaS and IaaS Price List",
      source_row: 29,
      constraints: [],
    },
    composition: [],
    proposed_mapping: { quantity_behavior: "hourly", minimum_quantity: "2" },
    reasons: ["Official document term present"],
  },
  {
    id: "candidate-2",
    part_number: "B92072",
    service_id: "API_GATEWAY",
    family_key: "api_call_millions",
    classification: "measured",
    confidence: 0.92,
    status: "approved",
    generator_version: "commercial-product-factory-1.2.0",
    rule_status: "approved",
    rule_fixture_status: "passed",
    identity: {
      display_name: "Oracle Cloud Infrastructure API Gateway",
      service_category: "Oracle Cloud Infrastructure Services",
      product_hierarchy: ["Section 1 - Universal Credits", "API Management"],
      product_paths: [["Section 1 - Universal Credits", "API Management"]],
      official_location_count: 1,
      structured_product: {},
    },
    commercial_term: {
      service_name: "Oracle Cloud Infrastructure API Gateway",
      metric_name: "1,000,000 API Calls Per Month",
      price_type: "MONTH",
      commercial_prices: [],
      additional_information: null,
      notes: null,
      source_sheet: "Oracle PaaS and IaaS Price List",
      source_row: 42,
      constraints: [],
    },
    composition: [],
    proposed_mapping: { quote_rounding: "ceiling" },
    reasons: ["Existing approved mapping matched by exact part number"],
  },
];

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

  it("searches across SKU, service, family, rationale, and proposed behavior", () => {
    expect(filterCommercialCandidates(candidates, "B95701", "all")).toHaveLength(1);
    expect(filterCommercialCandidates(candidates, "api gateway", "all")[0]?.id).toBe("candidate-2");
    expect(filterCommercialCandidates(candidates, "API Management", "all")[0]?.id).toBe("candidate-2");
    expect(filterCommercialCandidates(candidates, "ECPU Per Hour", "all")[0]?.id).toBe("candidate-1");
    expect(filterCommercialCandidates(candidates, "ceiling", "all")[0]?.id).toBe("candidate-2");
    expect(filterCommercialCandidates(candidates, "official document", "pending_review")[0]?.id).toBe("candidate-1");
  });

  it("applies the explicit status filter without mutating the queue", () => {
    const approved = filterCommercialCandidates(candidates, "", "approved");

    expect(approved.map((candidate) => candidate.id)).toEqual(["candidate-2"]);
    expect(candidates).toHaveLength(2);
  });
});
