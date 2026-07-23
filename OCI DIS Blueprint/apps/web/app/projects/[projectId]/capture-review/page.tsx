/* Governed external-capture review page. */

import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { ExternalCaptureReview } from "@/components/external-capture-review";
import { api } from "@/lib/api";
import { isProjectNotFoundError } from "@/lib/project-errors";

type CaptureReviewPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function CaptureReviewPage({
  params,
}: CaptureReviewPageProps): Promise<JSX.Element> {
  const { projectId } = await params;
  let project;
  try {
    project = await api.getProject(projectId);
  } catch (error) {
    if (isProjectNotFoundError(error)) notFound();
    throw error;
  }

  const [sessions, patterns] = await Promise.all([
    api.listExternalCaptureSessions(projectId),
    api.listPatterns(),
  ]);
  const clientName =
    typeof project.project_metadata?.client_name === "string"
      ? project.project_metadata.client_name
      : null;

  return (
    <div className="console-page">
      <section className="console-hero">
        <p className="app-kicker">Capture governance · External evidence review</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Capture Review
        </h1>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Review how customer evidence maps into the App contract before any row
          becomes a governed integration. Required gaps, pattern changes, payload
          interpretation, and economic scope remain explicit.
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project.name, href: `/projects/${projectId}` },
              { label: "Capture Review" },
            ]}
          />
          {clientName ? (
            <div className="text-right">
              <p className="app-label">Customer</p>
              <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">
                {clientName}
              </p>
            </div>
          ) : null}
        </div>
      </section>

      <ExternalCaptureReview
        project={project}
        initialSessions={sessions.sessions}
        patterns={patterns.patterns}
      />
    </div>
  );
}
