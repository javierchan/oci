"use client";

/* Interactive catalog table with filters, search, contextual actions, and pagination. */

import { useDeferredValue, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, SearchX, X } from "lucide-react";

import { ComplexityBadge } from "@/components/complexity-badge";
import { PatternBadge } from "@/components/pattern-badge";
import { QaBadge } from "@/components/qa-badge";
import { SkeletonRow } from "@/components/skeleton";
import { api } from "@/lib/api";
import type { CatalogPage, Integration, PatternDefinition } from "@/lib/types";

type CatalogTableProps = {
  projectId: string;
  projectName: string;
  initialPage: CatalogPage;
  patterns: PatternDefinition[];
  brands: string[];
  initialFilters: {
    search: string;
    system?: string;
    qa_status: string;
    pattern: string;
    brand: string;
    source_system: string;
    destination_system: string;
  };
};

export function CatalogTable({
  projectId,
  projectName,
  initialPage,
  patterns,
  brands,
  initialFilters,
}: CatalogTableProps): JSX.Element {
  const router = useRouter();
  const initialSystem = initialFilters.system ?? "";
  const [search, setSearch] = useState<string>(initialSystem || initialFilters.search);
  const [qaStatus, setQaStatus] = useState<string>(initialFilters.qa_status);
  const [pattern, setPattern] = useState<string>(initialFilters.pattern);
  const [brand, setBrand] = useState<string>(initialFilters.brand);
  const [sourceSystem] = useState<string>(initialFilters.source_system);
  const [destinationSystem] = useState<string>(initialFilters.destination_system);
  const [page, setPage] = useState<number>(initialPage.page);
  const [pageSize, setPageSize] = useState<number>(50);
  const [data, setData] = useState<CatalogPage>(initialPage);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError("");
      try {
        const response = await api.listCatalog(projectId, {
          page,
          page_size: pageSize,
          search: deferredSearch || undefined,
          qa_status: qaStatus || undefined,
          pattern: pattern || undefined,
          brand: brand || undefined,
          source_system: sourceSystem || undefined,
          destination_system: destinationSystem || undefined,
        });
        if (!cancelled) {
          setData(response);
        }
      } catch (caughtError) {
        if (!cancelled) {
          setError(caughtError instanceof Error ? caughtError.message : "Unable to load catalog.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [brand, deferredSearch, destinationSystem, page, pageSize, pattern, projectId, qaStatus, sourceSystem]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) {
      params.set("search", search);
    }
    if (initialSystem && search === initialSystem) {
      params.set("system", initialSystem);
    }
    if (qaStatus) {
      params.set("qa_status", qaStatus);
    }
    if (pattern) {
      params.set("pattern", pattern);
    }
    if (brand) {
      params.set("brand", brand);
    }
    if (sourceSystem) {
      params.set("source_system", sourceSystem);
    }
    if (destinationSystem) {
      params.set("destination_system", destinationSystem);
    }
    const query = params.toString();
    router.replace(`/projects/${projectId}/catalog${query ? `?${query}` : ""}`);
  }, [brand, destinationSystem, initialSystem, pattern, projectId, qaStatus, router, search, sourceSystem]);

  const totalPages = Math.max(1, Math.ceil(data.total / pageSize));
  const hasPromptFilters = search !== "" || qaStatus !== "" || pattern !== "" || brand !== "";
  const hasActiveFilters = hasPromptFilters || sourceSystem !== "" || destinationSystem !== "";
  const patternMap = new Map<string, PatternDefinition>(
    patterns.map((patternDefinition: PatternDefinition) => [
      patternDefinition.pattern_id,
      patternDefinition,
    ]),
  );

  function resetPageAndSet(setter: (_value: string) => void, value: string): void {
    setter(value);
    setPage(1);
  }

  function openIntegration(integrationId: string, focusPatch?: boolean): void {
    router.push(
      focusPatch
        ? `/projects/${projectId}/catalog/${integrationId}?focus=patch#patch-form`
        : `/projects/${projectId}/catalog/${integrationId}`,
    );
  }

  function clearPromptFilters(): void {
    resetPageAndSet(setSearch, "");
    resetPageAndSet(setQaStatus, "");
    resetPageAndSet(setPattern, "");
    resetPageAndSet(setBrand, "");
  }

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
          <label className="flex-1">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Search</span>
            <input
              value={search}
              onChange={(event) => resetPageAndSet(setSearch, event.target.value)}
              placeholder="Interface, system, description..."
              className="app-input"
            />
          </label>
          <label className="min-w-[12rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">QA Status</span>
            <select
              value={qaStatus}
              onChange={(event) => resetPageAndSet(setQaStatus, event.target.value)}
              className="app-input"
            >
              <option value="">All</option>
              <option value="OK">OK</option>
              <option value="REVISAR">REVISAR</option>
              <option value="PENDING">PENDING</option>
            </select>
          </label>
          <label className="min-w-[14rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Pattern</span>
            <select
              value={pattern}
              onChange={(event) => resetPageAndSet(setPattern, event.target.value)}
              className="app-input"
            >
              <option value="">All</option>
              {patterns.map((patternDefinition: PatternDefinition) => (
                <option key={patternDefinition.pattern_id} value={patternDefinition.pattern_id}>
                  {patternDefinition.pattern_id} {patternDefinition.name}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[12rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Brand</span>
            <select
              value={brand}
              onChange={(event) => resetPageAndSet(setBrand, event.target.value)}
              className="app-input"
            >
              <option value="">All</option>
              {brands.map((brandName: string) => (
                <option key={brandName} value={brandName}>
                  {brandName}
                </option>
              ))}
            </select>
          </label>
          <div className="app-theme-chip">{data.total} integrations</div>
        </div>

        {hasActiveFilters ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)]">Filters:</span>
            {search ? (
              <button
                type="button"
                onClick={() => resetPageAndSet(setSearch, "")}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)]"
              >
                &quot;{search.length > 20 ? `${search.slice(0, 20)}…` : search}&quot;
                <X className="h-3 w-3" />
              </button>
            ) : null}
            {qaStatus ? (
              <button
                type="button"
                onClick={() => resetPageAndSet(setQaStatus, "")}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)]"
              >
                QA: {qaStatus}
                <X className="h-3 w-3" />
              </button>
            ) : null}
            {pattern ? (
              <button
                type="button"
                onClick={() => resetPageAndSet(setPattern, "")}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)]"
              >
                Pattern: {pattern}
                <X className="h-3 w-3" />
              </button>
            ) : null}
            {brand ? (
              <button
                type="button"
                onClick={() => resetPageAndSet(setBrand, "")}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-medium text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)]"
              >
                Brand: {brand}
                <X className="h-3 w-3" />
              </button>
            ) : null}
            {sourceSystem ? <span className="app-theme-chip">Source: {sourceSystem}</span> : null}
            {destinationSystem ? <span className="app-theme-chip">Destination: {destinationSystem}</span> : null}
            {hasPromptFilters ? (
              <button
                type="button"
                onClick={clearPromptFilters}
                className="ml-1 text-xs font-semibold text-[var(--color-accent)] transition hover:underline"
              >
                Clear all
              </button>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="app-table-shell">
        <div className="border-b border-[var(--color-border)] px-6 py-4 md:hidden">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Review the integration route, QA status, and pattern assignment without losing the thread of the catalog.
          </p>
        </div>

        <div className="space-y-4 p-4 md:hidden">
          {loading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <article
                key={index}
                className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm"
              >
                <div className="space-y-3">
                  <div className="skeleton h-4 w-24" />
                  <div className="skeleton h-6 w-4/5" />
                  <div className="skeleton h-4 w-3/5" />
                  <div className="grid grid-cols-2 gap-3">
                    <div className="skeleton h-16 w-full" />
                    <div className="skeleton h-16 w-full" />
                  </div>
                </div>
              </article>
            ))
          ) : (
            data.integrations.map((integration: Integration) => {
              const patternDefinition = integration.selected_pattern
                ? patternMap.get(integration.selected_pattern)
                : null;
              return (
                <article
                  key={integration.id}
                  onClick={() => openIntegration(integration.id)}
                  className="cursor-pointer rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm transition hover:border-[var(--color-accent)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                        #{integration.seq_number}
                      </p>
                      <h3
                        className="mt-2 truncate text-lg font-semibold text-[var(--color-text-primary)]"
                        title={integration.interface_name ?? undefined}
                      >
                        {integration.interface_name ?? integration.interface_id ?? "Untitled integration"}
                      </h3>
                      <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">
                        {integration.interface_id ?? ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        openIntegration(integration.id, true);
                      }}
                      title="Edit pattern"
                      aria-label={`Edit pattern for ${integration.interface_name ?? integration.interface_id ?? "integration"}`}
                      className="rounded-full p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                  </div>

                  <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
                    <span className="max-w-[7rem] truncate" title={integration.source_system ?? undefined}>
                      {integration.source_system ?? "—"}
                    </span>
                    <span className="text-[var(--color-text-muted)]">→</span>
                    <span className="max-w-[7rem] truncate" title={integration.destination_system ?? undefined}>
                      {integration.destination_system ?? "—"}
                    </span>
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <PatternBadge
                      patternId={integration.selected_pattern}
                      name={patternDefinition?.name ?? null}
                      category={patternDefinition?.category ?? null}
                      compact
                    />
                    <ComplexityBadge value={integration.complexity} />
                    <QaBadge status={integration.qa_status} />
                  </div>
                </article>
              );
            })
          )}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
            <thead className="app-table-header">
              <tr>
                <th className="w-12 px-6 py-4">#</th>
                <th className="px-6 py-4">Integration</th>
                <th className="px-6 py-4">Flow</th>
                <th className="px-6 py-4">Pattern</th>
                <th className="px-6 py-4">Complexity</th>
                <th className="px-6 py-4">QA</th>
                <th className="w-16 px-6 py-4 text-right">···</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-table-border)]">
              {loading
                ? Array.from({ length: 7 }).map((_, index) => <SkeletonRow key={index} />)
                : data.integrations.map((integration: Integration) => {
                    const patternDefinition = integration.selected_pattern
                      ? patternMap.get(integration.selected_pattern)
                      : null;
                    return (
                      <tr
                        key={integration.id}
                        onClick={() => openIntegration(integration.id)}
                        className="app-table-row cursor-pointer text-sm transition"
                      >
                        <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">
                          {integration.seq_number}
                        </td>
                        <td className="px-6 py-4">
                          <p
                            className="max-w-[22rem] truncate font-semibold text-[var(--color-text-primary)]"
                            title={integration.interface_name ?? undefined}
                          >
                            {integration.interface_name ?? integration.interface_id ?? "—"}
                          </p>
                          <p className="mt-0.5 font-mono text-xs text-[var(--color-text-muted)]">
                            {integration.interface_id ?? ""}
                          </p>
                        </td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
                            <span className="max-w-[7rem] truncate" title={integration.source_system ?? undefined}>
                              {integration.source_system ?? "—"}
                            </span>
                            <span className="text-[var(--color-text-muted)]">→</span>
                            <span className="max-w-[7rem] truncate" title={integration.destination_system ?? undefined}>
                              {integration.destination_system ?? "—"}
                            </span>
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <PatternBadge
                            patternId={integration.selected_pattern}
                            name={patternDefinition?.name ?? null}
                            category={patternDefinition?.category ?? null}
                            compact
                          />
                        </td>
                        <td className="px-6 py-4">
                          <ComplexityBadge value={integration.complexity} />
                        </td>
                        <td className="px-6 py-4">
                          <QaBadge status={integration.qa_status} />
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              openIntegration(integration.id, true);
                            }}
                            title="Edit pattern"
                            aria-label={`Edit pattern for ${integration.interface_name ?? integration.interface_id ?? "integration"}`}
                            className="rounded-full p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>

        {!loading && data.integrations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 rounded-full bg-[var(--color-surface-3)] p-5">
              <SearchX className="h-8 w-8 text-[var(--color-text-muted)]" />
            </div>
            <p className="text-lg font-semibold text-[var(--color-text-primary)]">No integrations found</p>
            <p className="mt-2 max-w-xs text-sm text-[var(--color-text-secondary)]">
              {hasActiveFilters
                ? "Try adjusting your filters or clearing the search."
                : `${projectName} has no integrations yet. Import a workbook to get started.`}
            </p>
            {hasPromptFilters ? (
              <button
                type="button"
                onClick={clearPromptFilters}
                className="mt-4 app-button-secondary px-4 py-2 text-sm"
              >
                Clear filters
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-col gap-4 border-t border-[var(--color-border)] px-6 py-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
            <span>Show</span>
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <span>
              of <strong>{data.total}</strong> integrations
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage(1)}
              disabled={page <= 1 || loading}
              className="app-button-secondary px-3 py-2 text-xs"
              title="First page"
            >
              «
            </button>
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
              className="app-button-secondary px-4 py-2"
            >
              Prev
            </button>
            <span className="min-w-[6rem] text-center text-sm text-[var(--color-text-secondary)]">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages || loading}
              className="app-button-secondary px-4 py-2"
            >
              Next
            </button>
            <button
              type="button"
              onClick={() => setPage(totalPages)}
              disabled={page >= totalPages || loading}
              className="app-button-secondary px-3 py-2 text-xs"
              title="Last page"
            >
              »
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
