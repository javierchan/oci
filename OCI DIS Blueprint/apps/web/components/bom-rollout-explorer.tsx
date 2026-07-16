"use client";

/* Coordinated rollout, cost-driver, and product evidence explorer for governed BOM snapshots. */

import {
  CalendarRange,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  Layers3,
  Pencil,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  buildBomChartData,
  buildRolloutSignals,
  linePeriodMonthlyQuantities,
  phaseMonthlyQuantities,
  serviceProductLabel,
} from "@/lib/bom-ramp";
import type {
  BomLineItem,
  BomSnapshot,
  DeploymentRampPhaseInput,
  DeploymentScenario,
  ScenarioMetricOption,
} from "@/lib/types";

type RolloutPhase = {
  environment: string;
  phase: DeploymentRampPhaseInput;
};

type RolloutProduct = {
  serviceId: string;
  label: string;
  contractAmount: number;
  sharePct: number;
  firstPeriod: number | null;
  lastPeriod: number | null;
  environments: string[];
  lines: BomLineItem[];
  phases: RolloutPhase[];
};

const ENVIRONMENT_COLORS = ["#0A84FF", "#30D158", "#BF5AF2", "#64D2FF", "#FF9F0A"];

function currency(value: number, code: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNumber(value: number): string {
  const magnitude = Math.abs(value);
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: magnitude > 0 && magnitude < 1 ? 6 : magnitude < 10 ? 3 : 0,
  }).format(value);
}

function commercialVariant(line: BomLineItem): string {
  return typeof line.provenance.commercial_variant === "string"
    ? line.provenance.commercial_variant
    : "Governed default";
}

function lineActiveRange(line: BomLineItem): { first: number; last: number } | null {
  const active = line.periods.filter((period) => period.quantity > 0 || period.amount > 0);
  if (active.length === 0) return null;
  return {
    first: Math.min(...active.map((period) => period.period_index)),
    last: Math.max(...active.map((period) => period.period_index)),
  };
}

function buildProducts(snapshot: BomSnapshot, scenario: DeploymentScenario | null): RolloutProduct[] {
  const serviceIds = new Set(snapshot.line_items.map((line) => line.service_id));
  for (const environment of scenario?.environments ?? []) {
    for (const phase of environment.phases) {
      if (phase.service_id) serviceIds.add(phase.service_id);
    }
  }

  return [...serviceIds].map((serviceId) => {
    const lines = snapshot.line_items.filter((line) => line.service_id === serviceId);
    const phases = (scenario?.environments ?? []).flatMap((environment) => environment.phases
      .filter((phase) => phase.service_id === serviceId)
      .map((phase) => ({ environment: environment.name, phase })));
    const ranges = [
      ...lines.flatMap((line) => {
        const range = lineActiveRange(line);
        return range ? [range] : [];
      }),
      ...phases.map(({ phase }) => ({ first: phase.start_month, last: phase.end_month })),
    ];
    const contractAmount = lines.reduce((total, line) => total + line.contract_amount, 0);
    return {
      serviceId,
      label: serviceProductLabel(serviceId),
      contractAmount,
      sharePct: snapshot.contract_total > 0 ? (contractAmount / snapshot.contract_total) * 100 : 0,
      firstPeriod: ranges.length > 0 ? Math.min(...ranges.map((range) => range.first)) : null,
      lastPeriod: ranges.length > 0 ? Math.max(...ranges.map((range) => range.last)) : null,
      environments: [...new Set([
        ...lines.map((line) => line.environment),
        ...phases.map((phase) => phase.environment),
      ])],
      lines,
      phases,
    };
  }).sort((left, right) => right.contractAmount - left.contractAmount || left.label.localeCompare(right.label));
}

function quantityLabel(phase: DeploymentRampPhaseInput): string {
  if (phase.interpolation === "monthly") return `Monthly steps · ${phase.quantity_unit ?? "units"}`;
  const start = formatNumber(phase.start_quantity ?? 0);
  const end = formatNumber(phase.end_quantity ?? phase.start_quantity ?? 0);
  return `${phase.interpolation === "linear" ? `${start} → ${end}` : start} ${phase.quantity_unit ?? "units"}`;
}

