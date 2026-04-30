/* Server-rendered import page with client upload flow. */

import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { ImportUpload } from "@/components/import-upload";
import { api } from "@/lib/api";
import { isProjectNotFoundError } from "@/lib/project-errors";

type ProjectImportPageProps = {
  params: Promise<{
    projectId: string;
  }>;
  searchParams: Promise<{
    batch_id?: string;
    row?: string;
  }>;
};

export default async function ProjectImportPage({
  params,
  searchParams,
}: ProjectImportPageProps): Promise<JSX.Element> {
  const { projectId } = await params;
  const resolvedSearchParams = await searchParams;
  let project;
  try {
    project = await api.getProject(projectId);
  } catch (error) {
    if (isProjectNotFoundError(error)) {
      notFound();
    }
    throw error;
  }
  const [imports, selectedRows] = await Promise.all([
    api.listImports(projectId),
    resolvedSearchParams.batch_id
      ? api.listImportRows(projectId, resolvedSearchParams.batch_id, { page: 1, page_size: 200 })
      : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <p className="app-kicker">Workbook Import</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Import for {project.name}
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Upload governed workbooks, review imported source rows, and trace integrations back to their original line items.
        </p>
        <div className="mt-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project.name, href: `/projects/${projectId}` },
              { label: "Import" },
            ]}
          />
        </div>
      </section>

      <ImportUpload
        projectId={projectId}
        projectName={project.name}
        initialBatches={imports.batches}
        initialRows={selectedRows}
        initialSelectedBatchId={resolvedSearchParams.batch_id ?? null}
        highlightedRowNumber={resolvedSearchParams.row ? Number(resolvedSearchParams.row) : null}
      />
    </div>
  );
}
