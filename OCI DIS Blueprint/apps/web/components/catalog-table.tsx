"use client";

/* Interactive catalog table with filters, search, contextual actions, and pagination. */

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, Pencil, SearchX, X } from "lucide-react";

import { ComplexityBadge } from "@/components/complexity-badge";
import { PatternBadge } from "@/components/pattern-badge";
import { QaBadge } from "@/components/qa-badge";
import { SkeletonRow } from "@/components/skeleton";
import { api } from "@/lib/api";
import { displayQaStatus, formatNumber } from "@/lib/format";
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
  const [pageSize, setPageSize] = useState<number>(initialPage.page_size);
  const [data, setData] = useState<CatalogPage>(initialPage);
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string>(
    initialPage.integrations[0]?.id ?? "",
  );
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const skippedInitialLoad = useRef<boolean>(false);
  const skippedInitialUrlSync = useRef<boolean>(false);
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      if (!skippedInitialLoad.current) {
        skippedInitialLoad.current = true;
        return;
      }
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
    if (!skippedInitialUrlSync.current) {
      skippedInitialUrlSync.current = true;
      return;
    }
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
  const patternMap = useMemo(
    () =>
      new Map<string, PatternDefinition>(
        patterns.map((patternDefinition: PatternDefinition) => [
          patternDefinition.pattern_id,
          patternDefinition,
        ]),
      ),
    [patterns],
  );
  const selectedIntegration = useMemo(
    () =>
      data.integrations.find((integration) => integration.id === selectedIntegrationId) ??
      data.integrations[0] ??
      null,
    [data.integrations, selectedIntegrationId],
  );

  useEffect(() => {
    if (data.integrations.length === 0) {
      setSelectedIntegrationId("");
      return;
    }
    if (!data.integrations.some((integration) => integration.id === selectedIntegrationId)) {
      setSelectedIntegrationId(data.integrations[0].id);
    }
  }, [data.integrations, selectedIntegrationId]);

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
      <section className="console-toolbar">
        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <label className="lg:w-60">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Search</span>
            <input
              value={search}
              onChange={(event) => resetPageAndSet(setSearch, event.target.value)}
              placeholder="Interface, system, description..."
              className="app-input"
            />
          </label>
          <label className="lg:w-48">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">QA Status</span>
            <select
              value={qaStatus}
              onChange={(event) => resetPageAndSet(setQaStatus, event.target.value)}
              className="app-input"
            >
              <option value="">All</option>
              <option value="OK">OK</option>
              <option value="REVISAR">{displayQaStatus("REVISAR")}</option>
              <option value="PENDING">{displayQaStatus("PENDING")}</option>
            </select>
          </label>
          <label className="lg:w-64">
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
          <label className="lg:w-48">
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
          <div className="flex flex-1 items-center justify-end gap-2">
            <span className="console-pill font-mono uppercase tracking-[0.16em]">
              {data.total} integrations
            </span>
          </div>
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
                QA: {displayQaStatus(qaStatus)}
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
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <p className="app-label">Catalog Grid</p>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
              Select a row to open the preview panel, or jump directly into the full integration record.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDrawerOpen((current) => !current)}
            disabled={!selectedIntegration}
            className="app-button-secondary px-4 py-2 text-sm"
          >
            {drawerOpen ? "Hide Preview" : "Show Preview"}
          </button>
        </div>
        <div className={drawerOpen ? "grid xl:grid-cols-[minmax(0,1fr)_20rem]" : "grid xl:grid-cols-1"}>
          <div className="min-w-0 border-[var(--color-border)] xl:border-r">
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
                  className="cursor-pointer rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md"
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
                    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-secondary)]">
                      Detail
                      <ChevronRight className="h-3.5 w-3.5" />
                    </span>
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

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <span className="text-xs text-[var(--color-text-secondary)]">
                      Tap the card for the full integration record.
                    </span>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        openIntegration(integration.id, true);
                      }}
                      title="Jump to architect patch form"
                      aria-label={`Jump to architect patch for ${integration.interface_name ?? integration.interface_id ?? "integration"}`}
                      className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]"
                    >
                      Patch
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full table-fixed divide-y divide-[var(--color-table-border)] text-left">
            <colgroup>
              <col className="w-12" />
              <col className="w-[32%]" />
              <col className="w-[24%]" />
              <col className="w-[19%]" />
              <col className="w-[11%]" />
              <col className="w-[10%]" />
              <col className="w-12" />
            </colgroup>
            <thead className="app-table-header">
              <tr>
                <th className="px-3 py-3">#</th>
                <th className="px-3 py-3">Integration</th>
                <th className="px-3 py-3">Flow</th>
                <th className="px-3 py-3">Pattern</th>
                <th className="px-3 py-3">Complexity</th>
                <th className="px-3 py-3">QA</th>
                <th className="px-3 py-3 text-right">···</th>
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
                        onClick={() => {
                          setSelectedIntegrationId(integration.id);
                          setDrawerOpen(true);
                        }}
                        className={[
                          "app-table-row group cursor-pointer text-sm transition",
                          selectedIntegration?.id === integration.id ? "bg-[var(--color-accent-soft)]" : "",
                        ].join(" ")}
                      >
                        <td className="px-3 py-3 font-medium text-[var(--color-text-primary)]">
                          {integration.seq_number}
                        </td>
                        <td className="px-3 py-3">
                          <p
                            className="truncate font-semibold text-[var(--color-text-primary)]"
                            title={integration.interface_name ?? undefined}
                          >
                            {integration.interface_name ?? integration.interface_id ?? "—"}
                          </p>
                          <p className="mt-0.5 truncate text-xs text-[var(--color-text-muted)]" title={integration.business_process ?? undefined}>
                            <span className="font-mono">{integration.interface_id ?? integration.id.slice(0, 8)}</span>
                            {integration.business_process ? ` · ${integration.business_process}` : ""}
                          </p>
                        </td>
                        <td className="overflow-hidden px-3 py-3">
                          <span className="inline-flex w-full min-w-0 items-center gap-1.5 overflow-hidden text-xs text-[var(--color-text-secondary)]">
                            <span className="truncate" title={integration.source_system ?? undefined}>
                              {integration.source_system ?? "—"}
                            </span>
                            <span className="shrink-0 text-[var(--color-text-muted)]">→</span>
                            <span className="truncate" title={integration.destination_system ?? undefined}>
                              {integration.destination_system ?? "—"}
                            </span>
                          </span>
                        </td>
                        <td className="overflow-hidden px-3 py-3">
                          <PatternBadge
                            patternId={integration.selected_pattern}
                            name={patternDefinition?.name ?? null}
                            category={patternDefinition?.category ?? null}
                            compact
                          />
                        </td>
                        <td className="px-3 py-3">
                          <ComplexityBadge value={integration.complexity} />
                        </td>
                        <td className="px-3 py-3">
                          <QaBadge status={integration.qa_status} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              openIntegration(integration.id, true);
                            }}
                            title="Jump to architect patch form"
                            aria-label={`Jump to architect patch for ${integration.interface_name ?? integration.interface_id ?? "integration"}`}
                            className="inline-flex items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-text-secondary)] transition hover:border-[var(--color-accent)] hover:text-[var(--color-text-primary)]"
                          >
                            <Pencil className="h-3.5 w-3.5" />
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
              aria-label="Rows per page"
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
          </div>

          <aside className={drawerOpen ? "hidden min-w-0 bg-[var(--color-surface)] xl:block" : "hidden"}>
            {selectedIntegration ? (
              <div className="sticky top-[3.5rem] max-h-[calc(100vh-3.5rem)] overflow-y-auto">
                <div className="border-b border-[var(--color-border)] px-5 py-4">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)]">
                    <span className="font-mono">
                      {selectedIntegration.interface_id ?? selectedIntegration.id.slice(0, 8)}
                    </span>
                    <span className="console-pill">Drawer</span>
                  </div>
                  <h2 className="mt-3 text-xl font-semibold leading-snug text-[var(--color-text-primary)]">
                    {selectedIntegration.interface_name ?? selectedIntegration.interface_id ?? "Untitled integration"}
                  </h2>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {selectedIntegration.description ?? "No description captured for this integration yet."}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <QaBadge status={selectedIntegration.qa_status} />
                    <ComplexityBadge value={selectedIntegration.complexity} />
                    <PatternBadge
                      patternId={selectedIntegration.selected_pattern}
                      name={
                        selectedIntegration.selected_pattern
                          ? patternMap.get(selectedIntegration.selected_pattern)?.name ?? null
                          : null
                      }
                      category={
                        selectedIntegration.selected_pattern
                          ? patternMap.get(selectedIntegration.selected_pattern)?.category ?? null
                          : null
                      }
                      compact
                    />
                  </div>
                </div>

                <div className="flex justify-between gap-1 border-b border-[var(--color-border)] px-3">
                  {["Overview", "Canvas", "Volumetry", "QA", "History"].map((tabLabel, index) => (
                    <span
                      key={tabLabel}
                      className={[
                        "whitespace-nowrap border-b-2 px-1.5 py-3 text-[11px] font-semibold",
                        index === 0
                          ? "border-[var(--color-text-primary)] text-[var(--color-text-primary)]"
                          : "border-transparent text-[var(--color-text-muted)]",
                      ].join(" ")}
                    >
                      {tabLabel}
                    </span>
                  ))}
                </div>

                <div className="space-y-5 px-5 py-4">
                  <section>
                    <p className="app-label">Endpoints</p>
                    <div className="mt-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                        {selectedIntegration.source_system ?? "Unknown source"}
                      </p>
                      <p className="my-2 text-lg font-semibold text-[var(--color-accent)]">→</p>
                      <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                        {selectedIntegration.destination_system ?? "Unknown destination"}
                      </p>
                      <p className="mt-3 text-xs text-[var(--color-text-muted)]">
                        {selectedIntegration.trigger_type ?? "Trigger not set"}
                      </p>
                    </div>
                  </section>

                  <section>
                    <p className="app-label">Volumetry</p>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
                        <p className="text-xs text-[var(--color-text-muted)]">Payload</p>
                        <p className="mt-1 font-mono text-lg font-semibold text-[var(--color-text-primary)]">
                          {formatNumber(selectedIntegration.payload_per_execution_kb, 1)} KB
                        </p>
                      </div>
                      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
                        <p className="text-xs text-[var(--color-text-muted)]">Exec / day</p>
                        <p className="mt-1 font-mono text-lg font-semibold text-[var(--color-text-primary)]">
                          {formatNumber(selectedIntegration.executions_per_day, 1)}
                        </p>
                      </div>
                    </div>
                  </section>

                  <section>
                    <p className="app-label">QA Findings</p>
                    {selectedIntegration.qa_reasons.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {selectedIntegration.qa_reasons.slice(0, 4).map((reason) => (
                          <div
                            key={reason}
                            className="rounded-xl border border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
                          >
                            {reason.replace(/_/g, " ")}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 rounded-xl border border-[var(--color-qa-ok-border)] bg-[var(--color-qa-ok-bg)] px-3 py-2 text-sm text-[var(--color-qa-ok-text)]">
                        No QA findings on this row.
                      </p>
                    )}
                  </section>

                  <div className="flex flex-wrap gap-2 border-t border-[var(--color-border)] pt-4">
                    <button
                      type="button"
                      onClick={() => openIntegration(selectedIntegration.id)}
                      className="app-button-primary px-4 py-2 text-sm"
                    >
                      Open full record
                    </button>
                    <button
                      type="button"
                      onClick={() => openIntegration(selectedIntegration.id, true)}
                      className="app-button-secondary px-4 py-2 text-sm"
                    >
                      Patch
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-sm text-[var(--color-text-secondary)]">
                Select an integration to open the drawer.
              </div>
            )}
          </aside>
        </div>
      </section>
    </div>
  );
}
