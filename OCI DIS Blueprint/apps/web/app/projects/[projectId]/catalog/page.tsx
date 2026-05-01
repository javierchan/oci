/* Catalog page bootstrapping pattern data and the interactive grid. */

import { notFound } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { CatalogTable } from "@/components/catalog-table";
import { api } from "@/lib/api";
import { isProjectNotFoundError } from "@/lib/project-errors";

type ProjectCatalogPageProps = {
  params: Promise<{
    projectId: string;
  }>;
  searchParams: Promise<{
    search?: string;
    system?: string;
    qa_status?: string;
    pattern?: string;
    brand?: string;
    source_system?: string;
    destination_system?: string;
  }>;
};

export default async function ProjectCatalogPage({
  params,
  searchParams,
}: ProjectCatalogPageProps): Promise<JSX.Element> {
  const { projectId } = await params;
  const resolvedSearchParams = await searchParams;
  const initialFilters = {
    search: resolvedSearchParams.search ?? "",
    system: resolvedSearchParams.system ?? "",
    qa_status: resolvedSearchParams.qa_status ?? "",
    pattern: resolvedSearchParams.pattern ?? "",
    brand: resolvedSearchParams.brand ?? "",
    source_system: resolvedSearchParams.source_system ?? "",
    destination_system: resolvedSearchParams.destination_system ?? "",
  };
  let project;
  try {
    project = await api.getProject(projectId);
  } catch (error) {
    if (isProjectNotFoundError(error)) {
      notFound();
    }
    throw error;
  }
  const [initialPage, patterns, facets] = await Promise.all([
    api.listCatalog(projectId, {
      page: 1,
      page_size: 25,
      search: initialFilters.search || undefined,
      qa_status: initialFilters.qa_status || undefined,
      pattern: initialFilters.pattern || undefined,
      brand: initialFilters.brand || undefined,
      source_system: initialFilters.source_system || undefined,
      destination_system: initialFilters.destination_system || undefined,
    }),
    api.listPatterns(),
    api.getCatalogFacets(projectId),
  ]);

  return (
    <div className="console-page">
      <section className="console-hero">
        <p className="app-kicker">Catalog · Drill-down spine</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Integration Catalog
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Review imported rows in source order, filter by QA status or assigned pattern, and select a row to inspect it in the side drawer without losing catalog context.
        </p>
        <div className="mt-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project.name, href: `/projects/${projectId}` },
              { label: "Catalog" },
            ]}
          />
        </div>
      </section>
      <CatalogTable
        projectId={projectId}
        projectName={project.name}
        initialPage={initialPage}
        patterns={patterns.patterns}
        brands={facets.brands}
        initialFilters={initialFilters}
      />
    </div>
  );
}
