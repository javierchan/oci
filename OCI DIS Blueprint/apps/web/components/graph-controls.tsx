"use client";

/* Compact command bar for topology navigation, filtering, risk triage, and export. */

import Link from "next/link";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  GitBranch,
  Hand,
  Layers3,
  List,
  Maximize2,
  MousePointer,
  ShieldAlert,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { ReactElement, RefObject } from "react";

import { GraphExportButton } from "@/components/graph-export-button";
import { TopologyCombobox } from "@/components/topology-combobox";
import { displayQaStatus } from "@/lib/format";
import type {
  QaTotals,
  TopologyLayoutMode,
  TopologyMetricMode,
  TopologyVisibilityMode,
} from "@/lib/topology";
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
  metricMode: TopologyMetricMode;
  onMetricModeChange: (_mode: TopologyMetricMode) => void;
  visibilityMode: TopologyVisibilityMode;
  onVisibilityModeChange: (_mode: TopologyVisibilityMode) => void;
  layoutMode: TopologyLayoutMode;
  onLayoutModeChange: (_mode: TopologyLayoutMode) => void;
  mode: GraphMode;
  onModeChange: (_mode: GraphMode) => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onClearSelection: () => void;
  onClearFilters: () => void;
  onOpenTriage: () => void;
  onReviewNext: () => void;
  loading: boolean;
  hasSelection: boolean;
  activeFilterCount: number;
  reviewedRiskCount: number;
  currentRiskSelected: boolean;
  meta: GraphMeta;
  qaTotals: QaTotals;
  degradedSystemCount: number;
  riskPathCount: number;
  svgRef: RefObject<SVGSVGElement>;
  compact?: boolean;
};

function compactCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function relativeFreshness(value: string | null): string {
  if (!value) {
    return "No catalog updates";
  }
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60_000));
  if (minutes < 1) {
    return "Updated now";
  }
  if (minutes < 60) {
    return `Updated ${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `Updated ${hours}h ago`;
  }
  return `Updated ${Math.floor(hours / 24)}d ago`;
}

function iconButtonClasses(active = false): string {
  return [
    "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]",
    active
      ? "border-[var(--color-text-primary)] bg-[var(--color-text-primary)] text-[var(--color-surface)]"
      : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)]",
  ].join(" ");
}

function segmentClasses(active: boolean): string {
  return [
    "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-accent)]",
    active
      ? "bg-[var(--color-text-primary)] text-[var(--color-surface)] shadow-sm"
      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]",
  ].join(" ");
}

function ControlTooltip({ label, children }: { label: string; children: ReactElement }): JSX.Element {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={7}
          className="z-[80] rounded-md bg-[var(--color-text-primary)] px-2.5 py-1.5 text-xs font-semibold text-[var(--color-surface)] shadow-lg"
        >
          {label}
          <Tooltip.Arrow className="fill-[var(--color-text-primary)]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
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
  metricMode,
  onMetricModeChange,
  visibilityMode,
  onVisibilityModeChange,
  layoutMode,
  onLayoutModeChange,
  mode,
  onModeChange,
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onClearSelection,
  onClearFilters,
  onOpenTriage,
  onReviewNext,
  loading,
  hasSelection,
  activeFilterCount,
  reviewedRiskCount,
  currentRiskSelected,
  meta,
  qaTotals,
  degradedSystemCount,
  riskPathCount,
  svgRef,
  compact = false,
}: GraphControlsProps): JSX.Element {
  const qaFilter = filters.qa_status ?? "";
  const reviewActionLabel = loading
    ? "Refreshing..."
    : riskPathCount === 0
    ? "No risks"
    : reviewedRiskCount >= riskPathCount
      ? "Restart review"
      : currentRiskSelected
        ? "Review next"
        : reviewedRiskCount > 0
          ? "Continue review"
          : "Start review";

  return (
    <Tooltip.Provider delayDuration={350}>
    <section className="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex flex-col gap-3 px-4 py-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="inline-flex items-center gap-2 font-semibold text-[var(--color-text-primary)]">
            <span className="h-2 w-2 rounded-full bg-emerald-600" />
            Governed topology
          </span>
          <span className="text-[var(--color-text-muted)]">{compactCount(meta.integration_count)} integrations</span>
          <span className="text-[var(--color-text-muted)]">{compactCount(meta.node_count)} systems</span>
          <span className="text-[var(--color-text-muted)]">{relativeFreshness(meta.latest_updated_at)}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1" aria-label="Map zoom controls">
            <ControlTooltip label="Zoom out">
              <button type="button" onClick={onZoomOut} className={iconButtonClasses()} aria-label="Zoom out">
                <ZoomOut className="h-4 w-4" />
              </button>
            </ControlTooltip>
            <ControlTooltip label="Zoom in">
              <button type="button" onClick={onZoomIn} className={iconButtonClasses()} aria-label="Zoom in">
                <ZoomIn className="h-4 w-4" />
              </button>
            </ControlTooltip>
            <ControlTooltip label="Fit topology">
              <button type="button" onClick={onZoomReset} className={iconButtonClasses()} aria-label="Fit topology">
                <Maximize2 className="h-4 w-4" />
              </button>
            </ControlTooltip>
            <span className="min-w-12 text-center text-xs font-semibold text-[var(--color-text-muted)]">
              {Math.round(zoom * 100)}%
            </span>
          </div>

          <div className="flex rounded-lg bg-[var(--color-surface-2)] p-1" aria-label="Map interaction mode">
            <button type="button" onClick={() => onModeChange("select")} aria-pressed={mode === "select"} className={segmentClasses(mode === "select")} title="Select">
              <MousePointer className="h-3.5 w-3.5" />
              Select
            </button>
            <button type="button" onClick={() => onModeChange("pan")} aria-pressed={mode === "pan"} className={segmentClasses(mode === "pan")} title="Pan">
              <Hand className="h-3.5 w-3.5" />
              Pan
            </button>
          </div>

          <div className="flex rounded-lg bg-[var(--color-surface-2)] p-1" aria-label="Topology layout">
            <button type="button" onClick={() => onLayoutModeChange("cluster")} aria-pressed={layoutMode === "cluster"} className={segmentClasses(layoutMode === "cluster")}>
              <Layers3 className="h-3.5 w-3.5" />
              Domains
            </button>
            <button type="button" onClick={() => onLayoutModeChange("flow")} aria-pressed={layoutMode === "flow"} className={segmentClasses(layoutMode === "flow")}>
              <GitBranch className="h-3.5 w-3.5" />
              Flow
            </button>
          </div>

          <ControlTooltip label="Open catalog table">
            <Link href={`/projects/${projectId}/catalog`} className={iconButtonClasses()} aria-label="Open catalog table">
              <List className="h-4 w-4" />
            </Link>
          </ControlTooltip>
          <GraphExportButton projectId={projectId} svgRef={svgRef} />
        </div>
      </div>

      <div className="grid gap-2 border-t border-[var(--color-border)] px-4 py-2 xl:grid-cols-[minmax(18rem,0.8fr)_minmax(0,2fr)] xl:items-center">
        <div className="flex min-w-0 items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <button type="button" onClick={onOpenTriage} className="min-w-0 flex-1 text-left hover:underline">
            <span className="block text-xs font-semibold">
              {compact
                ? `${riskPathCount} risk paths`
                : `${degradedSystemCount} systems · ${riskPathCount} paths require attention`}
            </span>
            <span className="mt-0.5 block text-[10px] font-semibold opacity-75" aria-live="polite">
              {reviewedRiskCount} of {riskPathCount} reviewed in this session
            </span>
          </button>
          <button
            type="button"
            onClick={onReviewNext}
            disabled={loading || riskPathCount === 0}
            className="min-h-9 shrink-0 rounded-md bg-amber-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-amber-200 dark:text-amber-950"
          >
            {reviewActionLabel}
          </button>
        </div>

        <div className={[
          "grid min-w-0 items-center gap-2 md:grid-cols-2",
          compact ? "" : "xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)_10rem]",
        ].join(" ")}>
          <TopologyCombobox
            label="Process"
            ariaLabel="Filter by business process family"
            value={filters.business_process_family ?? ""}
            options={meta.business_process_families}
            placeholder="All process families"
            onChange={(value) => onFilterChange("business_process_family", value)}
          />
          <TopologyCombobox
            label="Focus"
            ariaLabel="Focus system"
            value={selectedSystem}
            options={systemOptions}
            placeholder="Search a system"
            onChange={onSystemChange}
          />

          <label className="flex h-10 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs font-semibold text-[var(--color-text-secondary)]">
            Brand
            <select
              value={filters.brand ?? ""}
              onChange={(event) => onFilterChange("brand", event.target.value)}
              className="min-w-0 flex-1 bg-transparent font-semibold text-[var(--color-text-primary)] outline-none"
              aria-label="Filter by brand"
            >
              <option value="">All</option>
              {meta.brands.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-t border-[var(--color-border)] px-4 py-2">
        <div className="flex rounded-lg bg-[var(--color-surface-2)] p-1" aria-label="QA filter">
          <button type="button" onClick={() => onFilterChange("qa_status", "")} aria-pressed={qaFilter === ""} className={segmentClasses(qaFilter === "")}>
            All <span className="font-mono opacity-70">{compactCount(qaTotals.total)}</span>
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "OK")} aria-pressed={qaFilter === "OK"} className={segmentClasses(qaFilter === "OK")}>
            <span className="h-2 w-2 rounded-full bg-[#15803d]" /> OK {compactCount(qaTotals.ok)}
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "REVISAR")} aria-pressed={qaFilter === "REVISAR"} className={segmentClasses(qaFilter === "REVISAR")}>
            <span className="h-2 w-2 rounded-full bg-[#b45309]" /> {displayQaStatus("REVISAR")} {compactCount(qaTotals.review)}
          </button>
          <button type="button" onClick={() => onFilterChange("qa_status", "PENDING")} aria-pressed={qaFilter === "PENDING"} className={segmentClasses(qaFilter === "PENDING")}>
            <span className="h-2 w-2 rounded-full bg-[#b91c1c]" /> {displayQaStatus("PENDING")} {compactCount(qaTotals.pending)}
          </button>
        </div>

        {activeFilterCount > 0 ? (
          <button type="button" onClick={onClearFilters} className="rounded-md px-3 py-2 text-xs font-semibold text-[var(--color-accent)] hover:bg-[var(--color-hover)]">
            Clear filters ({activeFilterCount})
          </button>
        ) : hasSelection ? (
          <button type="button" onClick={onClearSelection} className="rounded-md px-3 py-2 text-xs font-semibold text-[var(--color-accent)] hover:bg-[var(--color-hover)]">
            Clear selection
          </button>
        ) : null}

        <div className="ml-auto flex flex-wrap items-center justify-end gap-1" aria-label="Map display controls">
          <label className="flex min-h-8 items-center gap-2 rounded-lg bg-[var(--color-surface-2)] px-2.5 text-xs font-semibold text-[var(--color-text-secondary)]">
            <Activity className="h-3.5 w-3.5" />
            Weight
            <select
              value={metricMode}
              onChange={(event) => onMetricModeChange(event.target.value as TopologyMetricMode)}
              className="min-w-0 bg-transparent font-semibold text-[var(--color-text-primary)] outline-none"
              aria-label="Edge weight metric"
            >
              <option value="relationships">Count</option>
              <option value="executions">Exec / day</option>
              <option value="payload">Payload / hour</option>
            </select>
          </label>

          <div className="flex rounded-lg bg-[var(--color-surface-2)] p-1" aria-label="Path visibility">
            <button type="button" onClick={() => onVisibilityModeChange("priority")} aria-pressed={visibilityMode === "priority"} className={segmentClasses(visibilityMode === "priority")}>Priority paths</button>
            <button type="button" onClick={() => onVisibilityModeChange("all")} aria-pressed={visibilityMode === "all"} className={segmentClasses(visibilityMode === "all")}>All paths</button>
          </div>

          <div className="flex rounded-lg bg-[var(--color-surface-2)] p-1" aria-label="Map color mode">
            <button type="button" onClick={() => onColorModeChange("qa")} aria-pressed={colorMode === "qa"} className={segmentClasses(colorMode === "qa")}>QA color</button>
            <button type="button" onClick={() => onColorModeChange("bp")} aria-pressed={colorMode === "bp"} className={segmentClasses(colorMode === "bp")}>Process color</button>
          </div>
        </div>
      </div>
    </section>
    </Tooltip.Provider>
  );
}