function lineQuantityLabel(line: BomLineItem): string {
  const active = line.periods.filter((period) => period.quantity > 0 || period.amount > 0);
  if (active.length === 0) {
    return line.status === "non_billable" ? "Included / no metered charge" : `0 ${line.unit}`;
  }
  const quantities = [...new Set(active.map((period) => period.quantity))];
  if (quantities.length === 1) return `${formatNumber(quantities[0])} ${line.unit} / month`;
  return `Monthly quantities · ${line.unit}`;
}

function productContractMonths(product: RolloutProduct, scenario: DeploymentScenario | null): number {
  const snapshotMonths = Math.max(
    0,
    ...product.lines.flatMap((line) => line.periods.map((period) => period.period_index)),
  );
  return snapshotMonths || scenario?.contract_months || 12;
}

function MonthAxis({ months }: { months: number }): JSX.Element {
  return (
    <div
      className="grid h-6 items-center border-b border-[var(--color-border)] text-center font-mono text-[10px] text-[var(--color-text-muted)]"
      style={{ gridTemplateColumns: `repeat(${months}, minmax(2.5rem, 1fr))` }}
      aria-hidden="true"
    >
      {Array.from({ length: months }, (_, index) => (
        <span key={index} className="border-l border-[var(--color-border)] first:border-l-0">
          M{index + 1}
        </span>
      ))}
    </div>
  );
}

function RampShape({
  phase,
  months,
  included,
}: {
  phase: DeploymentRampPhaseInput;
  months: number;
  included: boolean;
}): JSX.Element {
  const left = ((phase.start_month - 1) / months) * 100;
  const width = ((phase.end_month - phase.start_month + 1) / months) * 100;
  const monthly = phaseMonthlyQuantities(phase, months);
  const maximum = Math.max(...monthly, 0);

  return (
    <div className="relative h-10 overflow-hidden border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
      <div
        className="pointer-events-none absolute inset-0 grid"
        style={{ gridTemplateColumns: `repeat(${months}, minmax(2.5rem, 1fr))` }}
        aria-hidden="true"
      >
        {Array.from({ length: months }, (_, index) => <span key={index} className="border-l border-[var(--color-border)] first:border-l-0" />)}
      </div>
      {included && maximum === 0 ? (
        <span className="absolute left-3 top-2 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-text-secondary)]">
          Included / no metered charge
        </span>
      ) : phase.interpolation === "monthly" ? (
        <div className="absolute inset-0 grid items-end" style={{ gridTemplateColumns: `repeat(${months}, minmax(2.5rem, 1fr))` }}>
          {monthly.map((quantity, index) => (
            <span
              key={index}
              className="mx-1 block min-h-0.5 rounded-t-sm bg-[#0A84FF]"
              style={{ height: `${maximum > 0 ? Math.max((quantity / maximum) * 30, quantity > 0 ? 4 : 1) : 1}px`, opacity: quantity > 0 ? 0.9 : 0.16 }}
              title={`M${index + 1}: ${formatNumber(quantity)} ${phase.quantity_unit ?? "units"}`}
            />
          ))}
        </div>
      ) : phase.interpolation === "linear" ? (
        <svg
          className="absolute inset-y-1"
          style={{ left: `${left}%`, width: `${width}%` }}
          viewBox="0 0 100 32"
          preserveAspectRatio="none"
          role="img"
          aria-label={`Linear ramp from month ${phase.start_month} to ${phase.end_month}`}
        >
          <line x1="2" y1="26" x2="98" y2="6" stroke="#0A84FF" strokeWidth="5" strokeLinecap="round" />
        </svg>
      ) : (
        <span
          className="absolute top-3 h-3 rounded-sm bg-[#0A84FF]"
          style={{ left: `${left}%`, width: `${width}%` }}
          aria-label={`Constant consumption from month ${phase.start_month} to ${phase.end_month}`}
        />
      )}
    </div>
  );
}

