"use client";

/* Admin synthetic job detail page with polling, artifacts, and cleanup actions. */

import Link from "next/link";
import { Loader2, RotateCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AdminConfirmDelete } from "@/components/admin-confirm-delete";
import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import {
  canCleanupSyntheticJob,
  canRetrySyntheticJob,
  resolveSyntheticJobCleanupPolicy,
  resolveSyntheticJobStatusClasses,
  usesEphemeralAutoCleanup,
} from "@/lib/admin-synthetic-ui";
import { formatDate, formatNumber } from "@/lib/format";
import type { SyntheticGenerationJob } from "@/lib/types";

function normalizeApiBase(value: string): string {
  return value.replace(/\/api\/v1\/?$/, "");
}

const API_DOWNLOAD_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

function renderScalar(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export default function AdminSyntheticJobPage(): JSX.Element {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const [job, setJob] = useState<SyntheticGenerationJob | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [retrying, setRetrying] = useState<boolean>(false);
  const [cleaningUp, setCleaningUp] = useState<boolean>(false);
  const [cleanupOpen, setCleanupOpen] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const load = useCallback(async (options?: { silent?: boolean }): Promise<void> => {
    if (!options?.silent) {
      setLoading(true);
    }
    try {
      const response = await api.getSyntheticJob(jobId);
      setJob(response);
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to load the synthetic job.");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [jobId, load]);

  const isActiveJob = job?.status === "pending" || job?.status === "running";

  useEffect(() => {
    if (!isActiveJob) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      void load({ silent: true });
    }, 5000);
    return () => window.clearInterval(interval);
  }, [isActiveJob, jobId, load]);

  const exportEntries = useMemo(
    () => Object.entries(job?.artifact_manifest?.export_jobs ?? {}),
    [job?.artifact_manifest?.export_jobs],
  );
  const jobCleanupPolicy = resolveSyntheticJobCleanupPolicy(job);

  async function handleRetry(): Promise<void> {
    setRetrying(true);
    try {
      const retried = await api.retrySyntheticJob(jobId);
      setError("");
      window.location.href = `/admin/synthetic/${retried.id}`;
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to retry the synthetic job.");
    } finally {
      setRetrying(false);
    }
  }

  async function handleCleanup(): Promise<void> {
    setCleaningUp(true);
    try {
      const cleaned = await api.cleanupSyntheticJob(jobId);
      setJob(cleaned);
      setCleanupOpen(false);
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to clean up the synthetic job.");
    } finally {
      setCleaningUp(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="app-card flex flex-col gap-4 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Admin Governance</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">Synthetic Job Detail</h1>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Admin", href: "/admin" },
                { label: "Synthetic Lab", href: "/admin/synthetic" },
                { label: job?.id ?? jobId },
              ]}
            />
          </div>
        </div>
        {job ? (
          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${resolveSyntheticJobStatusClasses(job.status)}`}>
            {job.status}
          </span>
        ) : null}
      </section>

      {error ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>
      ) : null}

      {loading && !job ? (
        <section className="app-card px-6 py-8 text-sm text-[var(--color-text-secondary)]">Loading synthetic job…</section>
      ) : null}

      {job ? (
        <>
          <section className="grid gap-4 lg:grid-cols-4">
            <article className="app-card p-5">
              <p className="app-label">Requested By</p>
              <p className="mt-3 text-xl font-semibold text-[var(--color-text-primary)]">{job.requested_by}</p>
            </article>
            <article className="app-card p-5">
              <p className="app-label">Catalog Target</p>
              <p className="mt-3 text-xl font-semibold text-[var(--color-text-primary)]">{formatNumber(job.catalog_target)}</p>
            </article>
            <article className="app-card p-5">
              <p className="app-label">Created</p>
              <p className="mt-3 text-xl font-semibold text-[var(--color-text-primary)]">{formatDate(job.created_at)}</p>
            </article>
            <article className="app-card p-5">
              <p className="app-label">Project</p>
              {job.project_id ? (
                <Link href={`/projects/${job.project_id}`} className="mt-3 inline-flex text-lg font-semibold text-[var(--color-accent)] hover:underline">
                  Open Project →
                </Link>
              ) : (
                <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{job.project_name ?? "Pending creation"}</p>
              )}
            </article>
          </section>

          <section className="flex flex-wrap gap-3">
            {canRetrySyntheticJob(job) ? (
              <button
                type="button"
                onClick={() => {
                  void handleRetry();
                }}
                disabled={retrying}
                className="app-button-secondary inline-flex items-center gap-2"
              >
                {retrying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                Retry Job
              </button>
            ) : null}
            {canCleanupSyntheticJob(job) ? (
              <button
                type="button"
                onClick={() => {
                  setCleanupOpen(true);
                }}
                className="inline-flex items-center gap-2 rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-500"
              >
                <Trash2 className="h-4 w-4" />
                Cleanup
              </button>
            ) : null}
            {isActiveJob ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Polling
              </span>
            ) : null}
          </section>

          {usesEphemeralAutoCleanup(jobCleanupPolicy) ? (
            <section className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
              Ephemeral smoke validation run. This job automatically removes its synthetic project and generated artifacts after completion.
            </section>
          ) : null}

          <section className="grid gap-6 xl:grid-cols-2">
            <article className="app-card p-6">
              <p className="app-label">Configuration</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Normalized Inputs</h2>
              <dl className="mt-5 grid gap-4 md:grid-cols-2">
                {Object.entries(job.normalized_payload).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{key}</dt>
                    <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{renderScalar(value)}</dd>
                  </div>
                ))}
              </dl>
            </article>

            <article className="app-card p-6">
              <p className="app-label">Validation</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Execution Results</h2>
              {job.validation_results ? (
                <dl className="mt-5 grid gap-4 md:grid-cols-2">
                  {Object.entries(job.validation_results).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                      <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{key}</dt>
                      <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{renderScalar(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-5 text-sm text-[var(--color-text-secondary)]">
                  Validation results will appear here once the job reaches a terminal state.
                </p>
              )}
            </article>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <article className="app-card p-6">
              <p className="app-label">Artifacts</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Generated Files</h2>
              {job.artifact_manifest ? (
                <div className="mt-5 space-y-4 text-sm">
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <p className="font-semibold text-[var(--color-text-primary)]">Workbook</p>
                    <p className="mt-2 break-all text-[var(--color-text-secondary)]">{job.artifact_manifest.workbook_path}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <p className="font-semibold text-[var(--color-text-primary)]">Reports</p>
                    <p className="mt-2 break-all text-[var(--color-text-secondary)]">{job.artifact_manifest.report_json_path}</p>
                    <p className="mt-2 break-all text-[var(--color-text-secondary)]">{job.artifact_manifest.report_markdown_path}</p>
                  </div>
                  {exportEntries.length > 0 ? (
                    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                      <p className="font-semibold text-[var(--color-text-primary)]">Exports</p>
                      <div className="mt-3 space-y-3">
                        {exportEntries.map(([format, artifact]) => (
                          <div key={format} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="font-medium text-[var(--color-text-primary)]">{format.toUpperCase()}</p>
                                <p className="mt-1 break-all text-xs text-[var(--color-text-muted)]">{artifact.file_path}</p>
                              </div>
                              <a
                                href={`${API_DOWNLOAD_BASE}${artifact.download_url}`}
                                className="text-sm font-medium text-[var(--color-accent)] hover:underline"
                                target="_blank"
                                rel="noreferrer"
                              >
                                Download
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="mt-5 text-sm text-[var(--color-text-secondary)]">
                  Artifacts are not available yet for this job.
                </p>
              )}
            </article>

            <article className="app-card p-6">
              <p className="app-label">Diagnostics</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Summary & Errors</h2>
              {job.result_summary ? (
                <dl className="mt-5 grid gap-4 md:grid-cols-2">
                  {Object.entries(job.result_summary).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                      <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{key}</dt>
                      <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{renderScalar(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-5 text-sm text-[var(--color-text-secondary)]">
                  Result summary will populate after the job completes.
                </p>
              )}
              {job.error_details ? (
                <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                  <p className="font-semibold">Error details</p>
                  <pre className="mt-3 whitespace-pre-wrap break-words text-xs">{JSON.stringify(job.error_details, null, 2)}</pre>
                </div>
              ) : null}
            </article>
          </section>
        </>
      ) : null}

      <AdminConfirmDelete
        open={cleanupOpen}
        title="Clean up synthetic job"
        description={`This will archive/delete the synthetic project and remove generated artifacts for "${job?.project_name ?? job?.id ?? jobId}".`}
        onConfirm={handleCleanup}
        onCancel={() => {
          if (!cleaningUp) {
            setCleanupOpen(false);
          }
        }}
        isLoading={cleaningUp}
      />
    </div>
  );
}
