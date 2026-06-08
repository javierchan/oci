"use client";

/* Floating toolbar for the integration topology workspace. */

import Link from "next/link";
import { Hand, List, Maximize2, MousePointer, Network, ZoomIn, ZoomOut } from "lucide-react";
import type { RefObject } from "react";

import { GraphExportButton } from "@/components/graph-export-button";
import { displayQaStatus } from "@/lib/format";
import type { QaTotals, TopologyLayoutMode } from "@/lib/topology";
import type { GraphMeta, GraphParams } from "@/lib/types";

type GraphMode = "select" | "pan";

type GraphControlsProps = {
  projectId: string;
  filters: GraphParams;
  onFilterChange: (_field: keyof GraphParams, _value: string) => void;
  selectedSystem: string;
  systemOptions: string[];
  onSystemChange: (_value: string) => void;
  colorMode: "qa" | "bp";
  onColorModeChange: (_mode: "qa" | "bp") => void;
  layoutMode: TopologyLayoutMode;
  onLayoutModeChange: (_mode: TopologyLayoutMode) => void;
  mode: GraphMode;
  onModeChange: (_mode: GraphMode) => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onClearSelection: () => void;
  hasSelection: boolean;
  meta: GraphMeta;
  qaTotals: QaTotals;
  degradedSystemCount: number;
  svgRef: RefObject<SVGSVGElement>;
};

function compactCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function iconButtonClasses(active = false): string {
  return [
    "inline-flex h-9 w-9 items-center justify-center rounded-lg border text-sm font-semibold transition",
    active
      ? "border-[var(--color-text-primary)] bg-[var(--color-text-primary)] text-[var(--color-surface)]"
      : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)]",
  ].join(" ");
}

function pillClasses(active: boolean): string {
  return [
    "inline-flex min-h-9 items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition",
    active
      ? "border-[var(--color-text-primary)] bg-[var(--color-text-primary)] text-[var(--color-surface)]"
      : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)]",
  ].join(" ");
}