function LinePeriodShape({
  line,
  months,
  currencyCode,
}: {
  line: BomLineItem;
  months: number;
  currencyCode: string;
}): JSX.Element {
  const quantities = linePeriodMonthlyQuantities(line.periods, months);
  const amounts = Array.from({ length: months }, (_, index) => (
    line.periods.find((period) => period.period_index === index + 1)?.amount ?? 0
  ));
  const maximumQuantity = Math.max(...quantities, 0);
  const maximumAmount = Math.max(...amounts, 0);
  const included = line.status === "non_billable" && maximumQuantity === 0 && maximumAmount === 0;

  return (
    <div
      className="relative h-12 overflow-hidden border-b border-[var(--color-border)] bg-[var(--color-surface-2)]"
      data-rollout-monthly-evidence={line.id}
      aria-label={`${line.metric_name} monthly consumption`}
    >
      <div
        className="absolute inset-0 grid items-end"
        style={{ gridTemplateColumns: `repeat(${months}, minmax(2.5rem, 1fr))` }}
      >
        {quantities.map((quantity, index) => {
          const amount = amounts[index];
          const value = maximumQuantity > 0 ? quantity : amount;
          const maximum = maximumQuantity > 0 ? maximumQuantity : maximumAmount;
          const active = quantity > 0 || amount > 0;
          return (
            <span
              key={index}
              className="relative h-full border-l border-[var(--color-border)] first:border-l-0"
              title={`M${index + 1}: ${formatNumber(quantity)} ${line.unit} · ${currency(amount, currencyCode)}`}
            >
              <span
                className="absolute inset-x-1 bottom-1 block min-h-0.5 rounded-t-sm bg-[#0A84FF]"
                style={{
                  height: `${maximum > 0 ? Math.max((value / maximum) * 36, active ? 4 : 1) : 1}px`,
                  opacity: active ? 0.9 : 0.12,
                }}
              />
            </span>
          );
        })}
      </div>
      {included ? (
        <span className="absolute left-3 top-3 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-text-secondary)]">
          Included / no metered charge
        </span>
      ) : null}
    </div>
  );
}

