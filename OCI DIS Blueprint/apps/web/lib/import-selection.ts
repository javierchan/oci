/* Deterministic selection rules for persistent import-review context. */

import type { ImportBatch } from "@/lib/types";

export function selectImportReviewBatch(
  batches: ImportBatch[],
  requestedBatchId?: string,
): ImportBatch | null {
  if (requestedBatchId) {
    return batches.find((batch) => batch.id === requestedBatchId) ?? null;
  }

  return batches.find((batch) => batch.status === "mapping_review") ?? null;
}