export function GraphControls({
  projectId,
  filters,
  onFilterChange,
  selectedSystem,
  systemOptions,
  onSystemChange,
  colorMode,
  onColorModeChange,
  layoutMode,
  onLayoutModeChange,
  mode,
  onModeChange,
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onClearSelection,
  hasSelection,
  meta,
  qaTotals,
  degradedSystemCount,
  svgRef,
}: GraphControlsProps): JSX.Element {
  const qaFilter = filters.qa_status ?? "";

  return (
    <section className="pointer-events-none absolute left-4 right-4 top-4 z-20 space-y-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="pointer-events-auto flex w-full max-w-[40rem] flex-wrap items-center gap-3 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 shadow-sm">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-600" />
          <span className="text-sm font-semibold text-[var(--color-text-primary)]">Live topology</span>
          <span className="text-sm text-[var(--color-text-muted)]">
            {compactCount(meta.integration_count)} integrations
          </span>
          <span className="text-sm text-[var(--color-text-muted)]">{compactCount(meta.node_count)} systems</span>
          <span className="text-sm text-[var(--color-text-muted)]">synced now</span>
        </div>

        <div className="pointer-events-auto flex flex-wrap items-center gap-2">
          <button type="button" onClick={onZoomOut} className={iconButtonClasses()} title="Zoom out" aria-label="Zoom out">
            <ZoomOut className="h-4 w-4" />
          </button>
          <button type="button" onClick={onZoomIn} className={iconButtonClasses(true)} title="Zoom in" aria-label="Zoom in">
            <ZoomIn className="h-4 w-4" />
          </button>
          <button type="button" onClick={onZoomReset} className={iconButtonClasses()} title="Fit map" aria-label="Fit map">
            <Maximize2 className="h-4 w-4" />
          </button>
          <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs font-semibold text-[var(--color-text-secondary)] shadow-sm">
            {Math.round(zoom * 100)}%
          </span>

          <span className="h-8 w-px bg-[var(--color-border)]" />

          <button
            type="button"
            onClick={() => onModeChange("select")}
            className={iconButtonClasses(mode === "select")}
            title="Select"
            aria-label="Select"
          >
            <MousePointer className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onModeChange("pan")}
            className={iconButtonClasses(mode === "pan")}
            title="Pan"
            aria-label="Pan"
          >
            <Hand className="h-4 w-4" />
          </button>

          <span className="h-8 w-px bg-[var(--color-border)]" />

          <button
            type="button"
            onClick={() => onLayoutModeChange("cluster")}
            className={pillClasses(layoutMode === "cluster")}
          >
            Cluster
          </button>
          <button
            type="button"
            onClick={() => onLayoutModeChange("free")}
            className={pillClasses(layoutMode === "free")}
          >
            Free
          </button>

          <Link href={`/projects/${projectId}/catalog`} className={pillClasses(false)}>
            <List className="h-4 w-4" />
            Switch to table
          </Link>
          <GraphExportButton projectId={projectId} svgRef={svgRef} />
        </div>
      </div>

      <div className="pointer-events-auto flex flex-col gap-3 xl:max-w-[73rem]">
        {degradedSystemCount > 0 ? (
          <div className="max-w-[39rem] rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900 shadow-sm dark:border-rose-900 dark:bg-rose-950 dark:text-rose-100">
            {degradedSystemCount} systems show degraded QA. Click any review or pending edge to triage.
          </div>
        ) : null}

        <div className="flex max-w-[72rem] flex-wrap items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 shadow-sm">
          <button type="button" onClick={() => onFilterChange("qa_status", "")} className={pillClasses(qaFilter === "")}>
            All patterns <span className="font-mono opacity-70">{compactCount(qaTotals.total)}</span>
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "OK")} className={pillClasses(qaFilter === "OK")}>
            <span className="h-2 w-2 rounded-full bg-[#15803d]" />
            QA OK <span className="font-mono opacity-70">{compactCount(qaTotals.ok)}</span>
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "REVISAR")} className={pillClasses(qaFilter === "REVISAR")}>
            <span className="h-2 w-2 rounded-full bg-[#b45309]" />
            QA {displayQaStatus("REVISAR")} <span className="font-mono opacity-70">{compactCount(qaTotals.review)}</span>
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "PENDING")} className={pillClasses(qaFilter === "PENDING")}>
            <span className="h-2 w-2 rounded-full bg-[#b91c1c]" />
            QA {displayQaStatus("PENDING")} <span className="font-mono opacity-70">{compactCount(qaTotals.pending)}</span>
          </button>

          <span className="hidden h-8 w-px bg-[var(--color-border)] md:block" />

          <label className="inline-flex min-h-9 items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
            <Network className="h-4 w-4" />
            <select
              value={filters.business_process ?? ""}
              onChange={(event) => onFilterChange("business_process", event.target.value)}
              className="max-w-[12rem] bg-transparent text-xs font-semibold text-[var(--color-text-primary)] outline-none"
              aria-label="Filter by business process"
            >
              <option value="">Business process</option>
              {meta.business_processes.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="inline-flex min-h-9 items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
            Brand
            <select
              value={filters.brand ?? ""}
              onChange={(event) => onFilterChange("brand", event.target.value)}
              className="max-w-[9rem] bg-transparent text-xs font-semibold text-[var(--color-text-primary)] outline-none"
              aria-label="Filter by brand"
            >
              <option value="">All</option>
              {meta.brands.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <label className="inline-flex min-h-9 items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
            Focus
            <select
              value={selectedSystem}
              onChange={(event) => onSystemChange(event.target.value)}
              className="max-w-[12rem] bg-transparent text-xs font-semibold text-[var(--color-text-primary)] outline-none"
              aria-label="Focus system"
            >
              <option value="">All systems</option>
              {systemOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          <button type="button" onClick={() => onColorModeChange("qa")} className={pillClasses(colorMode === "qa")}>
            QA color
          </button>
          <button type="button" onClick={() => onColorModeChange("bp")} className={pillClasses(colorMode === "bp")}>
            Process color
          </button>

          {hasSelection ? (
            <button type="button" onClick={onClearSelection} className={pillClasses(false)}>
              Show full topology
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
