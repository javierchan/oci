/* Server-rendered project list page. */

import { ProjectsPageClient, type ProjectRow } from "@/components/projects-page-client";
import { api } from "@/lib/api";
import type { ImportBatch } from "@/lib/types";

export default async function ProjectsPage(): Promise<JSX.Element> {
  const projectList = await api.listProjects();
  const projectRows = await Promise.all(
    projectList.projects.map(async (project): Promise<ProjectRow> => {
      const imports = await api.listImports(project.id);
      const latestBatch: ImportBatch | undefined = imports.batches[0];
      return {
        project,
        rowCount: latestBatch?.loaded_count ?? 0,
      };
    }),
  );

  return <ProjectsPageClient initialProjects={projectRows} />;
}
