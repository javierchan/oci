/* Project dashboard page with latest import, QA, and volumetry metrics. */

import { RecalculateButton } from "@/components/recalculate-button";
import { VolumetryCard } from "@/components/volumetry-card";
import { api } from "@/lib/api";
import { formatCompactNumber, formatNumber } from "@/lib/format";
import { parityBenchmark } from "@/lib/parity";

type ProjectDashboardPageProps = {
  params: {
    projectId: string;
  };
};

export default async function ProjectDashboardPage({
  params,
}: ProjectDashboardPageProps): Promise<JSX.Element> {
  const projectId = params.projectId;
  const [project, imports, catalogPage, snapshots] = await Promise.all([
    api.getProject(projectId),
    api.listImports(projectId),
    api.listCatalog(projectId, { page: 1, page_size: 500 }),
    api.listSnapshots(projectId),
  ]);

  const latestImport = imports.batches[0];
  const latestSnapshot = snapshots.snapshots[0];
  const consolidated = latestSnapshot?.consolidated;

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
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-sky-700">Project Dashboard</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
              {project.name}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Track the current import footprint, QA exposure, and latest technical sizing for this assessment workspace.
            </p>
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
        <article className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">QA Breakdown</p>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-emerald-700">OK</p>
              <p className="mt-3 text-3xl font-semibold text-emerald-950">
                {qaBreakdown.OK ?? 0}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-amber-700">REVISAR</p>
              <p className="mt-3 text-3xl font-semibold text-amber-950">
                {qaBreakdown.REVISAR ?? 0}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">PENDING</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">
                {qaBreakdown.PENDING ?? 0}
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Catalog Rows</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">{catalogPage.total}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Snapshots</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">{snapshots.snapshots.length}</p>
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
    </div>
  );
}
