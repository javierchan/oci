/* Project commercial workspace for governed OCI Bill of Materials. */

import { BadgeDollarSign } from "lucide-react";
import { notFound } from "next/navigation";

import { BomWorkspace } from "@/components/bom-workspace";
import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import { isProjectNotFoundError } from "@/lib/project-errors";

type ProjectBomPageProps = { params: Promise<{ projectId: string }> };

export default async function ProjectBomPage({ params }: ProjectBomPageProps): Promise<JSX.Element> {
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

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-accent)]"><BadgeDollarSign className="h-5 w-5" /></span>
          <div>
            <p className="app-kicker">Commercial Workspace · Governed Estimate</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">BOM &amp; Cost</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">Build a deployment-aware OCI estimate for {project.name} from approved technical demand, price evidence, and SKU mappings.</p>
            <div className="mt-4"><Breadcrumb items={[{ label: "Home", href: "/projects" }, { label: "Projects", href: "/projects" }, { label: project.name, href: `/projects/${projectId}` }, { label: "BOM & Cost" }]} /></div>
          </div>
        </div>
      </section>
      <BomWorkspace projectId={projectId} projectName={project.name} />
    </div>
  );
}
