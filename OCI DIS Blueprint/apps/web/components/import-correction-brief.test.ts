/* Regression coverage for structured Import Correction Agent briefs. */

import { describe, expect, it } from "vitest";

import type { AgentRun } from "@/lib/types";

import {
  parseImportCorrectionBrief,
  selectLatestImportCorrectionSessionRun,
} from "./import-correction-brief";

const SYNTHETIC_BRIEF = {
  explanation: "Two governed fields need review before approval.",
  deviations: [
    {
      source_field: "Source Pattern",
      target_field: "selected_pattern",
      issue: "Governed pattern is missing",
      evidence: "The synthetic proposal contains no selected pattern.",
      proposed_action: "request evidence",
      confidence: "high",
    },
  ],
  excluded_fields: ["Synthetic formula column"],
  required_decisions: ["Confirm the governed pattern."],
};

describe("Import Correction Agent brief normalization", () => {
  it("parses the governed JSON contract into bounded presentation data", () => {
    const parsed = parseImportCorrectionBrief(JSON.stringify(SYNTHETIC_BRIEF));

    expect(parsed?.explanation).toBe(SYNTHETIC_BRIEF.explanation);
    expect(parsed?.deviations).toHaveLength(1);
    expect(parsed?.deviations[0]?.confidence).toBe("high");
    expect(parsed?.excluded_fields).toEqual(["Synthetic formula column"]);
    expect(parsed?.required_decisions).toEqual([
      "Confirm the governed pattern.",
    ]);
  });

  it("accepts historical fenced or prose-wrapped JSON", () => {
    const wrapped = `Review follows.\n\`\`\`json\n${JSON.stringify(
      SYNTHETIC_BRIEF,
    )}\n\`\`\`\nEnd of review.`;

    expect(parseImportCorrectionBrief(wrapped)?.deviations).toHaveLength(1);
  });

  it("rejects unstructured and incomplete payloads", () => {
    expect(parseImportCorrectionBrief("Plain provider prose.")).toBeNull();
    expect(parseImportCorrectionBrief('{"deviations":[]}')).toBeNull();
  });

  it("restores only the latest completed session-level import run", () => {
    const baseRun: AgentRun = {
      id: "base-run",
      agent_type: "import_quality",
      definition_version: "test",
      project_id: "project-1",
      integration_id: null,
      requested_by: "test-user",
      status: "completed",
      context: { external_capture_session_id: "session-1" },
      result: null,
      error: null,
      model: null,
      provider_response_id: null,
      opc_request_id: null,
      input_tokens: null,
      output_tokens: null,
      step_count: 0,
      max_steps: 4,
      cancel_requested: false,
      started_at: null,
      finished_at: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      steps: [],
      approvals: [],
    };
    const draftRun = {
      ...baseRun,
      id: "draft-run",
      context: {
        external_capture_session_id: "session-1",
        external_capture_draft_id: "draft-1",
      },
    };
    const sessionRun = { ...baseRun, id: "session-run" };

    expect(
      selectLatestImportCorrectionSessionRun(
        [draftRun, sessionRun],
        "session-1",
      )?.id,
    ).toBe("session-run");
  });
});
