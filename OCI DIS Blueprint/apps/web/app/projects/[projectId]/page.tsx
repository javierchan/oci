/* Project dashboard page with latest import, QA, and volumetry metrics. */

import { notFound } from "next/navigation";
import Link from "next/link";
import { Download } from "lucide-react";

import { AiReviewButton } from "@/components/ai-review-button";
import { Breadcrumb } from "@/components/breadcrumb";
import { RecalculateButton } from "@/components/recalculate-button";
import { VolumetryCard } from "@/components/volumetry-card";
import { api, apiDownloadUrl } from "@/lib/api";
import { displayQaStatus, formatCompactNumber, formatDate, formatNumber } from "@/lib/format";
import { parityBenchmark } from "@/lib/parity";
import { isProjectNotFoundError } from "@/lib/project-errors";
import type { DashboardCoverageMetric, DashboardSnapshot } from "@/lib/types";

type ProjectDashboardPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

function isSyntheticProject(project: { project_metadata?: Record<string, unknown> | null }): boolean {
  const metadata = project.project_metadata;
  return metadata?.synthetic === true || metadata?.seed_type === "synthetic-enterprise";
}

export default async function ProjectDashboardPage({
  params,
}: ProjectDashboardPageProps): Promise<JSX.Element> {
  const { projectId } = await params;
  let project;
  try {
    project = await api.getProject(projectId);
  } catch (error) {
    if (isProjectNotFoundError(error)) {
      notFound();
    }
    throw error;
  }
  const [catalogPage, snapshots, dashboardSnapshots, baselineLookup] = await Promise.all([
    api.listCatalog(projectId, { page: 1, page_size: 1 }),
    api.listSnapshots(projectId),
    api.listDashboardSnapshots(projectId),
    api.getAiReviewBaseline(projectId, { scope: "project" }).catch(() => ({ baseline: null })),
  ]);

  const latestSnapshot = snapshots.snapshots[0];
  const prevSnapshot = snapshots.snapshots[1];
  const consolidated = latestSnapshot?.consolidated;
  const latestDashboard: DashboardSnapshot | null = dashboardSnapshots.snapshots[0]
    ? await api.getDashboardSnapshot(projectId, dashboardSnapshots.snapshots[0].snapshot_id)
    : null;
  const coverageMetrics: Array<[string, DashboardCoverageMetric]> = latestDashboard
    ? [
        ["Payload Coverage", latestDashboard.charts.coverage.payload],
        ["Pattern Coverage", latestDashboard.charts.coverage.pattern],
        ["Trigger Coverage", latestDashboard.charts.coverage.trigger],
        ["Formal ID Coverage", latestDashboard.charts.coverage.formal_id],
        ["Fan-out Coverage", latestDashboard.charts.coverage.fan_out],
      ]
    : [];

  const qaBreakdown = latestDashboard
    ? {
        OK: latestDashboard.charts.completeness.qa_ok,
        REVISAR: latestDashboard.charts.completeness.qa_revisar,
        PENDING: latestDashboard.charts.completeness.qa_pending,
      }
    : { OK: 0, REVISAR: 0, PENDING: 0 };
  const qaTotal = (qaBreakdown.OK ?? 0) + (qaBreakdown.REVISAR ?? 0) + (qaBreakdown.PENDING ?? 0);
  const qaOkPct = qaTotal > 0 ? Math.round(((qaBreakdown.OK ?? 0) / qaTotal) * 100) : 0;
  const qaReviewPct = qaTotal > 0 ? Math.round(((qaBreakdown.REVISAR ?? 0) / qaTotal) * 100) : 0;
  const qaPendingPct = qaTotal > 0 ? Math.max(0, 100 - qaOkPct - qaReviewPct) : 0;
  const patternCount = latestDashboard?.charts.pattern_mix.filter((entry) => entry.count > 0).length ?? 0;

  function pct(value: number): string {
    return qaTotal > 0 ? `${Math.round((value / qaTotal) * 100)}% of total` : "—";
  }

  function trendDelta(curr: number | undefined, prev: number | undefined): number | null {
    if (!curr || !prev || prev === 0) {
      return null;
    }
    return Math.round(((curr - prev) / prev) * 100);
  }

  const oicTrend = trendDelta(
    consolidated?.oic.total_billing_msgs_month,
    prevSnapshot?.consolidated?.oic.total_billing_msgs_month,
  );
  const platformFootprint = [
    {
      label: "Functions Invocations / Month",
      value: formatCompactNumber(consolidated?.functions.total_invocations_month ?? 0),
      unit: "invocations",
      tooltip: "Estimated Oracle Functions calls on the latest snapshot.",
    },
    {
      label: "Streaming Throughput / Month",
      value: formatNumber(consolidated?.streaming.total_gb_month ?? 0, 1),
      unit: "GB",
      tooltip: "Estimated OCI Streaming data volume for the current project footprint.",
    },
    {
      label: "Queue-backed Routes",
      value: formatNumber(consolidated?.queue.row_count ?? 0),
      unit: "routes",
      tooltip: "Integrations currently using OCI Queue in the governed route.",
    },
    {
      label: "Data Integration / Month",
      value: formatNumber(consolidated?.data_integration.data_processed_gb_month ?? 0, 1),
      unit: "GB",
      tooltip: consolidated?.data_integration.workspace_active
        ? "The latest snapshot includes an active OCI Data Integration workspace."
        : "No active OCI Data Integration workspace was detected in the latest snapshot.",
    },
  ];

  return (
    <div className="console-page">
      <section className="console-hero flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Project Dashboard</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-tight text-[var(--color-text-primary)] lg:text-4xl">
                {project.name}
              </h1>
              {isSyntheticProject(project) ? <span className="app-theme-chip">Synthetic</span> : null}
              {baselineLookup.baseline ? (
                <span className="app-status-chip active" title={baselineLookup.baseline.label}>
                  Planned baseline approved
                </span>
              ) : (
                <span className="app-status-chip archived">No planned baseline</span>
              )}
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Track the current import footprint, QA exposure, and latest technical sizing for this assessment workspace.
            </p>
            {isSyntheticProject(project) ? (
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
                This workspace was generated by the governed synthetic lab flow and is intended for product validation,
                demos, and non-production analysis.
              </p>
            ) : null}
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Projects", href: "/projects" },
                  { label: project.name },
                ]}
              />
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 lg:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={apiDownloadUrl(`/api/v1/exports/${projectId}/brief`)}
                className="app-button-secondary gap-2 px-4 py-2 text-sm"
                title="Download an executive Markdown brief using dashboard, baseline, and AI review evidence."
              >
                <Download className="h-4 w-4" />
                Export brief
              </Link>
              <Link href={`/projects/${projectId}/catalog`} className="app-button-secondary px-4 py-2 text-sm">
                Open Catalog
              </Link>
              <Link href={`/projects/${projectId}/graph`} className="app-button-secondary px-4 py-2 text-sm">
                Open Map
              </Link>
              <RecalculateButton projectId={projectId} />
              <AiReviewButton projectId={projectId} />
            </div>
            {latestSnapshot ? (
              <p className="text-xs text-[var(--color-text-muted)]">
                Last calculated {formatDate(latestSnapshot.created_at)}
              </p>
            ) : null}
          </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_repeat(3,minmax(0,1fr))] md:grid-cols-2">
        <article className="console-stat">
          <p className="app-label">QA Status</p>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              {qaOkPct}
              <span className="text-base text-[var(--color-text-muted)]">%</span>
            </span>
            <span className="text-sm text-[var(--color-text-secondary)]">
              OK · {qaBreakdown.OK ?? 0} of {qaTotal || catalogPage.total}
            </span>
          </div>
          <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-[var(--color-surface-3)]">
            <span style={{ width: `${qaOkPct}%` }} className="bg-[var(--color-qa-ok-text)]" />
            <span style={{ width: `${qaReviewPct}%` }} className="bg-[var(--color-qa-revisar-text)]" />
            <span style={{ width: `${qaPendingPct}%` }} className="bg-[var(--color-qa-pending-text)]" />
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-[var(--color-text-secondary)]">
            <span>OK {qaBreakdown.OK ?? 0}</span>
            <span>Review {qaBreakdown.REVISAR ?? 0}</span>
            <span>Pending {qaBreakdown.PENDING ?? 0}</span>
          </div>
        </article>
        <VolumetryCard
          label="Total Integrations"
          value={formatNumber(catalogPage.total)}
          unit="integrations"
          tooltip="Live count of catalog integrations in this project."
        />
        <VolumetryCard
          label="OIC Billing Msgs / Month"
          value={formatCompactNumber(consolidated?.oic.total_billing_msgs_month ?? 0)}
          unit="msgs"
          trend={oicTrend !== null ? { delta: oicTrend, label: "vs last snapshot" } : null}
          tooltip="OIC billing messages = ceil(payload_kb / 50) x executions/month. Used for license cost estimation."
        />
        <VolumetryCard
          label="Patterns in Use"
          value={formatNumber(patternCount)}
          unit="/ 17"
          tooltip="Patterns with one or more catalog integrations in the latest dashboard snapshot."
        />
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="app-label">Platform Footprint</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              Services active beyond OIC
            </h2>
          </div>
          <span className="app-theme-chip">
            DI workspace {consolidated?.data_integration.workspace_active ? "active" : "inactive"}
          </span>
        </div>
        <div className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
          {platformFootprint.map((card) => (
            <VolumetryCard
              key={card.label}
              label={card.label}
              value={card.value}
              unit={card.unit}
              tooltip={card.tooltip}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <article className="app-card p-6">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">QA Breakdown</p>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.5rem] border border-[var(--color-qa-ok-text)]/20 bg-[var(--color-qa-ok-bg)] p-5 text-[var(--color-qa-ok-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">{displayQaStatus("OK")}</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.OK ?? 0}
              </p>
              <p className="mt-1 text-xs">{pct(qaBreakdown.OK ?? 0)}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[var(--color-qa-revisar-text)]/20 bg-[var(--color-qa-revisar-bg)] p-5 text-[var(--color-qa-revisar-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">{displayQaStatus("REVISAR")}</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.REVISAR ?? 0}
              </p>
              <p className="mt-1 text-xs">{pct(qaBreakdown.REVISAR ?? 0)}</p>
            </div>
            <div className="rounded-[1.5rem] border border-[var(--color-qa-pending-text)]/20 bg-[var(--color-qa-pending-bg)] p-5 text-[var(--color-qa-pending-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">{displayQaStatus("PENDING")}</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.PENDING ?? 0}
              </p>
              <p className="mt-1 text-xs">{pct(qaBreakdown.PENDING ?? 0)}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="app-card-muted p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Catalog Rows</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{catalogPage.total}</p>
            </div>
            <div className="app-card-muted p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Snapshots</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{snapshots.snapshots.length}</p>
            </div>
          </div>
        </article>

        <article className="app-card p-6">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-400">
            Parity Benchmark
            <span className="ml-2 font-normal normal-case tracking-normal opacity-60">(reference target)</span>
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Phase 1 Workbook Benchmark
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Reference values from the original parity workbook, not current project totals. Use this card to
            compare the product implementation against the source workbook contract.
          </p>
          <dl className="mt-6 grid gap-3 sm:grid-cols-2">
            <div className="rounded-[1.5rem] bg-[var(--color-surface-2)] p-4">
              <dt className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Loaded rows</dt>
              <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{parityBenchmark.loadedRows}</dd>
            </div>
            <div className="rounded-[1.5rem] bg-[var(--color-surface-2)] p-4">
              <dt className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Excluded rows</dt>
              <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{parityBenchmark.excludedRows}</dd>
            </div>
            <div className="rounded-[1.5rem] bg-[var(--color-surface-2)] p-4">
              <dt className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">TBQ = Y</dt>
              <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{parityBenchmark.tbqRows}</dd>
            </div>
            <div className="rounded-[1.5rem] bg-[var(--color-surface-2)] p-4">
              <dt className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">Expected QA Review</dt>
              <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{parityBenchmark.qaRevisar}</dd>
            </div>
          </dl>
        </article>
      </section>

      {latestDashboard ? (
        <section className="space-y-6">
          {latestDashboard.charts.forecast_confidence.level !== "high" ? (
            <article
              className={[
                "rounded-[1.5rem] border p-5",
                latestDashboard.charts.forecast_confidence.level === "low"
                  ? "border-amber-300 bg-amber-50 text-amber-900"
                  : "border-sky-300 bg-sky-50 text-sky-900",
              ].join(" ")}
            >
              <p className="text-xs uppercase tracking-[0.25em]">
                {latestDashboard.charts.forecast_confidence.level === "low" ? "Forecast Warning" : "Forecast Notice"}
              </p>
              <h2 className="mt-2 text-xl font-semibold">{latestDashboard.charts.forecast_confidence.title}</h2>
              <p className="mt-2 text-sm leading-6">{latestDashboard.charts.forecast_confidence.message}</p>
            </article>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-3 md:grid-cols-2">
            {coverageMetrics.map(([label, metric]) => (
              <article key={label} className="app-card-muted p-5">
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">{label}</p>
                <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">
                  {formatNumber(metric.complete, 0)}
                  <span className="ml-1 text-lg text-[var(--color-text-secondary)]">
                    / {formatNumber(metric.total, 0)}
                  </span>
                </p>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                  {formatNumber(metric.ratio * 100, 1)}% complete
                </p>
              </article>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.9fr)]">
            <div className="grid gap-6">
              <article className="app-card p-6">
                <p className="app-label">Pattern Mix</p>
                <div className="mt-4 space-y-3">
                  {latestDashboard.charts.pattern_mix.map((entry) => {
                    const ratio = latestDashboard.charts.coverage.total_integrations
                      ? (entry.count / latestDashboard.charts.coverage.total_integrations) * 100
                      : 0;
                    return (
                      <div key={`${entry.pattern_id}-${entry.name}`} className="space-y-1">
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="font-medium text-[var(--color-text-primary)]">{entry.name}</span>
                          <span className="text-[var(--color-text-secondary)]">{entry.count}</span>
                        </div>
                        <div className="h-2 rounded-full bg-[var(--color-surface-3)]">
                          <div
                            className="h-2 rounded-full bg-[var(--color-accent)]"
                            style={{ width: `${Math.max(ratio, entry.count > 0 ? 8 : 0)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </article>

              <article className="app-card p-6">
                <p className="app-label">Payload Distribution</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {latestDashboard.charts.payload_distribution.map((bucket) => {
                    const ratio = latestDashboard.charts.coverage.total_integrations
                      ? (bucket.count / latestDashboard.charts.coverage.total_integrations) * 100
                      : 0;
                    return (
                      <div key={bucket.label} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-[var(--color-text-primary)]">{bucket.label}</span>
                          <span className="text-sm text-[var(--color-text-secondary)]">
                            {bucket.count} ({formatNumber(ratio, 1)}%)
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </article>
            </div>

            <div className="grid gap-6">
              <article className="app-card p-6">
                <p className="app-label">Maturity</p>
                <div className="mt-4 space-y-4">
                  {[
                    ["Governance Maturity", latestDashboard.maturity.governed_pct],
                    ["Pattern Coverage", latestDashboard.maturity.pattern_assigned_pct],
                    ["Payload Coverage", latestDashboard.maturity.payload_informed_pct],
                    ["QA OK", latestDashboard.maturity.qa_ok_pct],
                  ].map(([label, value]) => (
                    <div key={label} className="space-y-1">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-[var(--color-text-primary)]">{label}</span>
                        <span className="text-[var(--color-text-secondary)]">{formatNumber(Number(value), 1)}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-[var(--color-surface-3)]">
                        <div
                          className="h-2 rounded-full bg-[var(--color-accent)]"
                          style={{ width: `${Math.min(Number(value), 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="app-card p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="app-label">Risks</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                      Highest-impact issues stay visible here without overwhelming the rest of the dashboard.
                    </p>
                  </div>
                  <span className="app-theme-chip">{latestDashboard.risks.length} signals</span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  {latestDashboard.risks.map((risk) => {
                    const severityClass =
                      risk.count >= 10
                        ? "border-rose-300 bg-rose-50 text-rose-700"
                        : risk.count >= 5
                          ? "border-amber-300 bg-amber-50 text-amber-700"
                          : "border-sky-300 bg-sky-50 text-sky-700";
                    const severityLabel = risk.count >= 10 ? "High" : risk.count >= 5 ? "Medium" : "Low";
                    return (
                      <article key={risk.code} className={`rounded-2xl border p-4 ${severityClass}`}>
                        <p className="text-xs uppercase tracking-[0.2em]">{severityLabel}</p>
                        <p className="mt-2 font-semibold">{risk.label}</p>
                        <p className="mt-2 text-sm">
                          {risk.count} impacted integrations require review before the project can be considered governed.
                        </p>
                      </article>
                    );
                  })}
                </div>
              </article>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
