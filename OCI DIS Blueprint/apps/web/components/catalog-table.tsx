"use client";

/* Interactive catalog table with filters, search, contextual actions, and pagination. */

import { useDeferredValue, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ComplexityBadge } from "@/components/complexity-badge";
import { PatternBadge } from "@/components/pattern-badge";
import { QaBadge } from "@/components/qa-badge";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";
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
  const [rowsPerPage, setRowsPerPage] = useState<number>(initialPage.page_size || 20);
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
          page_size: rowsPerPage,
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
  }, [brand, deferredSearch, destinationSystem, page, pattern, projectId, qaStatus, rowsPerPage, sourceSystem]);

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

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const hasActiveFilters =
    search !== "" ||
    qaStatus !== "" ||
    pattern !== "" ||
    brand !== "" ||
    sourceSystem !== "" ||
    destinationSystem !== "";
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
          {hasActiveFilters ? (
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setQaStatus("");
                setPattern("");
                setBrand("");
                setPage(1);
              }}
              className="rounded border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-2)]"
            >
              Clear filters
            </button>
          ) : null}
          <div className="app-theme-chip">{data.total} integrations</div>
        </div>
        {sourceSystem || destinationSystem ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {sourceSystem ? (
              <span className="app-theme-chip">Source: {sourceSystem}</span>
            ) : null}
            {destinationSystem ? (
              <span className="app-theme-chip">Destination: {destinationSystem}</span>
            ) : null}
          </div>
        ) : null}
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="app-table-shell">
        <div className="border-b border-[var(--color-border)] px-6 py-4 md:hidden">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Mobile view prioritizes QA status, interface name, and quick actions so rows stay reviewable without horizontal scrolling.
          </p>
        </div>

        <div className="space-y-4 p-4 md:hidden">
          {data.integrations.map((integration: Integration) => {
            const patternDefinition = integration.selected_pattern
              ? patternMap.get(integration.selected_pattern)
              : null;
            return (
              <article
                key={integration.id}
                className="rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                      #{integration.seq_number} · {integration.brand ?? "Unassigned brand"}
                    </p>
                    <h3 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">
                      {integration.interface_name ?? "Untitled integration"}
                    </h3>
                    <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                      {integration.interface_id ?? "No Interface ID"} ·{" "}
                      {integration.source_row_id ? `Lineage ${integration.source_row_id.slice(0, 8)}` : "Manual capture"}
                    </p>
                  </div>
                  <QaBadge status={integration.qa_status} />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <PatternBadge
                    patternId={integration.selected_pattern}
                    name={patternDefinition?.name ?? null}
                    category={patternDefinition?.category ?? null}
                  />
                  <ComplexityBadge value={integration.complexity} />
                </div>

                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-2xl bg-[var(--color-surface-2)] px-3 py-3">
                    <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Frequency</dt>
                    <dd className="mt-2 font-medium text-[var(--color-text-primary)]">{integration.frequency ?? "—"}</dd>
                  </div>
                  <div className="rounded-2xl bg-[var(--color-surface-2)] px-3 py-3">
                    <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Payload KB</dt>
                    <dd className="mt-2 font-medium text-[var(--color-text-primary)]">
                      {formatNumber(integration.payload_per_execution_kb, 1)}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => openIntegration(integration.id)}
                    className="app-button-primary px-4 py-2"
                  >
                    View
                  </button>
                  <button
                    type="button"
                    onClick={() => openIntegration(integration.id, true)}
                    className="app-button-secondary px-4 py-2"
                  >
                    Edit
                  </button>
                </div>
              </article>
            );
          })}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
            <thead className="app-table-header">
              <tr>
                <th className="px-6 py-4">#</th>
                <th className="px-6 py-4">Interface ID</th>
                <th className="px-6 py-4">Brand</th>
                <th className="px-6 py-4">Interface Name</th>
                <th className="px-6 py-4">Pattern</th>
                <th className="px-6 py-4">Frequency</th>
                <th className="px-6 py-4">Complexity</th>
                <th className="px-6 py-4">Payload KB</th>
                <th className="px-6 py-4">QA Status</th>
                <th className="px-6 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-table-border)]">
              {data.integrations.map((integration: Integration) => {
                const patternDefinition = integration.selected_pattern
                  ? patternMap.get(integration.selected_pattern)
                  : null;
                return (
                  <tr
                    key={integration.id}
                    onClick={() => router.push(`/projects/${projectId}/catalog/${integration.id}`)}
                    className="app-table-row cursor-pointer text-sm transition"
                  >
                    <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">{integration.seq_number}</td>
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-[var(--color-text-primary)]">{integration.interface_id ?? "—"}</p>
                        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                          {integration.source_row_id ? `Lineage ${integration.source_row_id.slice(0, 8)}` : "Manual capture"}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-[var(--color-text-secondary)]">{integration.brand ?? "—"}</td>
                    <td className="px-6 py-4 text-[var(--color-text-primary)]">{integration.interface_name ?? "—"}</td>
                    <td className="px-6 py-4">
                      <PatternBadge
                        patternId={integration.selected_pattern}
                        name={patternDefinition?.name ?? null}
                        category={patternDefinition?.category ?? null}
                      />
                    </td>
                    <td className="px-6 py-4 text-[var(--color-text-secondary)]">{integration.frequency ?? "—"}</td>
                    <td className="px-6 py-4">
                      <ComplexityBadge value={integration.complexity} />
                    </td>
                    <td className="px-6 py-4 text-[var(--color-text-secondary)]">
                      {formatNumber(integration.payload_per_execution_kb, 1)}
                    </td>
                    <td className="px-6 py-4">
                      <QaBadge status={integration.qa_status} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            openIntegration(integration.id);
                          }}
                          className="app-link"
                        >
                          View
                        </button>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            openIntegration(integration.id, true);
                          }}
                          className="text-sm font-semibold text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)]"
                        >
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-4 border-t border-[var(--color-border)] px-6 py-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
            <div className="text-sm text-[var(--color-text-secondary)]">
              {loading ? "Refreshing catalog..." : `Page ${data.page} of ${totalPages}`}
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
              Rows per page
              <select
                value={rowsPerPage}
                onChange={(event) => {
                  const nextPageSize = Number(event.target.value);
                  setRowsPerPage(nextPageSize);
                  setPage(1);
                }}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
              className="app-button-secondary px-4 py-2"
            >
              Prev
            </button>
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages || loading}
              className="app-button-secondary px-4 py-2"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
