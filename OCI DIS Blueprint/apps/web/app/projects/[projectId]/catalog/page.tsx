/* Catalog page bootstrapping pattern data and the interactive grid. */

import { CatalogTable } from "@/components/catalog-table";
import { api } from "@/lib/api";

type ProjectCatalogPageProps = {
  params: {
    projectId: string;
  };
};

export default async function ProjectCatalogPage({
  params,
}: ProjectCatalogPageProps): Promise<JSX.Element> {
  const [allRows, patterns] = await Promise.all([
    api.listCatalog(params.projectId, { page: 1, page_size: 500 }),
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
    integrations: allRows.integrations.slice(0, 50),
    total: allRows.total,
    page: 1,
    page_size: 50,
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.25em] text-sky-700">Catalog Grid</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
          Integration Catalog
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          Review imported rows in source order, filter by QA status or assigned pattern, and open a row to patch governed fields.
        </p>
      </section>
      <CatalogTable
        projectId={params.projectId}
        initialPage={initialPage}
        patterns={patterns.patterns}
        brands={brands}
      />
    </div>
  );
}
