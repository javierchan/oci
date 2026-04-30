"use client";

/* Filter, color mode, zoom, and export controls for the system dependency graph. */

import { Hand, MousePointer } from "lucide-react";
import type { RefObject } from "react";

import { GraphExportButton } from "@/components/graph-export-button";
import { displayQaStatus } from "@/lib/format";
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
  mode: GraphMode;
  onModeChange: (_mode: GraphMode) => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  meta: GraphMeta;
  svgRef: RefObject<SVGSVGElement>;
};

export function GraphControls({
  projectId,
  filters,
  onFilterChange,
  selectedSystem,
  systemOptions,
  onSystemChange,
  colorMode,
  onColorModeChange,
  mode,
  onModeChange,
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  meta,
  svgRef,
}: GraphControlsProps): JSX.Element {
  return (
    <section className="app-card pointer-events-auto p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:flex-wrap xl:items-end">
        <label className="min-w-[14rem]">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Business Process</span>
          <select
            value={filters.business_process ?? ""}
            onChange={(event) => onFilterChange("business_process", event.target.value)}
            className="app-input"
          >
            <option value="">All</option>
            {meta.business_processes.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="min-w-[12rem]">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Brand</span>
          <select
            value={filters.brand ?? ""}
            onChange={(event) => onFilterChange("brand", event.target.value)}
            className="app-input"
          >
            <option value="">All</option>
            {meta.brands.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="min-w-[12rem]">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">QA Status</span>
          <select
            value={filters.qa_status ?? ""}
            onChange={(event) => onFilterChange("qa_status", event.target.value)}
            className="app-input"
          >
            <option value="">All</option>
            <option value="OK">OK</option>
            <option value="REVISAR">{displayQaStatus("REVISAR")}</option>
            <option value="PENDING">{displayQaStatus("PENDING")}</option>
          </select>
        </label>

        <label className="min-w-[14rem]">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">System</span>
          <select
            value={selectedSystem}
            onChange={(event) => onSystemChange(event.target.value)}
            className="app-input"
          >
            <option value="">All</option>
            {systemOptions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] p-1">
          <button
            type="button"
            onClick={() => onColorModeChange("qa")}
            className={[
              "rounded-xl px-4 py-2 text-sm font-semibold transition",
              colorMode === "qa"
                ? "bg-[var(--color-accent)] text-white"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
            ].join(" ")}
          >
            QA
          </button>
          <button
            type="button"
            onClick={() => onColorModeChange("bp")}
            className={[
              "rounded-xl px-4 py-2 text-sm font-semibold transition",
              colorMode === "bp"
                ? "bg-[var(--color-accent)] text-white"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
            ].join(" ")}
          >
            Business Process
          </button>
        </div>

        <div className="flex items-center gap-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] p-1">
          <button
            type="button"
            onClick={() => onModeChange("select")}
            title="Select (V)"
            className={mode === "select" ? "rounded p-2 bg-[var(--color-accent)] text-white" : "rounded p-2 text-[var(--color-text-secondary)]"}
          >
            <MousePointer className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => onModeChange("pan")}
            title="Pan (H)"
            className={mode === "pan" ? "rounded p-2 bg-[var(--color-accent)] text-white" : "rounded p-2 text-[var(--color-text-secondary)]"}
          >
            <Hand className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onZoomOut}
            className="app-button-secondary px-4 py-2"
          >
            -
          </button>
          <span className="app-theme-chip">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={onZoomIn}
            className="app-button-secondary px-4 py-2"
          >
            +
          </button>
          <button
            type="button"
            onClick={onZoomReset}
            className="app-button-secondary px-4 py-2"
          >
            Reset
          </button>
        </div>

        <GraphExportButton projectId={projectId} svgRef={svgRef} />
      </div>
    </section>
  );
}
