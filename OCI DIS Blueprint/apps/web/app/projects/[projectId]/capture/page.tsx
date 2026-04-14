/* Capture landing page with recent manual-capture history and a CTA into the wizard. */

import Link from "next/link";

import { Breadcrumb } from "@/components/breadcrumb";
import { CaptureHistoryClient } from "@/components/capture-history-client";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

type CapturePageProps = {
  params: {
    projectId: string;
  };
};

export default async function CapturePage({ params }: CapturePageProps): Promise<JSX.Element> {
  const [project, audit] = await Promise.all([
    api.getProject(params.projectId),
    api.listAudit(params.projectId),
  ]);

  const manualEvents = audit.events.filter((event) => event.event_type === "manual_capture");

  return (
    <div className="space-y-8">
      <section className="app-card flex flex-col gap-5 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="app-kicker">Guided Capture</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {project.name}
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Create governed catalog entries without waiting for a workbook import. The wizard will preview duplicate matches, live OIC sizing, and QA readiness before it writes anything.
          </p>
          <div className="mt-4">
            <Breadcrumb
              items={[
                { label: "Home", href: "/projects" },
                { label: "Projects", href: "/projects" },
                { label: project.name, href: `/projects/${params.projectId}` },
                { label: "Capture" },
              ]}
            />
          </div>
        </div>
        <Link
          href={`/projects/${params.projectId}/capture/new`}
          className="app-button-primary"
        >
          New Integration
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Manual Captures</p>
          <p className="mt-3 text-3xl font-semibold text-slate-950">{manualEvents.length}</p>
        </article>
        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Latest Capture</p>
          <p className="mt-3 text-sm font-medium text-slate-950">
            {manualEvents[0] ? formatDate(manualEvents[0].created_at) : "No captures yet"}
          </p>
        </article>
        <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Next Step</p>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            Capture a new integration, then review it in Catalog detail for downstream patching and recalculation.
          </p>
        </article>
      </section>

      <CaptureHistoryClient projectId={params.projectId} initialEvents={manualEvents} />
    </div>
  );
}
