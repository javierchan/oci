"use client";

import { Activity, ChevronDown, ChevronUp, Clock3 } from "lucide-react";
import { useMemo } from "react";

import { formatCompactNumber } from "@/lib/format";
import type { TopologyPulseInsights } from "@/lib/topology-insights";
import type { TopologyMetricMode } from "@/lib/topology";

type TopologyPulseProps = {
  insights: TopologyPulseInsights;
  metricMode: TopologyMetricMode;
  expanded: boolean;
  selectedIntegrationId: string;
  onExpandedChange: (_expanded: boolean) => void;
  onIntegrationChange: (_integrationId: string) => void;
  onHighlightEdges: (_edgeIds: string[]) => void;
  onPinEdge: (_edgeId: string) => void;
};

const QA_COLORS = {
  ok: "var(--color-qa-ok-text)",
  review: "var(--color-qa-revisar-text)",
  pending: "var(--color-toast-error-text)",
};

function formatKilobytes(value: number | null): string {
  if (value === null) {
    return "—";
  }
  if (value >= 1024 * 1024) {
    return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value / 1024 / 1024)} GB`;
  }
  if (value >= 1024) {
    return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value / 1024)} MB`;
  }
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)} KB`;
}

function metricLabel(metricMode: TopologyMetricMode): string {
  if (metricMode === "executions") {
    return "executions / day";
  }
  if (metricMode === "payload") {
    return "payload / hour";
  }
  return "integrations";
}

function metricValue(value: number, metricMode: TopologyMetricMode): string {
  if (metricMode === "payload") {
    return formatKilobytes(value).replace("KB", "KB/h").replace("MB", "MB/h").replace("GB", "GB/h");
  }
  return formatCompactNumber(value);
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function Metric({
  label,
  value,
  detail,
  title,
}: {
  label: string;
  value: string;
  detail: string;
  title?: string;
}): JSX.Element {
  return (
    <div className="min-w-0 border-l border-[var(--color-border)] pl-3 first:border-l-0 first:pl-0">
      <p className="truncate text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-0.5 truncate text-sm font-semibold text-[var(--color-text-primary)]" title={title}>
        {value}
      </p>
      <p className="truncate text-[10px] text-[var(--color-text-muted)]">{detail}</p>
    </div>
  );
}

function QaPulse({ insights }: { insights: TopologyPulseInsights }): JSX.Element {
  const total = Math.max(insights.qa.total, 1);
  const values = [
    { key: "ok", label: "OK", value: insights.qa.ok, color: QA_COLORS.ok },
    { key: "review", label: "Review", value: insights.qa.review, color: QA_COLORS.review },
    { key: "pending", label: "Pending", value: insights.qa.pending, color: QA_COLORS.pending },
  ];
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">QA pulse</p>
      <div
        className="mt-3 flex h-2 overflow-hidden rounded-sm bg-[var(--color-surface-3)]"
        aria-label={`${insights.qa.ok} OK, ${insights.qa.review} need review, ${insights.qa.pending} pending`}
      >
        {values.map((item) => (
          item.value > 0 ? (
            <span
              key={item.key}
              style={{ width: `${(item.value / total) * 100}%`, backgroundColor: item.color }}
            />
          ) : null
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {values.map((item) => (
          <div key={item.key}>
            <p className="text-sm font-semibold" style={{ color: item.color }}>{item.value}</p>
            <p className="truncate text-[10px] text-[var(--color-text-muted)]">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function FlowBalance({ insights }: { insights: TopologyPulseInsights }): JSX.Element {
  const maximum = Math.max(insights.flow.leftValue, insights.flow.rightValue, 1);
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">Flow balance</p>
      <div className="mt-3 space-y-3">
        {[
          { label: insights.flow.leftLabel, value: insights.flow.leftValue },
          { label: insights.flow.rightLabel, value: insights.flow.rightValue },
        ].map((item, index) => (
          <div key={`${item.label}-${index}`}>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-[var(--color-text-secondary)]">{item.label}</span>
              <span className="font-semibold text-[var(--color-text-primary)]">{item.value}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-sm bg-[var(--color-surface-3)]">
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${(item.value / maximum) * 100}%`,
                  backgroundColor: index === 0 ? "var(--color-signal)" : "var(--color-accent)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Concentration({ insights }: { insights: TopologyPulseInsights }): JSX.Element {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">Concentration</p>
      <div className="mt-3 space-y-3">
        {[
          {
            label: insights.concentration.topPathLabel,
            value: insights.concentration.topPathShare,
            helper: "Top path share",
          },
          {
            label: insights.concentration.topSystemLabel,
            value: insights.concentration.topSystemShare,
            helper: "Top system share",
          },
        ].map((item) => (
          <div key={item.helper}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-[var(--color-text-primary)]" title={item.label}>
                  {item.label}
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)]">{item.helper}</p>
              </div>
              <span className="text-sm font-semibold text-[var(--color-text-primary)]">{percent(item.value)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RankedPathLoad({
  insights,
  metricMode,
  onHighlightEdges,
  onPinEdge,
}: {
  insights: TopologyPulseInsights;
  metricMode: TopologyMetricMode;
  onHighlightEdges: (_edgeIds: string[]) => void;
  onPinEdge: (_edgeId: string) => void;
}): JSX.Element {
  const topPaths = insights.paths.slice(0, 5);
  const maximum = Math.max(...topPaths.map((path) => path.value), 1);
  const sparkline = useMemo(() => {
    if (topPaths.length === 0) {
      return "";
    }
    return topPaths
      .map((path, index) => {
        const x = topPaths.length === 1 ? 100 : (index / (topPaths.length - 1)) * 200;
        const y = 36 - (path.value / maximum) * 30;
        return `${x},${y}`;
      })
      .join(" ");
  }, [maximum, topPaths]);

  return (
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">Ranked path load</p>
          <p className="text-[10px] text-[var(--color-text-muted)]">{metricLabel(metricMode)}</p>
        </div>
        <div className="flex gap-3 text-right text-[10px] text-[var(--color-text-muted)]">
          <span>P50 <b className="text-[var(--color-text-primary)]">{metricValue(insights.pathStats.p50, metricMode)}</b></span>
          <span>P95 <b className="text-[var(--color-text-primary)]">{metricValue(insights.pathStats.p95, metricMode)}</b></span>
          <span>Max <b className="text-[var(--color-text-primary)]">{metricValue(insights.pathStats.max, metricMode)}</b></span>
        </div>
      </div>
      <svg className="mt-1 h-10 w-full" viewBox="0 0 200 42" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" y1="36" x2="200" y2="36" stroke="var(--color-border)" strokeWidth="1" />
        <polyline
          points={sparkline}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="mt-1 flex gap-1.5 overflow-hidden">
        {topPaths.map((path) => (
          <button
            key={path.edgeId}
            type="button"
            className="min-w-0 flex-1 border-t-2 border-[var(--color-accent-border)] pt-1 text-left hover:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
            onMouseEnter={() => onHighlightEdges([path.edgeId])}
            onMouseLeave={() => onHighlightEdges([])}
            onFocus={() => onHighlightEdges([path.edgeId])}
            onBlur={() => onHighlightEdges([])}
            onClick={() => onPinEdge(path.edgeId)}
            title={`${path.label}: ${metricValue(path.value, metricMode)}; payload per execution ${formatKilobytes(path.payloadPerExecutionKb)}`}
          >
            <span className="block truncate text-[10px] font-medium text-[var(--color-text-primary)]">{path.label}</span>
            <span className="block text-[10px] text-[var(--color-text-muted)]">{metricValue(path.value, metricMode)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function TopologyPulse({
  insights,
  metricMode,
  expanded,
  selectedIntegrationId,
  onExpandedChange,
  onIntegrationChange,
  onHighlightEdges,
  onPinEdge,
}: TopologyPulseProps): JSX.Element {
  const selectedEdge = insights.edges.length === 1 ? insights.edges[0] : null;
  const reviewCount = insights.qa.review + insights.qa.pending;
  const exactPayload = insights.totalPayloadPerExecutionKb === null
    ? undefined
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(insights.totalPayloadPerExecutionKb);

  return (
    <section
      data-testid="topology-pulse"
      className="pointer-events-auto overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/90 shadow-[0_14px_35px_rgba(15,23,42,0.16)] backdrop-blur-xl"
      aria-label="Topology Pulse insights"
    >
      <div className="flex min-h-[4.5rem] items-center gap-4 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-accent-soft)] text-[var(--color-accent)]">
            <Activity size={17} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-semibold text-[var(--color-text-primary)]">Topology Pulse</h2>
              <span className="rounded-sm bg-[var(--color-status-active-bg)] px-1.5 py-0.5 text-[9px] font-semibold uppercase text-[var(--color-status-active-text)]">
                Current
              </span>
            </div>
            <p className="max-w-[16rem] truncate text-[10px] text-[var(--color-text-muted)]" title={insights.scopeLabel}>
              {insights.scopeLabel}
            </p>
          </div>
        </div>

        <div className="hidden min-w-0 flex-1 grid-cols-4 gap-3 lg:grid">
          <Metric
            label="Integrations"
            value={formatCompactNumber(insights.integrationCount)}
            detail={`${insights.systemCount} systems`}
          />
          <Metric
            label="Payload / execution"
            value={formatKilobytes(insights.totalPayloadPerExecutionKb)}
            detail={`${insights.payloadExecutionCoverage}/${insights.integrationCount} measured`}
            title={exactPayload ? `${exactPayload} KB summed across the current scope` : "No measured payload per execution"}
          />
          <Metric
            label="Payload / hour"
            value={formatKilobytes(insights.totalPayloadPerHourKb)}
            detail={`${insights.payloadHourCoverage}/${insights.integrationCount} measured`}
          />
          <Metric
            label="Attention"
            value={String(reviewCount)}
            detail={`${insights.qa.ok} QA OK`}
          />
        </div>

        {selectedEdge && selectedEdge.integrations.length > 1 ? (
          <label className="hidden min-w-[13rem] xl:block">
            <span className="sr-only">Topology Pulse integration scope</span>
            <select
              aria-label="Topology Pulse integration scope"
              className="h-9 w-full rounded-md border border-[var(--color-border)] px-2 text-xs"
              value={selectedIntegrationId}
              onChange={(event) => onIntegrationChange(event.target.value)}
            >
              <option value="">All integrations on path</option>
              {selectedEdge.integrations.map((integration) => (
                <option key={integration.id} value={integration.id}>{integration.name}</option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            disabled
            className="flex h-8 items-center gap-1.5 rounded-md px-2 text-[10px] text-[var(--color-text-muted)] opacity-65"
            title="Historical topology snapshots are not available yet."
          >
            <Clock3 size={13} aria-hidden="true" />
            History
          </button>
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
            onClick={() => onExpandedChange(!expanded)}
            aria-label={expanded ? "Collapse Topology Pulse" : "Expand Topology Pulse"}
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="grid grid-cols-2 border-t border-[var(--color-border)] px-4 py-3 xl:grid-cols-[minmax(0,1.65fr)_repeat(3,minmax(0,0.8fr))]">
          <div className="col-span-2 min-w-0 pb-3 xl:col-span-1 xl:pb-0 xl:pr-4">
            <RankedPathLoad
              insights={insights}
              metricMode={metricMode}
              onHighlightEdges={onHighlightEdges}
              onPinEdge={onPinEdge}
            />
          </div>
          <div className="border-t border-[var(--color-border)] py-3 pr-4 xl:border-l xl:border-t-0 xl:px-4 xl:py-0">
            <QaPulse insights={insights} />
          </div>
          <div className="border-l border-t border-[var(--color-border)] py-3 pl-4 xl:border-t-0 xl:px-4 xl:py-0">
            <FlowBalance insights={insights} />
          </div>
          <div className="col-span-2 border-t border-[var(--color-border)] pt-3 xl:col-span-1 xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
            <Concentration insights={insights} />
          </div>
        </div>
      ) : null}
    </section>
  );
}
