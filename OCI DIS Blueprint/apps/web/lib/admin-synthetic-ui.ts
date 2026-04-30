/* Shared UI-state helpers for the admin synthetic lab surfaces. */

import type {
  SyntheticGenerationJob,
  SyntheticGenerationJobRequest,
  SyntheticGenerationPreset,
} from "./types";

export type SyntheticJobFormState = Required<SyntheticGenerationJobRequest>;

export function buildSyntheticJobFormState(
  preset: SyntheticGenerationPreset,
): SyntheticJobFormState {
  return {
    project_name: preset.project_name,
    preset_code: preset.code,
    target_catalog_size: preset.target_catalog_size,
    min_distinct_systems: preset.min_distinct_systems,
    import_target: preset.import_target,
    manual_target: preset.manual_target,
    excluded_import_target: preset.excluded_import_target,
    include_justifications: preset.include_justifications,
    include_exports: preset.include_exports,
    include_design_warnings: preset.include_design_warnings,
    cleanup_policy: preset.cleanup_policy,
    seed_value: preset.seed_value,
  };
}

export function resolveSyntheticJobStatusClasses(status: string): string {
  switch (status) {
    case "completed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300";
    case "running":
      return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300";
    case "failed":
      return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300";
    case "cleaned_up":
      return "border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300";
    default:
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300";
  }
}

export function resolveSelectedSyntheticPreset(
  presets: SyntheticGenerationPreset[],
  presetCode: string | undefined,
): SyntheticGenerationPreset | null {
  return presets.find((preset) => preset.code === presetCode) ?? presets[0] ?? null;
}

export function isSyntheticTargetMismatch(
  formState: SyntheticJobFormState | null,
): boolean {
  if (formState === null) {
    return false;
  }
  return formState.import_target + formState.manual_target !== formState.target_catalog_size;
}

export function getSyntheticTargetSplitMessage(
  formState: SyntheticJobFormState,
): string {
  if (isSyntheticTargetMismatch(formState)) {
    return "Adjust the split so it matches the catalog target before submitting.";
  }
  return "Split is aligned with the governed catalog target.";
}

export function usesEphemeralAutoCleanup(
  cleanupPolicy: string | null | undefined,
): boolean {
  return cleanupPolicy === "ephemeral_auto_cleanup";
}

export function resolveSyntheticJobCleanupPolicy(
  job: SyntheticGenerationJob | null,
): "manual" | "ephemeral_auto_cleanup" {
  const value = job?.normalized_payload?.cleanup_policy;
  return usesEphemeralAutoCleanup(typeof value === "string" ? value : null)
    ? "ephemeral_auto_cleanup"
    : "manual";
}

export function getSyntheticCleanupPolicyLabel(
  cleanupPolicy: "manual" | "ephemeral_auto_cleanup",
): string {
  return cleanupPolicy === "ephemeral_auto_cleanup"
    ? "Ephemeral auto-cleanup"
    : "Manual cleanup";
}

export function canRetrySyntheticJob(job: SyntheticGenerationJob | null): boolean {
  return job?.status === "failed";
}

export function canCleanupSyntheticJob(job: SyntheticGenerationJob | null): boolean {
  return job?.status === "completed" || job?.status === "failed";
}