function ProductTimeline({
  product,
  scenario,
  currencyCode,
  metricOptions,
  openEnvironment,
  onToggleEnvironment,
}: {
  product: RolloutProduct;
  scenario: DeploymentScenario | null;
  currencyCode: string;
  metricOptions: ScenarioMetricOption[];
  openEnvironment: string | null;
  onToggleEnvironment: (_environment: string) => void;
}): JSX.Element {
  const months = productContractMonths(product, scenario);
  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)]/40 px-4 py-3 sm:px-5">
      <div className="space-y-2">
        {product.environments.map((environment) => {
          const phases = product.phases.filter((item) => item.environment === environment);
          const lines = product.lines.filter((line) => line.environment === environment);
          const environmentAmount = lines.reduce((total, line) => total + line.contract_amount, 0);
          const expanded = openEnvironment === environment;
          return (
            <div key={environment} className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
              <button
                type="button"
                data-rollout-environment={environment}
                className="flex min-h-12 w-full items-center justify-between gap-3 px-3 py-2 text-left"
                aria-expanded={expanded}
                aria-label={`Toggle ${environment} details`}
                onClick={() => onToggleEnvironment(environment)}
              >
                <span>
                  <span className="block text-sm font-semibold text-[var(--color-text-primary)]">{environment}</span>
                  <span className="block text-xs text-[var(--color-text-muted)]">{phases.length || lines.length} planned metric{(phases.length || lines.length) === 1 ? "" : "s"}</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-mono text-xs text-[var(--color-text-secondary)]">{currency(environmentAmount, scenario?.currency ?? "USD")}</span>
                  <ChevronDown className={`h-4 w-4 text-[var(--color-text-muted)] transition-transform ${expanded ? "rotate-180" : ""}`} />
                </span>
              </button>
              {expanded ? (
                <div className="overflow-x-auto border-t border-[var(--color-border)]">
                  <div style={{ minWidth: `${Math.max(680, months * 44)}px` }}>
                    <MonthAxis months={months} />
                    {lines.some((line) => line.periods.length > 0) ? lines.map((line) => (
                      <div key={line.id} className="grid grid-cols-[13rem_minmax(0,1fr)] border-b border-[var(--color-border)] last:border-b-0">
                        <div className="px-3 py-2">
                          <p className="truncate text-xs font-semibold text-[var(--color-text-primary)]" title={line.metric_name}>{line.metric_name}</p>
                          <p className="mt-0.5 truncate text-[11px] text-[var(--color-text-muted)]" title={commercialVariant(line)}>{commercialVariant(line)}</p>
                          <p className="mt-0.5 truncate text-[11px] text-[var(--color-text-secondary)]" title={lineQuantityLabel(line)}>{lineQuantityLabel(line)}</p>
                        </div>
                        {line.periods.length > 0 ? (
                          <LinePeriodShape line={line} months={months} currencyCode={currencyCode} />
                        ) : (
                          <div className="flex items-center border-b border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 text-xs text-[var(--color-text-muted)]">
                            This historical line has no monthly period evidence.
                          </div>
                        )}
                      </div>
                    )) : phases.length > 0 ? phases.map(({ phase }, phaseIndex) => {
                      const option = metricOptions.find((item) => item.service_id === product.serviceId && item.metric_key === phase.metric_key);
                      const variant = option?.variants.find((item) => item.sku_mapping_id === phase.sku_mapping_id);
                      const matchedLine = lines.find((line) => (
                        (typeof line.provenance.mapping_id === "string" && line.provenance.mapping_id === phase.sku_mapping_id)
                        || line.metric_name === option?.metric_label
                      ));
                      const metricLabel = matchedLine?.metric_name ?? option?.metric_label ?? phase.metric_key ?? "Base schedule";
                      const included = matchedLine?.status === "non_billable";
                      return (
                        <div key={`${phase.metric_key}-${phaseIndex}`} className="grid grid-cols-[13rem_minmax(0,1fr)] border-b border-[var(--color-border)] last:border-b-0">
                          <div className="px-3 py-2">
                            <p className="truncate text-xs font-semibold text-[var(--color-text-primary)]" title={metricLabel}>{metricLabel}</p>
                            <p className="mt-0.5 truncate text-[11px] text-[var(--color-text-muted)]" title={variant?.label ?? (matchedLine ? commercialVariant(matchedLine) : "Governed default")}>{variant?.label ?? (matchedLine ? commercialVariant(matchedLine) : "Governed default")}</p>
                            <p className="mt-0.5 truncate text-[11px] text-[var(--color-text-secondary)]">{quantityLabel(phase)}</p>
                          </div>
                          <RampShape phase={phase} months={months} included={included} />
                        </div>
                      );
                    }) : (
                      <div className="px-3 py-4 text-xs text-[var(--color-text-muted)]">This snapshot has no monthly period evidence or editable phase definition.</div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProductInspector({
  product,
  snapshot,
  onEditScenario,
}: {
  product: RolloutProduct | null;
  snapshot: BomSnapshot;
  onEditScenario: () => void;
}): JSX.Element {
  if (!product) {
    return <div className="p-5 text-sm text-[var(--color-text-secondary)]">Select a product to inspect its governed cost evidence.</div>;
  }
  return (
    <div className="p-5">
      <p className="app-label">Selected Product</p>
      <h3 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">{product.label}</h3>
      <p className="mt-1 text-sm leading-5 text-[var(--color-text-secondary)]">
        {currency(product.contractAmount, snapshot.currency)} across {product.environments.length} environment{product.environments.length === 1 ? "" : "s"}.
      </p>

      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 border-y border-[var(--color-border)] py-4">
        <div><dt className="app-label">Cost share</dt><dd className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{product.sharePct.toFixed(1)}%</dd></div>
        <div><dt className="app-label">Active</dt><dd className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{product.firstPeriod ? `M${product.firstPeriod}–M${product.lastPeriod}` : "Included"}</dd></div>
        <div><dt className="app-label">Metrics</dt><dd className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{product.lines.length}</dd></div>
        <div><dt className="app-label">Environments</dt><dd className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{product.environments.length}</dd></div>
      </dl>

      <p className="app-label mt-5">Commercial evidence</p>
      <div className="mt-2 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
        {product.lines.map((line) => {
          const activePeriods = line.periods.filter((period) => period.quantity > 0 || period.amount > 0);
          const steady = activePeriods.at(-1);
          return (
            <div key={line.id} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{line.environment} · {line.metric_name}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{commercialVariant(line)}</p></div>
                <span className="shrink-0 font-mono text-xs text-[var(--color-text-secondary)]">{line.part_number ?? "Included"}</span>
              </div>
              <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-[var(--color-text-secondary)]">
                <span>{steady ? `${formatNumber(steady.quantity)} ${line.unit}` : "No metered quantity"}</span>
                <span>{currency(line.contract_amount, snapshot.currency)}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-xs leading-5 text-[var(--color-text-secondary)]">
        Price snapshot <span className="font-mono text-[var(--color-text-primary)]">{snapshot.price_catalog_snapshot_id.slice(0, 8)}</span> · mapping <span className="font-mono text-[var(--color-text-primary)]">{snapshot.mapping_version}</span>
      </div>
      <button type="button" className="app-button-secondary mt-4 w-full gap-2" onClick={onEditScenario}>
        <Pencil className="h-4 w-4" />Edit scenario
      </button>
    </div>
  );
}

export function BomRolloutExplorer({
  snapshot,
  scenario,
  metricOptions,
  onEditScenario,
}: {
  snapshot: BomSnapshot;
  scenario: DeploymentScenario | null;
  metricOptions: ScenarioMetricOption[];
  onEditScenario: () => void;
}): JSX.Element {
  const [compositionMode, setCompositionMode] = useState<"environment" | "service">("environment");
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [expandedServiceId, setExpandedServiceId] = useState<string | null>(null);
  const [openEnvironment, setOpenEnvironment] = useState<string | null>(null);
  const [mobilePanel, setMobilePanel] = useState<"timeline" | "inspector">("timeline");
  const chart = useMemo(() => buildBomChartData(snapshot, compositionMode), [compositionMode, snapshot]);
  const products = useMemo(() => buildProducts(snapshot, scenario), [scenario, snapshot]);
  const signals = useMemo(() => buildRolloutSignals(snapshot, scenario?.environments), [scenario?.environments, snapshot]);
  const selectedProduct = products.find((product) => product.serviceId === selectedServiceId) ?? products[0] ?? null;

  useEffect(() => {
    if (!products.some((product) => product.serviceId === selectedServiceId)) {
      setSelectedServiceId(products[0]?.serviceId ?? null);
      setExpandedServiceId(products[0]?.serviceId ?? null);
      setOpenEnvironment(products[0]?.environments[0] ?? null);
    }
  }, [products, selectedServiceId]);

  function selectProduct(product: RolloutProduct): void {
    setSelectedServiceId(product.serviceId);
    setExpandedServiceId(product.serviceId);
    setOpenEnvironment(product.environments[0] ?? null);
    setCompositionMode("service");
    setMobilePanel("inspector");
  }

  const maximumDriver = products[0]?.contractAmount ?? 0;
  const signalRows = [
    { icon: Layers3, label: "First environment", value: signals.firstEnvironment ? `${signals.firstEnvironment.environment} · M${signals.firstEnvironment.period}` : "Not active" },
    { icon: CalendarRange, label: "Production starts", value: signals.productionStart ? `${signals.productionStart.environment} · M${signals.productionStart.period}` : "Not scheduled" },
    { icon: Clock3, label: "Stabilizes", value: signals.stabilizationPeriod ? `Month ${signals.stabilizationPeriod}` : "No plateau" },
    { icon: CircleDollarSign, label: "Rollout timing effect", value: `-${currency(signals.timingEffect, snapshot.currency)}` },
  ];

  return (
    <section className="app-card overflow-hidden" aria-labelledby="rollout-explorer-title">
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="app-label">Rollout Explorer</p>
            <h2 id="rollout-explorer-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">When capacity starts, what drives cost, and where it lands</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">Read the contract from activation to steady state. Select a product in the ranking, chart, or timeline to inspect its exact environments, quantities, SKU, and price evidence.</p>
          </div>
          <div className="inline-flex rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1" role="group" aria-label="Group monthly consumption">
            <button type="button" className={`rounded-md px-3 py-2 text-sm font-semibold ${compositionMode === "environment" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-secondary)]"}`} aria-pressed={compositionMode === "environment"} onClick={() => setCompositionMode("environment")}>Environment</button>
            <button type="button" className={`rounded-md px-3 py-2 text-sm font-semibold ${compositionMode === "service" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-secondary)]"}`} aria-pressed={compositionMode === "service"} onClick={() => setCompositionMode("service")}>Product</button>
          </div>
        </div>

        <div className="mt-5 grid border-y border-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-4">
          {signalRows.map((signal) => <div key={signal.label} className="flex min-h-24 gap-3 border-b border-[var(--color-border)] px-3 py-4 last:border-b-0 sm:[&:nth-child(odd)]:border-r sm:[&:nth-child(n+3)]:border-b-0 xl:border-b-0 xl:border-r xl:last:border-r-0"><signal.icon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-accent)]" /><div><p className="app-label">{signal.label}</p><p className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">{signal.value}</p></div></div>)}
        </div>

        <div className="mt-5 h-[320px] w-full" aria-label="Monthly cost ramp chart">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chart.rows} margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis yAxisId="monthly" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} tickFormatter={(value) => new Intl.NumberFormat("en-US", { notation: "compact" }).format(Number(value))} />
              <YAxis yAxisId="cumulative" orientation="right" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} tickFormatter={(value) => new Intl.NumberFormat("en-US", { notation: "compact" }).format(Number(value))} />
              <Tooltip contentStyle={{ background: "var(--color-surface)", borderColor: "var(--color-border)", borderRadius: 8, color: "var(--color-text-primary)" }} formatter={(value) => currency(Number(value), snapshot.currency)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {chart.keys.map((key, index) => {
                const serviceSelected = compositionMode === "service" && selectedProduct?.serviceId === key;
                const muted = compositionMode === "service" && selectedProduct !== null && !serviceSelected;
                const color = compositionMode === "environment" ? ENVIRONMENT_COLORS[index % ENVIRONMENT_COLORS.length] : serviceSelected ? "#0A84FF" : "#8E8E93";
                return <Area key={key} yAxisId="monthly" type="monotone" dataKey={key} name={compositionMode === "service" ? serviceProductLabel(key) : key} stackId="monthly" stroke={color} strokeWidth={serviceSelected ? 2.5 : 1} fill={color} fillOpacity={muted ? 0.16 : 0.72} cursor={compositionMode === "service" ? "pointer" : "default"} onClick={() => { const product = products.find((item) => item.serviceId === key); if (product) selectProduct(product); }} />;
              })}
              <Line yAxisId="cumulative" type="monotone" dataKey="cumulative" name="Cumulative" stroke="var(--color-text-primary)" strokeWidth={2.5} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_23rem]">
          <div className={`${mobilePanel === "timeline" ? "block" : "hidden"} min-w-0 border-[var(--color-border)] lg:block lg:border-r`}>
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[var(--color-border)] px-5 py-4">
              <div><p className="app-label">Products and activation</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Expand a product, then an environment, to inspect its governed consumption shape.</p></div>
              <span className="text-xs text-[var(--color-text-muted)]">{products.length} products</span>
            </div>
            <div className="divide-y divide-[var(--color-border)]">
              {products.map((product) => {
                const expanded = expandedServiceId === product.serviceId;
                const selected = selectedProduct?.serviceId === product.serviceId;
                return (
                  <div key={product.serviceId} className={selected ? "bg-[#0A84FF]/[0.06]" : undefined}>
                    <button
                      type="button"
                      data-rollout-product={product.serviceId}
                      className="grid min-h-16 w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-3 text-left"
                      aria-expanded={expanded}
                      aria-label={`Toggle ${product.label} details`}
                      onClick={() => {
                        setSelectedServiceId(product.serviceId);
                        setExpandedServiceId(expanded ? null : product.serviceId);
                        setOpenEnvironment(product.environments[0] ?? null);
                      }}
                    >
                      <span className="min-w-0"><span className="block truncate text-sm font-semibold text-[var(--color-text-primary)]">{product.label}</span><span className="mt-1 block text-xs text-[var(--color-text-muted)]">{product.environments.join(" · ")} · {product.firstPeriod ? `M${product.firstPeriod}–M${product.lastPeriod}` : "included"}</span></span>
                      <span className="flex items-center gap-4"><span className="text-right"><span className="block font-mono text-sm font-semibold text-[var(--color-text-primary)]">{currency(product.contractAmount, snapshot.currency)}</span><span className="block text-xs text-[var(--color-text-muted)]">{product.sharePct.toFixed(1)}%</span></span><ChevronDown className={`h-4 w-4 text-[var(--color-text-muted)] transition-transform ${expanded ? "rotate-180" : ""}`} /></span>
                    </button>
                    {expanded ? <ProductTimeline product={product} scenario={scenario} currencyCode={snapshot.currency} metricOptions={metricOptions} openEnvironment={openEnvironment} onToggleEnvironment={(environment) => setOpenEnvironment((current) => current === environment ? null : environment)} /> : null}
                  </div>
                );
              })}
            </div>
          </div>

          <aside className={`${mobilePanel === "inspector" ? "block" : "hidden"} min-w-0 lg:block`} aria-label="Selected product inspector">
            <div className="border-b border-[var(--color-border)] px-5 py-4">
              <p className="app-label">Top contract drivers</p>
              <div className="mt-3 space-y-2">
                {products.slice(0, 6).map((product, index) => {
                  const selected = selectedProduct?.serviceId === product.serviceId;
                  return <button key={product.serviceId} type="button" className={`block w-full rounded-md px-2 py-2 text-left ${selected ? "bg-[#0A84FF]/10" : "hover:bg-[var(--color-surface-2)]"}`} aria-label={`Inspect ${product.label}`} aria-pressed={selected} onClick={() => selectProduct(product)}><span className="flex justify-between gap-3 text-xs"><span className="truncate font-semibold text-[var(--color-text-primary)]">{product.label}</span><span className="shrink-0 font-mono text-[var(--color-text-secondary)]">{currency(product.contractAmount, snapshot.currency)}</span></span><span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-[var(--color-surface-2)]"><span className="block h-full rounded-full bg-[#0A84FF]" style={{ width: `${maximumDriver > 0 ? (product.contractAmount / maximumDriver) * 100 : 0}%`, opacity: 1 - (index * 0.1) }} /></span></button>;
                })}
              </div>
            </div>
            <ProductInspector product={selectedProduct} snapshot={snapshot} onEditScenario={onEditScenario} />
          </aside>
        </div>

        <div className="grid grid-cols-2 border-t border-[var(--color-border)] lg:hidden" role="tablist" aria-label="Rollout explorer mobile view">
          <button type="button" role="tab" aria-selected={mobilePanel === "timeline"} className={`min-h-11 text-sm font-semibold ${mobilePanel === "timeline" ? "border-t-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-[var(--color-text-secondary)]"}`} onClick={() => setMobilePanel("timeline")}>Timeline</button>
          <button type="button" role="tab" aria-selected={mobilePanel === "inspector"} className={`min-h-11 text-sm font-semibold ${mobilePanel === "inspector" ? "border-t-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-[var(--color-text-secondary)]"}`} onClick={() => setMobilePanel("inspector")}>Inspector</button>
        </div>
      </div>

      <div className="grid gap-4 border-t border-[var(--color-border)] px-5 py-4 sm:grid-cols-3">
        <div><p className="app-label">Day-one full capacity</p><p className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{currency(snapshot.contract_total + snapshot.ramp_deferred_amount, snapshot.currency)}</p></div>
        <div><p className="app-label">Phased activation effect</p><p className="mt-1 text-lg font-semibold text-[var(--color-accent)]">-{currency(snapshot.ramp_deferred_amount, snapshot.currency)}</p></div>
        <div><p className="app-label">Planned contract</p><p className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{currency(snapshot.contract_total, snapshot.currency)}</p></div>
        <p className="text-xs leading-5 text-[var(--color-text-muted)] sm:col-span-3">Timing effect compares this rollout with full capacity active from month one. It is not a negotiated discount or guaranteed saving.</p>
      </div>
    </section>
  );
}
