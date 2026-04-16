/* Project dashboard page with latest import, QA, and volumetry metrics. */

import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { RecalculateButton } from "@/components/recalculate-button";
import { VolumetryCard } from "@/components/volumetry-card";
import { api } from "@/lib/api";
import { formatCompactNumber, formatNumber } from "@/lib/format";
import { parityBenchmark } from "@/lib/parity";
import type { DashboardSnapshot } from "@/lib/types";

type ProjectDashboardPageProps = {
  params: {
    projectId: string;
  };
};

function isProjectNotFound(error: unknown): boolean {
  return error instanceof Error && error.message.includes("PROJECT_NOT_FOUND");
}

export default async function ProjectDashboardPage({
  params,
}: ProjectDashboardPageProps): Promise<JSX.Element> {
  const projectId = params.projectId;
  let project;
  let imports;
  let catalogPage;
  let snapshots;

  try {
    [project, imports, catalogPage, snapshots] = await Promise.all([
      api.getProject(projectId),
      api.listImports(projectId),
      api.listCatalog(projectId, { page: 1, page_size: 500 }),
      api.listSnapshots(projectId),
    ]);
  } catch (error) {
    if (isProjectNotFound(error)) {
      notFound();
    }
    throw error;
  }

  const latestImport = imports.batches[0];
  const latestSnapshot = snapshots.snapshots[0];
  const consolidated = latestSnapshot?.consolidated;
  const dashboardSnapshots = await api.listDashboardSnapshots(projectId);
  const latestDashboard: DashboardSnapshot | null = dashboardSnapshots.snapshots[0]
    ? await api.getDashboardSnapshot(projectId, dashboardSnapshots.snapshots[0].snapshot_id)
    : null;

  const qaBreakdown = catalogPage.integrations.reduce(
    (accumulator: Record<string, number>, integration) => {
      const key = integration.qa_status ?? "PENDING";
      accumulator[key] = (accumulator[key] ?? 0) + 1;
      return accumulator;
    },
    { OK: 0, REVISAR: 0, PENDING: 0 },
  );

  return (
    <div className="space-y-8">
      <section className="app-card p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Project Dashboard</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              {project.name}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Track the current import footprint, QA exposure, and latest technical sizing for this assessment workspace.
            </p>
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
          <RecalculateButton projectId={projectId} />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
        <VolumetryCard
          label="Integrations Loaded"
          value={formatNumber(latestImport?.loaded_count ?? 0)}
          unit="rows"
        />
        <VolumetryCard
          label="Excluded (Duplicado 2)"
          value={formatNumber(latestImport?.excluded_count ?? 0)}
          unit="rows"
        />
        <VolumetryCard
          label="OIC Peak Packs / Hour"
          value={formatNumber(consolidated?.oic.peak_packs_hour ?? 0, 1)}
          unit="packs"
        />
        <VolumetryCard
          label="OIC Billing Msgs / Month"
          value={formatCompactNumber(consolidated?.oic.total_billing_msgs_month ?? 0)}
          unit="msgs"
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <article className="app-card p-6">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">QA Breakdown</p>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.5rem] border border-[var(--color-qa-ok-text)]/20 bg-[var(--color-qa-ok-bg)] p-5 text-[var(--color-qa-ok-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">OK</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.OK ?? 0}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-[var(--color-qa-revisar-text)]/20 bg-[var(--color-qa-revisar-bg)] p-5 text-[var(--color-qa-revisar-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">REVISAR</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.REVISAR ?? 0}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-[var(--color-qa-pending-text)]/20 bg-[var(--color-qa-pending-bg)] p-5 text-[var(--color-qa-pending-text)]">
              <p className="text-xs uppercase tracking-[0.25em]">PENDING</p>
              <p className="mt-3 text-3xl font-semibold">
                {qaBreakdown.PENDING ?? 0}
              </p>
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

        <article className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Parity Benchmark</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">Workbook reference</h2>
          <dl className="mt-6 space-y-4 text-sm">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-4">
              <dt className="text-slate-400">Loaded rows</dt>
              <dd className="font-semibold text-white">{parityBenchmark.loadedRows}</dd>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-4">
              <dt className="text-slate-400">Excluded rows</dt>
              <dd className="font-semibold text-white">{parityBenchmark.excludedRows}</dd>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-4">
              <dt className="text-slate-400">TBQ = Y</dt>
              <dd className="font-semibold text-white">{parityBenchmark.tbqRows}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-slate-400">Expected QA Revisar</dt>
              <dd className="font-semibold text-white">{parityBenchmark.qaRevisar}</dd>
            </div>
          </dl>
        </article>
      </section>

      {latestDashboard ? (
        <section className="grid gap-6 lg:grid-cols-2 xl:grid-cols-4">
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
            <div className="mt-4 space-y-3">
              {latestDashboard.charts.payload_distribution.map((bucket) => {
                const ratio = latestDashboard.charts.coverage.total_integrations
                  ? (bucket.count / latestDashboard.charts.coverage.total_integrations) * 100
                  : 0;
                return (
                  <div key={bucket.label} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
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

          <article className="app-card p-6">
            <p className="app-label">Risks</p>
            <div className="mt-4 space-y-3">
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
        </section>
      ) : null}
    </div>
  );
}
