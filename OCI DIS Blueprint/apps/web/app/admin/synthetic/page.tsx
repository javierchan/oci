"use client";

/* Admin synthetic lab landing page for preset selection and job monitoring. */

import Link from "next/link";
import { FlaskConical, Loader2, RefreshCcw, RotateCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AdminConfirmDelete } from "@/components/admin-confirm-delete";
import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import {
  buildSyntheticJobFormState,
  getSyntheticCleanupPolicyLabel,
  getSyntheticTargetSplitMessage,
  isSyntheticTargetMismatch,
  resolveSelectedSyntheticPreset,
  resolveSyntheticJobStatusClasses,
  type SyntheticJobFormState,
  usesEphemeralAutoCleanup,
} from "@/lib/admin-synthetic-ui";
import { formatDate, formatNumber } from "@/lib/format";
import type {
  SyntheticGenerationJob,
  SyntheticGenerationPreset,
} from "@/lib/types";

export default function AdminSyntheticPage(): JSX.Element {
  const [presets, setPresets] = useState<SyntheticGenerationPreset[]>([]);
  const [jobs, setJobs] = useState<SyntheticGenerationJob[]>([]);
  const [formState, setFormState] = useState<SyntheticJobFormState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [cleanupTarget, setCleanupTarget] = useState<SyntheticGenerationJob | null>(null);
  const [cleaningUp, setCleaningUp] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const load = useCallback(async (options?: { silent?: boolean }): Promise<void> => {
    const silent = options?.silent ?? false;
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const [presetResponse, jobResponse] = await Promise.all([
        api.listSyntheticPresets(),
        api.listSyntheticJobs({ limit: 20 }),
      ]);
      setPresets(presetResponse.presets);
      setJobs(jobResponse.jobs);
      setFormState((current) =>
        current ?? (presetResponse.presets[0] ? buildSyntheticJobFormState(presetResponse.presets[0]) : null),
      );
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load the synthetic lab.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasRunningJobs = useMemo(
    () => jobs.some((job) => job.status === "pending" || job.status === "running"),
    [jobs],
  );

  useEffect(() => {
    if (!hasRunningJobs) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      void load({ silent: true });
    }, 5000);
    return () => window.clearInterval(interval);
  }, [hasRunningJobs, load]);

  const selectedPreset = useMemo(
    () => resolveSelectedSyntheticPreset(presets, formState?.preset_code),
    [formState?.preset_code, presets],
  );

  async function handleSubmit(): Promise<void> {
    if (!formState) {
      return;
    }
    setSubmitting(true);
    try {
      await api.createSyntheticJob(formState);
      await load({ silent: true });
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to create the synthetic job.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(jobId: string): Promise<void> {
    setRetryingJobId(jobId);
    try {
      await api.retrySyntheticJob(jobId);
      await load({ silent: true });
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to retry the synthetic job.");
    } finally {
      setRetryingJobId(null);
    }
  }

  async function handleCleanup(): Promise<void> {
    if (!cleanupTarget) {
      return;
    }
    setCleaningUp(true);
    try {
      await api.cleanupSyntheticJob(cleanupTarget.id);
      setCleanupTarget(null);
      await load({ silent: true });
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to clean up the synthetic job.");
    } finally {
      setCleaningUp(false);
    }
  }

  const latestJob = jobs[0] ?? null;
  const targetMismatch = isSyntheticTargetMismatch(formState);

  return (
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Synthetic Lab</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Generate deterministic synthetic enterprise projects through the same import, catalog, snapshot, audit,
            justification, graph, and export flows used by the real product.
          </p>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Admin", href: "/admin" },
                { label: "Synthetic Lab" },
              ]}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            void load({ silent: true });
          }}
          disabled={refreshing}
          className="app-button-secondary inline-flex items-center gap-2"
        >
          {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Refresh
        </button>
      </section>

      {error ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="app-card p-6">
          <p className="app-label">Governed Presets</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{presets.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            Admin-only templates define the deterministic generation bounds and defaults.
          </p>
        </article>
        <article className="app-card p-6">
          <p className="app-label">Recent Jobs</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">{jobs.length}</p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            {latestJob ? `Latest update ${formatDate(latestJob.updated_at)}` : "No synthetic jobs yet."}
          </p>
        </article>
        <article className="app-card p-6">
          <p className="app-label">Active Monitoring</p>
          <p className="mt-4 text-4xl font-semibold text-[var(--color-text-primary)]">
            {jobs.filter((job) => job.status === "pending" || job.status === "running").length}
          </p>
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
            Running jobs auto-refresh every 5 seconds until they settle.
          </p>
        </article>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <article className="app-card p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="app-label">Job Submission</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                Create a governed synthetic run
              </h2>
            </div>
            {selectedPreset ? (
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-right">
                <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Preset</p>
                <p className="mt-1 font-semibold text-[var(--color-text-primary)]">{selectedPreset.label}</p>
              </div>
            ) : null}
          </div>

          {formState ? (
            <div className="mt-6 space-y-5">
              {usesEphemeralAutoCleanup(selectedPreset?.cleanup_policy) ? (
                <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
                  Smoke validation preset. This run exercises the real synthetic job flow and automatically removes the generated project and artifacts after completion.
                </div>
              ) : null}
              <label className="block">
                <span className="app-label">Preset</span>
                <select
                  value={formState.preset_code}
                  onChange={(event) => {
                    const preset = presets.find((item) => item.code === event.target.value);
                    if (preset) {
                      setFormState(buildSyntheticJobFormState(preset));
                    }
                  }}
                  className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                >
                  {presets.map((preset) => (
                    <option key={preset.code} value={preset.code}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="app-label">Project Name</span>
                <input
                  type="text"
                  value={formState.project_name}
                  onChange={(event) => {
                    setFormState((current) => (current ? { ...current, project_name: event.target.value } : current));
                  }}
                  className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                />
              </label>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="app-label">Seed Value</span>
                  <input
                    type="number"
                    value={formState.seed_value}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, seed_value: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
                <label className="block">
                  <span className="app-label">Target Catalog Size</span>
                  <input
                    type="number"
                    value={formState.target_catalog_size}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, target_catalog_size: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
                <label className="block">
                  <span className="app-label">Import Rows</span>
                  <input
                    type="number"
                    value={formState.import_target}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, import_target: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
                <label className="block">
                  <span className="app-label">Manual Rows</span>
                  <input
                    type="number"
                    value={formState.manual_target}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, manual_target: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
                <label className="block">
                  <span className="app-label">Excluded Import Rows</span>
                  <input
                    type="number"
                    value={formState.excluded_import_target}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, excluded_import_target: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
                <label className="block">
                  <span className="app-label">Min Distinct Systems</span>
                  <input
                    type="number"
                    value={formState.min_distinct_systems}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, min_distinct_systems: Number(event.target.value) } : current,
                      );
                    }}
                    className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
                  />
                </label>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <label className="flex min-h-[3.25rem] items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                  <input
                    type="checkbox"
                    checked={formState.include_justifications}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, include_justifications: event.target.checked } : current,
                      );
                    }}
                    className="h-4 w-4 shrink-0 self-center"
                  />
                  <span className="leading-tight">Include justifications</span>
                </label>
                <label className="flex min-h-[3.25rem] items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                  <input
                    type="checkbox"
                    checked={formState.include_exports}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, include_exports: event.target.checked } : current,
                      );
                    }}
                    className="h-4 w-4 shrink-0 self-center"
                  />
                  <span className="leading-tight">Include exports</span>
                </label>
                <label className="flex min-h-[3.25rem] items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                  <input
                    type="checkbox"
                    checked={formState.include_design_warnings}
                    onChange={(event) => {
                      setFormState((current) =>
                        current ? { ...current, include_design_warnings: event.target.checked } : current,
                      );
                    }}
                    className="h-4 w-4 shrink-0 self-center"
                  />
                  <span className="leading-tight">Track design warnings</span>
                </label>
              </div>

              <div
                className={[
                  "rounded-2xl border px-4 py-3 text-sm",
                  targetMismatch
                    ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300"
                    : "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]",
                ].join(" ")}
              >
                Import + manual rows = {formatNumber(formState.import_target + formState.manual_target)}.{" "}
                {getSyntheticTargetSplitMessage(formState)}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    void handleSubmit();
                  }}
                  disabled={submitting || targetMismatch}
                  className="app-button-primary inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                  {submitting ? "Submitting…" : "Create Synthetic Job"}
                </button>
                {selectedPreset ? (
                  <button
                    type="button"
                    onClick={() => {
                      setFormState(buildSyntheticJobFormState(selectedPreset));
                    }}
                    className="app-button-secondary"
                  >
                    Reset to Preset
                  </button>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-6 text-sm text-[var(--color-text-secondary)]">
              {loading ? "Loading preset catalog…" : "No presets are available."}
            </div>
          )}
        </article>

        <article className="app-card p-6">
          <p className="app-label">Preset Summary</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {selectedPreset?.label ?? "Waiting for preset"}
          </h2>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
            {selectedPreset?.description ?? "The selected preset will define the governed generation envelope."}
          </p>
          {selectedPreset ? (
            <dl className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <dt className="app-label">Catalog Target</dt>
                <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">
                  {formatNumber(selectedPreset.target_catalog_size)}
                </dd>
              </div>
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <dt className="app-label">Distinct Systems</dt>
                <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">
                  {formatNumber(selectedPreset.min_distinct_systems)}
                </dd>
              </div>
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <dt className="app-label">Import / Manual Split</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                  {formatNumber(selectedPreset.import_target)} / {formatNumber(selectedPreset.manual_target)}
                </dd>
              </div>
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <dt className="app-label">Excluded Workbook Rows</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                  {formatNumber(selectedPreset.excluded_import_target)}
                </dd>
              </div>
              <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <dt className="app-label">Cleanup Policy</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                  {getSyntheticCleanupPolicyLabel(selectedPreset.cleanup_policy)}
                </dd>
              </div>
            </dl>
          ) : null}
        </article>
      </section>

      <section className="app-table-shell">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-table-border)] px-6 py-4">
          <div>
            <p className="app-label">Recent Runs</p>
            <h2 className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">Synthetic generation jobs</h2>
          </div>
          {hasRunningJobs ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Auto-refreshing
            </span>
          ) : null}
        </div>
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-6 py-4 font-medium">Job</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Project</th>
              <th className="px-6 py-4 font-medium">Targets</th>
              <th className="px-6 py-4 font-medium">Updated</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {loading ? (
              <tr>
                <td className="px-6 py-8 text-[var(--color-text-secondary)]" colSpan={6}>
                  Loading synthetic jobs…
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td className="px-6 py-8 text-[var(--color-text-secondary)]" colSpan={6}>
                  No synthetic jobs have been submitted yet.
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id} className="app-table-row">
                  <td className="px-6 py-4">
                    <Link
                      href={`/admin/synthetic/${job.id}`}
                      title={job.id}
                      className="block max-w-[12rem] truncate font-mono text-xs font-semibold text-[var(--color-accent)] hover:underline"
                    >
                      {job.id}
                    </Link>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">{job.requested_by}</p>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${resolveSyntheticJobStatusClasses(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-medium text-[var(--color-text-primary)]">{job.project_name ?? "Pending creation"}</p>
                    {job.project_id ? (
                      <Link href={`/projects/${job.project_id}`} className="mt-1 inline-flex text-xs text-[var(--color-accent)] hover:underline">
                        Open project →
                      </Link>
                    ) : null}
                  </td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">
                    <p>{formatNumber(job.catalog_target)} catalog rows</p>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                      {formatNumber(job.import_target)} import / {formatNumber(job.manual_target)} manual
                    </p>
                  </td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatDate(job.updated_at)}</td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap justify-end gap-3">
                      <Link href={`/admin/synthetic/${job.id}`} className="text-sm font-medium text-[var(--color-accent)] hover:underline">
                        View
                      </Link>
                      {job.status === "failed" ? (
                        <button
                          type="button"
                          onClick={() => {
                            void handleRetry(job.id);
                          }}
                          disabled={retryingJobId === job.id}
                          className="inline-flex items-center gap-1 text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
                        >
                          {retryingJobId === job.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                          Retry
                        </button>
                      ) : null}
                      {job.status === "completed" || job.status === "failed" ? (
                        <button
                          type="button"
                          onClick={() => {
                            setCleanupTarget(job);
                          }}
                          className="inline-flex items-center gap-1 text-sm font-medium text-rose-700 hover:text-rose-500"
                        >
                          <Trash2 className="h-4 w-4" />
                          Cleanup
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <AdminConfirmDelete
        open={cleanupTarget !== null}
        title="Clean up synthetic job"
        description={`This will archive/delete the synthetic project and remove generated artifacts for "${cleanupTarget?.project_name ?? cleanupTarget?.id ?? "this job"}".`}
        onConfirm={handleCleanup}
        onCancel={() => {
          if (!cleaningUp) {
            setCleanupTarget(null);
          }
        }}
        isLoading={cleaningUp}
      />
    </div>
  );
}
