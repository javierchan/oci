import { describe, expect, it } from "vitest";

import { selectImportReviewBatch } from "./import-selection";
import type { ImportBatch } from "./types";

function batch(id: string, status: ImportBatch["status"]): ImportBatch {
  return {
    id,
    project_id: "project-1",
    filename: `${id}.xlsx`,
    parser_version: "3.1.0",
    status,
    candidate_count: 10,
    loaded_count: status === "completed" ? 10 : 0,
    excluded_count: 0,
    tbq_y_count: 10,
    tbq_n_count: 0,
    source_row_count: 10,
    header_map: null,
    error_details: null,
    intake_mode: status === "mapping_review" ? "external_mapping" : "official_template",
    mapping_contract: null,
    mapping_profile_id: null,
    mapping_reviewed_by: null,
    mapping_reviewed_at: null,
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:00:00Z",
  };
}

describe("selectImportReviewBatch", () => {
  it("keeps an explicitly requested historical batch selected", () => {
    const batches = [batch("latest", "completed"), batch("requested", "mapping_review")];

    expect(selectImportReviewBatch(batches, "requested")?.id).toBe("requested");
  });

  it("restores the newest unresolved mapping review after navigation", () => {
    const batches = [
      batch("latest-completed", "completed"),
      batch("newest-review", "mapping_review"),
      batch("older-review", "mapping_review"),
    ];

    expect(selectImportReviewBatch(batches)?.id).toBe("newest-review");
  });

  it("does not open a completed import automatically", () => {
    expect(selectImportReviewBatch([batch("completed", "completed")])).toBeNull();
  });
});
