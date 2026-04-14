/* Server-rendered import page with client upload flow. */

import { Breadcrumb } from "@/components/breadcrumb";
import { ImportUpload } from "@/components/import-upload";
import { api } from "@/lib/api";

type ProjectImportPageProps = {
  params: {
    projectId: string;
  };
  searchParams: {
    batch_id?: string;
    row?: string;
  };
};

export default async function ProjectImportPage({
  params,
  searchParams,
}: ProjectImportPageProps): Promise<JSX.Element> {
  const [project, imports, selectedRows] = await Promise.all([
    api.getProject(params.projectId),
    api.listImports(params.projectId),
    searchParams.batch_id
      ? api.listImportRows(params.projectId, searchParams.batch_id, { page: 1, page_size: 200 })
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
              { label: project.name, href: `/projects/${params.projectId}` },
              { label: "Import" },
            ]}
          />
        </div>
      </section>

      <ImportUpload
        projectId={params.projectId}
        projectName={project.name}
        initialBatches={imports.batches}
        initialRows={selectedRows}
        initialSelectedBatchId={searchParams.batch_id ?? null}
        highlightedRowNumber={searchParams.row ? Number(searchParams.row) : null}
      />
    </div>
  );
}
