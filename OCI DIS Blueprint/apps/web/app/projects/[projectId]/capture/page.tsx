/* Capture landing page with recent manual-capture history and a CTA into the wizard. */

import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { CaptureHistoryClient } from "@/components/capture-history-client";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { isProjectNotFoundError } from "@/lib/project-errors";

type CapturePageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function CapturePage({ params }: CapturePageProps): Promise<JSX.Element> {
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
  const audit = await api.listAudit(projectId);

  const manualEvents = audit.events.filter((event) => event.event_type === "manual_capture");
  const hasCaptures = manualEvents.length > 0;

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
                { label: project.name, href: `/projects/${projectId}` },
                { label: "Capture" },
              ]}
            />
          </div>
        </div>
        <Link
          href={`/projects/${projectId}/capture/new`}
          className="app-button-primary"
        >
          New Integration
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="app-card-muted p-5">
          <p className="app-label">Manual Captures</p>
          <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{manualEvents.length}</p>
        </article>
        <article className="app-card-muted p-5">
          <p className="app-label">Latest Capture</p>
          <p className="mt-3 text-sm font-medium text-[var(--color-text-primary)]">
            {manualEvents[0] ? formatDate(manualEvents[0].created_at) : "No captures yet"}
          </p>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            {manualEvents[0]
              ? "The latest guided entry is ready for catalog review and downstream patching."
              : "No manual capture has been submitted for this project yet."}
          </p>
        </article>
        <article className="app-card-muted p-5">
          <p className="app-label">Next Step</p>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
            {hasCaptures
              ? "Open a captured integration in Catalog to review lineage, adjust the architect patch, and recalculate if needed."
              : "Start with one guided capture or import a workbook, then use Catalog to refine the governed integration record."}
          </p>
        </article>
      </section>

      <CaptureHistoryClient projectId={projectId} initialEvents={manualEvents} />
    </div>
  );
}
