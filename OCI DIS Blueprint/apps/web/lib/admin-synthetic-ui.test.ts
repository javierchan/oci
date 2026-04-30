/* Focused Vitest coverage for admin synthetic UI-state helpers. */

import { describe, expect, it } from "vitest";

import {
  buildSyntheticJobFormState,
  canCleanupSyntheticJob,
  canRetrySyntheticJob,
  getSyntheticCleanupPolicyLabel,
  getSyntheticTargetSplitMessage,
  isSyntheticTargetMismatch,
  resolveSelectedSyntheticPreset,
  resolveSyntheticJobCleanupPolicy,
  resolveSyntheticJobStatusClasses,
  usesEphemeralAutoCleanup,
} from "./admin-synthetic-ui";
import type { SyntheticGenerationJob, SyntheticGenerationPreset } from "./types";

function preset(
  overrides: Partial<SyntheticGenerationPreset>,
): SyntheticGenerationPreset {
  return {
    code: "enterprise-default",
    label: "Enterprise Reference",
    description: "Enterprise-scale governed run.",
    project_name: "Synthetic Enterprise Project",
    seed_value: 20260416,
    target_catalog_size: 480,
    min_distinct_systems: 70,
    import_target: 420,
    manual_target: 60,
    excluded_import_target: 36,
    include_justifications: true,
    include_exports: true,
    include_design_warnings: true,
    cleanup_policy: "manual",
    ...overrides,
  };
}

function job(overrides: Partial<SyntheticGenerationJob>): SyntheticGenerationJob {
  return {
    id: "job-1",
    requested_by: "web-admin",
    status: "pending",
    preset_code: "enterprise-default",
    input_payload: {},
    normalized_payload: { cleanup_policy: "manual" },
    project_id: "project-1",
    project_name: "Synthetic Enterprise Project",
    seed_value: 20260416,
    catalog_target: 480,
    manual_target: 60,
    import_target: 420,
    excluded_import_target: 36,
    result_summary: null,
    validation_results: null,
    artifact_manifest: null,
    error_details: null,
    started_at: null,
    finished_at: null,
    created_at: "2026-04-28T20:24:59.600092Z",
    updated_at: "2026-04-28T20:24:59.600095Z",
    ...overrides,
  };
}

describe("admin-synthetic-ui", () => {
  it("builds smoke form state from the preset contract", () => {
    const smokePreset = preset({
      code: "ephemeral-smoke",
      label: "Ephemeral Smoke Validation",
      target_catalog_size: 18,
      min_distinct_systems: 12,
      import_target: 12,
      manual_target: 6,
      excluded_import_target: 2,
      include_justifications: false,
      include_exports: false,
      include_design_warnings: false,
      cleanup_policy: "ephemeral_auto_cleanup",
    });

    const formState = buildSyntheticJobFormState(smokePreset);

    expect(formState.preset_code).toBe("ephemeral-smoke");
    expect(formState.cleanup_policy).toBe("ephemeral_auto_cleanup");
    expect(formState.target_catalog_size).toBe(18);
    expect(formState.import_target).toBe(12);
    expect(formState.manual_target).toBe(6);
  });

  it("resolves the selected preset and falls back to the first preset", () => {
    const enterprisePreset = preset({});
    const smokePreset = preset({
      code: "ephemeral-smoke",
      label: "Ephemeral Smoke Validation",
      cleanup_policy: "ephemeral_auto_cleanup",
    });
    const presets = [enterprisePreset, smokePreset];

    expect(resolveSelectedSyntheticPreset(presets, "ephemeral-smoke")?.label).toBe(
      "Ephemeral Smoke Validation",
    );
    expect(resolveSelectedSyntheticPreset(presets, "missing")?.label).toBe(
      "Enterprise Reference",
    );
    expect(resolveSelectedSyntheticPreset([], "missing")).toBeNull();
  });

  it("detects target mismatches and returns the correct operator guidance", () => {
    const alignedState = buildSyntheticJobFormState(
      preset({
        code: "ephemeral-smoke",
        target_catalog_size: 18,
        import_target: 12,
        manual_target: 6,
        cleanup_policy: "ephemeral_auto_cleanup",
      }),
    );
    const mismatchedState = {
      ...alignedState,
      manual_target: 5,
    };

    expect(isSyntheticTargetMismatch(alignedState)).toBe(false);
    expect(getSyntheticTargetSplitMessage(alignedState)).toBe(
      "Split is aligned with the governed catalog target.",
    );
    expect(isSyntheticTargetMismatch(mismatchedState)).toBe(true);
    expect(getSyntheticTargetSplitMessage(mismatchedState)).toBe(
      "Adjust the split so it matches the catalog target before submitting.",
    );
  });

  it("derives the cleanup policy and allowed actions from the job state", () => {
    const cleanedUpSmokeJob = job({
      status: "cleaned_up",
      preset_code: "ephemeral-smoke",
      project_id: null,
      normalized_payload: { cleanup_policy: "ephemeral_auto_cleanup" },
    });
    const failedJob = job({
      status: "failed",
      error_details: { detail: "Synthetic generation failed." },
    });

    expect(resolveSyntheticJobCleanupPolicy(cleanedUpSmokeJob)).toBe(
      "ephemeral_auto_cleanup",
    );
    expect(usesEphemeralAutoCleanup(resolveSyntheticJobCleanupPolicy(cleanedUpSmokeJob))).toBe(
      true,
    );
    expect(getSyntheticCleanupPolicyLabel("ephemeral_auto_cleanup")).toBe(
      "Ephemeral auto-cleanup",
    );

    expect(canRetrySyntheticJob(cleanedUpSmokeJob)).toBe(false);
    expect(canCleanupSyntheticJob(cleanedUpSmokeJob)).toBe(false);
    expect(canRetrySyntheticJob(failedJob)).toBe(true);
    expect(canCleanupSyntheticJob(failedJob)).toBe(true);
  });

  it("maps status classes for cleaned-up and failure states", () => {
    expect(resolveSyntheticJobStatusClasses("cleaned_up")).toContain("border-slate-200");
    expect(resolveSyntheticJobStatusClasses("failed")).toContain("border-rose-200");
    expect(resolveSyntheticJobStatusClasses("pending")).toContain("border-amber-200");
  });
});
