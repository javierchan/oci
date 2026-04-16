/* Catalog page bootstrapping pattern data and the interactive grid. */

import { Breadcrumb } from "@/components/breadcrumb";
import { CatalogTable } from "@/components/catalog-table";
import { api } from "@/lib/api";

type ProjectCatalogPageProps = {
  params: {
    projectId: string;
  };
  searchParams: {
    search?: string;
    system?: string;
    qa_status?: string;
    pattern?: string;
    brand?: string;
    source_system?: string;
    destination_system?: string;
  };
};

export default async function ProjectCatalogPage({
  params,
  searchParams,
}: ProjectCatalogPageProps): Promise<JSX.Element> {
  const initialFilters = {
    search: searchParams.search ?? "",
    system: searchParams.system ?? "",
    qa_status: searchParams.qa_status ?? "",
    pattern: searchParams.pattern ?? "",
    brand: searchParams.brand ?? "",
    source_system: searchParams.source_system ?? "",
    destination_system: searchParams.destination_system ?? "",
  };
  const [project, allRows, patterns] = await Promise.all([
    api.getProject(params.projectId),
    api.listCatalog(params.projectId, {
      page: 1,
      page_size: 500,
      search: initialFilters.search || undefined,
      qa_status: initialFilters.qa_status || undefined,
      pattern: initialFilters.pattern || undefined,
      brand: initialFilters.brand || undefined,
      source_system: initialFilters.source_system || undefined,
      destination_system: initialFilters.destination_system || undefined,
    }),
    api.listPatterns(),
  ]);

  const brands = Array.from(
    new Set(
      allRows.integrations
        .map((integration) => integration.brand)
        .filter((brandName): brandName is string => Boolean(brandName)),
    ),
  ).sort((left, right) => left.localeCompare(right));

  const initialPage = {
    integrations: allRows.integrations.slice(0, 20),
    total: allRows.total,
    page: 1,
    page_size: 20,
  };

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <p className="app-kicker">Catalog Grid</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Integration Catalog
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Review imported rows in source order, filter by QA status or assigned pattern, and open a row to patch governed fields.
        </p>
        <div className="mt-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project.name, href: `/projects/${params.projectId}` },
              { label: "Catalog" },
            ]}
          />
        </div>
      </section>
      <CatalogTable
        projectId={params.projectId}
        projectName={project.name}
        initialPage={initialPage}
        patterns={patterns.patterns}
        brands={brands}
        initialFilters={initialFilters}
      />
    </div>
  );
}
