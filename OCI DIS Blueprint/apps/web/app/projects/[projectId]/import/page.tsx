/* Server-rendered import page with client upload flow. */

import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { ImportUpload } from "@/components/import-upload";
import { api } from "@/lib/api";
import { selectImportReviewBatch } from "@/lib/import-selection";
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
  const imports = await api.listImports(projectId);
  const selectedBatch = selectImportReviewBatch(imports.batches, resolvedSearchParams.batch_id);
  const selectedBatchId = selectedBatch?.id ?? null;
  const [selectedRows, qualityAssistant] = await Promise.all([
    selectedBatchId
      ? api.listImportRows(projectId, selectedBatchId, { page: 1, page_size: 1000 })
      : Promise.resolve(null),
    selectedBatchId
      ? api.getImportQualityAssistant(projectId, selectedBatchId).catch(() => null)
      : Promise.resolve(null),
  ]);

  return (
    <div className="console-page">
      <section className="console-hero">
        <p className="app-kicker">Capture & Import · Workbook ingest</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Import for {project.name}
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Upload governed workbooks, review parse output and source rows, then trace integrations back to their original line items before merging decisions into the catalog.
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
        projectStatus={project.status}
        initialBatches={imports.batches}
        initialRows={selectedRows}
        initialQualityAssistant={qualityAssistant}
        initialSelectedBatchId={selectedBatchId}
        initialSelectedBatch={selectedBatch}
        highlightedRowNumber={resolvedSearchParams.row ? Number(resolvedSearchParams.row) : null}
      />
    </div>
  );
}
