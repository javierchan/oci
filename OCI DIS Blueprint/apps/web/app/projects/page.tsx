/* Server-rendered project list page. */

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

  return <ProjectsPageClient initialProjects={projectRows} />;
}
