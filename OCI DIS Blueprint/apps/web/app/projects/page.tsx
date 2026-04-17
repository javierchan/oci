/* Server-rendered project list page. */

import { Breadcrumb } from "@/components/breadcrumb";
import { ProjectsPageClient, type ProjectRow } from "@/components/projects-page-client";
import { api } from "@/lib/api";

export default async function ProjectsPage(): Promise<JSX.Element> {
  const projectList = await api.listProjects();
  const projectRows = await Promise.all(
    projectList.projects.map(async (project): Promise<ProjectRow> => {
      const catalogPage = await api.listCatalog(project.id, { page: 1, page_size: 1 });
      return {
        project,
        rowCount: catalogPage.total,
      };
    }),
  );

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <p className="app-kicker">Workspace</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Projects
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Create an assessment workspace, import the workbook, and drill into the catalog, QA, and volumetry flows.
        </p>
        <div className="mt-4">
          <Breadcrumb items={[{ label: "Home" }]} />
        </div>
      </section>

      <ProjectsPageClient initialProjects={projectRows} />
    </div>
  );
}
