"use client";

/* Edits one governed real-unit consumption plan without hiding commercial policy. */

import {
  ChevronDown,
  ChevronRight,
  Clock3,
  LayoutList,
  PackageCheck,
  Plus,
  Search,
  Table2,
  Trash2,
} from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import {
  explicitPlanReadiness,
  explicitQuantityPhase,
  phaseMonthlyQuantities,
  withMonthlyQuantity,
} from "@/lib/bom-ramp";
import type {
  DeploymentEnvironmentInput,
  DeploymentRampPhaseInput,
  ScenarioMetricOption,
  ScenarioSkuVariant,
} from "@/lib/types";

type ConsumptionEditorProps = {
  contractMonths: number;
  environments: DeploymentEnvironmentInput[];
  metricOptions: ScenarioMetricOption[];
  onChange: (_environments: DeploymentEnvironmentInput[]) => void;
};

type IndexedPhase = { phase: DeploymentRampPhaseInput; phaseIndex: number };

const inputClass = "mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm text-[var(--color-text-primary)]";
const PRODUCT_DOTS = [
  "bg-sky-500",
  "bg-violet-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
];

function optionKey(option: Pick<ScenarioMetricOption, "service_id" | "metric_key">): string {
  return `${option.service_id}:${option.metric_key}`;
}

function productDot(serviceId: string): string {
  const score = [...serviceId].reduce((total, character) => total + character.charCodeAt(0), 0);
  return PRODUCT_DOTS[score % PRODUCT_DOTS.length];
}

function quantityRule(
  option: Pick<ScenarioMetricOption, "quantity_behavior" | "quantity_increment" | "minimum_quantity" | "quote_rounding"> | ScenarioSkuVariant | undefined,
): string {
  if (!option) return "Governed rule unavailable";
  const behavior = option.quantity_behavior.replaceAll("_", " ");
  const increment = option.quantity_increment === 1 ? "whole units" : `${option.quantity_increment} increments`;
  return `${behavior} · ${increment}${option.minimum_quantity > 0 ? ` · minimum ${option.minimum_quantity}` : ""}`;
}

function normalizedQuote(quantity: number, increment: number, minimum: number): number {
  if (quantity <= 0) return 0;
  const normalized = Math.ceil((quantity / increment) - Number.EPSILON) * increment;
  return Math.max(normalized, minimum);
}

function planningEnvelope(quantity: number, increment: number | null | undefined): number | null {
  if (!increment || increment <= 0 || quantity <= 0) return null;
  return Math.ceil((quantity / increment) - Number.EPSILON) * increment;
}

function policyLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function basisLabel(basis: string): string {
  const labels: Record<string, string> = {
    allocated_capacity: "Allocated capacity",
    metered_usage: "Measured usage",
    provisioned_runtime: "Running time",
    utilized_runtime: "Execution time",
  };
  return labels[basis] ?? basis.replaceAll("_", " ");
}

export function BomConsumptionEditor({
  contractMonths,
  environments,
  metricOptions,
  onChange,
}: ConsumptionEditorProps): JSX.Element {
  const [mode, setMode] = useState<"standard" | "monthly">("standard");
  const [productQuery, setProductQuery] = useState("");
  const [selectedProducts, setSelectedProducts] = useState<Record<number, string>>({});
  const [metricToAdd, setMetricToAdd] = useState<Record<number, string>>({});
  const [addMetricOpen, setAddMetricOpen] = useState<Set<number>>(new Set());
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(
    () => new Set(environments.flatMap((environment, index) => {
      const serviceId = environment.phases[0]?.service_id;
      return serviceId ? [`${index}:${serviceId}`] : [];
    })),
  );
  const readiness = useMemo(() => explicitPlanReadiness(environments), [environments]);

  const optionsByService = useMemo(() => {
    const grouped = new Map<string, ScenarioMetricOption[]>();
    for (const option of metricOptions) {
      grouped.set(option.service_id, [...(grouped.get(option.service_id) ?? []), option]);
    }
    return grouped;
  }, [metricOptions]);

  function patchEnvironment(index: number, patch: Partial<DeploymentEnvironmentInput>): void {
    onChange(environments.map((environment, current) => current === index ? { ...environment, ...patch } : environment));
  }

  function patchPhase(environmentIndex: number, phaseIndex: number, next: DeploymentRampPhaseInput): void {
    patchEnvironment(environmentIndex, {
      phases: environments[environmentIndex].phases.map((phase, current) => current === phaseIndex ? next : phase),
    });
  }

  function addEnvironment(): void {
    onChange([...environments, {
      name: `Environment ${environments.length + 1}`,
      active_hours_month: 744,
      demand_share: 1,
      ha_multiplier: 1,
      dr_role: "none",
      phases: [],
    }]);
  }

  function removeEnvironment(index: number): void {
    if (environments.length > 1) onChange(environments.filter((_, current) => current !== index));
  }

  function availableOptions(environmentIndex: number): ScenarioMetricOption[] {
    const existing = new Set(environments[environmentIndex].phases.map((phase) => `${phase.service_id}:${phase.metric_key}`));
    return metricOptions.filter((candidate) => !existing.has(optionKey(candidate)));
  }

  function addMetric(environmentIndex: number): void {
    const available = availableOptions(environmentIndex);
    const selectedKey = metricToAdd[environmentIndex];
    const option = available.find((candidate) => optionKey(candidate) === selectedKey);
    if (!option) return;
    patchEnvironment(environmentIndex, {
      phases: [...environments[environmentIndex].phases, explicitQuantityPhase(option, contractMonths)],
    });
    setExpandedProducts((current) => new Set(current).add(`${environmentIndex}:${option.service_id}`));
    setSelectedProducts((current) => ({ ...current, [environmentIndex]: option.service_id }));
    setMetricToAdd((current) => ({ ...current, [environmentIndex]: "" }));
    setAddMetricOpen((current) => {
      const next = new Set(current);
      next.delete(environmentIndex);
      return next;
    });
  }

  function removeMetric(environmentIndex: number, phaseIndex: number): void {
    const removedServiceId = environments[environmentIndex].phases[phaseIndex]?.service_id;
    const phases = environments[environmentIndex].phases.filter((_, current) => current !== phaseIndex);
    patchEnvironment(environmentIndex, {
      phases,
    });
    if (removedServiceId && !phases.some((phase) => phase.service_id === removedServiceId)) {
      setSelectedProducts((current) => ({ ...current, [environmentIndex]: "" }));
    }
  }

  function replaceMetric(environmentIndex: number, phaseIndex: number, option: ScenarioMetricOption | undefined): void {
    if (!option) return;
    const current = environments[environmentIndex].phases[phaseIndex];
    patchPhase(environmentIndex, phaseIndex, {
      ...explicitQuantityPhase(option, contractMonths),
      start_month: current.start_month,
      end_month: current.end_month,
    });
  }

  function replaceVariant(
    environmentIndex: number,
    phaseIndex: number,
    option: ScenarioMetricOption,
    skuMappingId: string,
  ): void {
    const variant = option.variants.find((candidate) => candidate.sku_mapping_id === skuMappingId);
    if (!variant) return;
    const phase = environments[environmentIndex].phases[phaseIndex];
    patchPhase(environmentIndex, phaseIndex, {
      ...phase,
      sku_mapping_id: variant.sku_mapping_id,
      quantity_unit: variant.quantity_unit,
    });
  }

  function setSchedule(
    environmentIndex: number,
    phaseIndex: number,
    interpolation: DeploymentRampPhaseInput["interpolation"],
  ): void {
    const phase = environments[environmentIndex].phases[phaseIndex];
    if (interpolation === "monthly") {
      const quantities = phaseMonthlyQuantities(phase, contractMonths);
      patchPhase(environmentIndex, phaseIndex, {
        ...phase,
        start_month: 1,
        end_month: contractMonths,
        interpolation,
        start_quantity: null,
        end_quantity: null,
        monthly_quantities: quantities.map((quantity, index) => ({ period_index: index + 1, quantity })),
      });
      setMode("monthly");
      return;
    }
    const quantities = phaseMonthlyQuantities(phase, contractMonths);
    const first = quantities[phase.start_month - 1] ?? 0;
    const last = quantities[phase.end_month - 1] ?? first;
    patchPhase(environmentIndex, phaseIndex, {
      ...phase,
      interpolation,
      start_quantity: first,
      end_quantity: interpolation === "step" ? first : last,
      monthly_quantities: [],
    });
  }

  function applyPreset(environmentIndex: number, phaseIndex: number, quantity: number): void {
    const phase = environments[environmentIndex].phases[phaseIndex];
    patchPhase(environmentIndex, phaseIndex, {
      ...phase,
      interpolation: "step",
      start_quantity: quantity,
      end_quantity: quantity,
      monthly_quantities: [],
    });
  }

  function toggleProduct(key: string): void {
    setExpandedProducts((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function phaseGroups(
    environment: DeploymentEnvironmentInput,
    selectedServiceId = "",
    queryValue = productQuery,
  ): Array<{ serviceId: string; name: string; phases: IndexedPhase[] }> {
    const groups = new Map<string, IndexedPhase[]>();
    environment.phases.forEach((phase, phaseIndex) => {
      const serviceId = phase.service_id ?? "UNASSIGNED";
      groups.set(serviceId, [...(groups.get(serviceId) ?? []), { phase, phaseIndex }]);
    });
    const query = queryValue.trim().toLowerCase();
    return [...groups.entries()].map(([serviceId, phases]) => ({
      serviceId,
      name: optionsByService.get(serviceId)?.[0]?.product_name ?? serviceId,
      phases,
    })).filter((group) => {
      if (selectedServiceId && group.serviceId !== selectedServiceId) return false;
      if (!query) return true;
      return group.name.toLowerCase().includes(query) || group.phases.some(({ phase }) => {
        const option = metricOptions.find((candidate) => candidate.service_id === phase.service_id && candidate.metric_key === phase.metric_key);
        return option?.metric_label.toLowerCase().includes(query)
          || option?.variants.some((variant) => variant.part_number?.toLowerCase().includes(query));
      });
    }).sort((left, right) => left.name.localeCompare(right.name));
  }

  return (
    <div className="mt-5 border-t border-[var(--color-border)] pt-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="app-label">Environment Consumption</p>
          <h3 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">Plan in Oracle commercial units</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Organize demand by environment and product. Measured consumption, quote rounding, commercial variant, and monthly activation remain traceable as separate decisions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="inline-flex rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1" role="group" aria-label="Consumption editor view">
            <button type="button" className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-semibold ${mode === "standard" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-secondary)]"}`} aria-pressed={mode === "standard"} onClick={() => setMode("standard")}><LayoutList className="h-4 w-4" />Standard</button>
            <button type="button" className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-semibold ${mode === "monthly" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-secondary)]"}`} aria-pressed={mode === "monthly"} onClick={() => setMode("monthly")}><Table2 className="h-4 w-4" />Monthly matrix</button>
          </div>
          <button type="button" className="app-button-secondary gap-2" onClick={addEnvironment}><Plus className="h-4 w-4" />Add environment</button>
        </div>
      </div>

      <div className="mt-4 grid gap-2 border-y border-[var(--color-border)] py-3 text-xs text-[var(--color-text-secondary)] sm:grid-cols-3">
        <p><span className="font-semibold text-[var(--color-text-primary)]">1. Environment</span><br />Define DEV, QA, PROD, or DR and its runtime posture.</p>
        <p><span className="font-semibold text-[var(--color-text-primary)]">2. Product</span><br />Choose the exact SKU, metric, and real commercial-unit quantity.</p>
        <p><span className="font-semibold text-[var(--color-text-primary)]">3. Activation</span><br />Use a constant, linear, or exact month-by-month schedule.</p>
      </div>

      <label className="relative mt-4 block max-w-lg">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
        <span className="sr-only">Find product, metric, or SKU</span>
        <input value={productQuery} onChange={(event) => setProductQuery(event.target.value)} placeholder="Find product, metric, or SKU..." className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pl-9 pr-3 text-sm text-[var(--color-text-primary)]" />
      </label>

      <div className="mt-2 divide-y divide-[var(--color-border)]">
        {environments.map((environment, environmentIndex) => {
          const available = availableOptions(environmentIndex);
          const allGroups = phaseGroups(environment, "", "");
          const selectedProduct = selectedProducts[environmentIndex] ?? "";
          const groups = phaseGroups(environment, selectedProduct);
          const isAddMetricOpen = addMetricOpen.has(environmentIndex);
          return (
            <section key={`environment-${environmentIndex}`} className="py-5" aria-label={`${environment.name || `Environment ${environmentIndex + 1}`} consumption plan`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <label className="block max-w-xl text-xs font-semibold text-[var(--color-text-secondary)]">Environment<input aria-label={`Environment ${environmentIndex + 1} name`} className={inputClass} value={environment.name} onChange={(event) => patchEnvironment(environmentIndex, { name: event.target.value })} /></label>
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">{environment.phases.length} product metric{environment.phases.length === 1 ? "" : "s"} planned</p>
                </div>
                <button type="button" className="app-icon-button" title="Remove environment" disabled={environments.length === 1} onClick={() => removeEnvironment(environmentIndex)}><Trash2 className="h-4 w-4" /></button>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <label className="text-xs font-semibold text-[var(--color-text-secondary)]">Runtime ceiling / month<input type="number" min={0} max={744} className={inputClass} value={environment.active_hours_month} onChange={(event) => patchEnvironment(environmentIndex, { active_hours_month: Number(event.target.value) })} /><span className="mt-1.5 block font-normal leading-5 text-[var(--color-text-muted)]">Used by capacity SKUs that truly run by the hour. Product runtime can be planned separately below.</span></label>
                <label className="text-xs font-semibold text-[var(--color-text-secondary)]">HA multiplier<input type="number" min={1} max={10} step={0.1} className={inputClass} value={environment.ha_multiplier} onChange={(event) => patchEnvironment(environmentIndex, { ha_multiplier: Number(event.target.value) })} /></label>
                <label className="text-xs font-semibold text-[var(--color-text-secondary)]">DR role<select className={inputClass} value={environment.dr_role} onChange={(event) => patchEnvironment(environmentIndex, { dr_role: event.target.value as DeploymentEnvironmentInput["dr_role"] })}><option value="primary">Primary</option><option value="standby">Standby</option><option value="none">None</option></select></label>
              </div>

              <div className="mt-5 flex flex-wrap items-end justify-between gap-3 border-t border-[var(--color-border)] pt-4">
                <div><p className="app-label">Products</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Select one product to review, or show the complete environment plan.</p></div>
                <div className="flex min-w-0 flex-1 flex-wrap justify-end gap-2">
                  <label className="min-w-64 max-w-md flex-1 text-xs text-[var(--color-text-muted)]"><span className="sr-only">Product to review in {environment.name}</span><select aria-label={`Product to review in ${environment.name}`} className="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-text-primary)]" value={selectedProduct} onChange={(event) => { const serviceId = event.target.value; setSelectedProducts((current) => ({ ...current, [environmentIndex]: serviceId })); if (serviceId) setExpandedProducts((current) => new Set(current).add(`${environmentIndex}:${serviceId}`)); }} disabled={allGroups.length === 0}><option value="">{allGroups.length === 0 ? "No planned products" : `All products (${allGroups.length})`}</option>{allGroups.map((group) => <option key={group.serviceId} value={group.serviceId}>{group.name} · {group.phases.length} metric{group.phases.length === 1 ? "" : "s"}</option>)}</select></label>
                  <button type="button" className="app-button-secondary h-9 gap-2 px-3" aria-expanded={isAddMetricOpen} disabled={available.length === 0} onClick={() => setAddMetricOpen((current) => { const next = new Set(current); if (next.has(environmentIndex)) next.delete(environmentIndex); else next.add(environmentIndex); return next; })}><Plus className="h-3.5 w-3.5" />Add metric</button>
                </div>
              </div>

              {isAddMetricOpen ? (
                <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
                  <label className="min-w-64 max-w-xl flex-1 text-xs font-semibold text-[var(--color-text-secondary)]">Metric to add<select aria-label={`Product metric to add to ${environment.name}`} className={inputClass} value={metricToAdd[environmentIndex] ?? ""} onChange={(event) => setMetricToAdd((current) => ({ ...current, [environmentIndex]: event.target.value }))}><option value="">Choose a product metric...</option>{[...optionsByService.entries()].map(([serviceId, options]) => { const selectable = options.filter((option) => available.some((candidate) => optionKey(candidate) === optionKey(option))); return selectable.length > 0 ? <optgroup key={serviceId} label={options[0].product_name}>{selectable.map((option) => <option key={optionKey(option)} value={optionKey(option)}>{option.metric_label} · {option.variants[0]?.part_number ?? "No SKU"}</option>)}</optgroup> : null; })}</select></label>
                  <button type="button" className="app-button-primary h-10 px-3" disabled={!metricToAdd[environmentIndex]} onClick={() => addMetric(environmentIndex)}>Add selected metric</button>
                  <button type="button" className="app-button-secondary h-10 px-3" onClick={() => setAddMetricOpen((current) => { const next = new Set(current); next.delete(environmentIndex); return next; })}>Cancel</button>
                </div>
              ) : null}

              {environment.phases.length === 0 ? <p className="mt-3 border-l-2 border-[var(--color-border)] py-2 pl-3 text-sm text-[var(--color-text-muted)]">No consumption is planned for this environment yet.</p> : null}
              {environment.phases.length > 0 && groups.length === 0 ? <p className="mt-3 py-3 text-sm text-[var(--color-text-muted)]">No products match the current product selection and search.</p> : null}

              {mode === "standard" ? (
                <div className="mt-3 space-y-2">
                  {groups.map((group) => {
                    const groupKey = `${environmentIndex}:${group.serviceId}`;
                    const expanded = productQuery.trim().length > 0 || expandedProducts.has(groupKey);
                    const activeMonths = group.phases.flatMap(({ phase }) => [phase.start_month, phase.end_month]);
                    return (
                      <article key={groupKey} className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                        <button type="button" className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[var(--color-surface-2)]" aria-expanded={expanded} onClick={() => toggleProduct(groupKey)}>
                          {expanded ? <ChevronDown className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" /> : <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />}
                          <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${productDot(group.serviceId)}`} aria-hidden="true" />
                          <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold text-[var(--color-text-primary)]">{group.name}</span><span className="mt-0.5 block text-xs text-[var(--color-text-muted)]">{group.phases.length} metric{group.phases.length === 1 ? "" : "s"} · M{Math.min(...activeMonths)}–M{Math.max(...activeMonths)}</span></span>
                          <span className="hidden rounded-full bg-[var(--color-surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--color-text-secondary)] sm:inline">{[...new Set(group.phases.map(({ phase }) => phase.quantity_unit).filter(Boolean))].join(" · ")}</span>
                        </button>
                        {expanded ? <div className="border-t border-[var(--color-border)] px-4 pb-4">{group.phases.map(({ phase, phaseIndex }) => {
                          const selectedOption = metricOptions.find((option) => option.service_id === phase.service_id && option.metric_key === phase.metric_key);
                          const selectedVariant = selectedOption?.variants.find((variant) => variant.sku_mapping_id === phase.sku_mapping_id)
                            ?? selectedOption?.variants.find((variant) => variant.sku_mapping_id === selectedOption.default_sku_mapping_id)
                            ?? selectedOption?.variants[0];
                          const serviceOptions = optionsByService.get(group.serviceId) ?? [];
                          const policy = selectedVariant ?? selectedOption;
                          const presets = policy?.quantity_presets ?? [];
                          const sourceQuantity = phase.start_quantity ?? 0;
                          const quotedQuantity = policy ? normalizedQuote(sourceQuantity, policy.quantity_increment, policy.minimum_quantity) : sourceQuantity;
                          const envelopeQuantity = planningEnvelope(sourceQuantity, policy?.planning_envelope_increment);
                          return (
                            <div key={`phase-${environmentIndex}-${phaseIndex}`} className="relative grid gap-3 border-t border-[var(--color-border)] pt-4 first:border-t-0 md:grid-cols-2 xl:grid-cols-4 xl:items-end">
                              <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Billing metric<select aria-label={`${environment.name} ${group.name} billing metric`} className={inputClass} value={phase.metric_key ?? ""} onChange={(event) => replaceMetric(environmentIndex, phaseIndex, serviceOptions.find((option) => option.metric_key === event.target.value))}>{serviceOptions.map((option) => <option key={option.metric_key} value={option.metric_key}>{option.metric_label}</option>)}</select></label>
                              {selectedOption ? <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Commercial variant<select aria-label={`${environment.name} ${selectedOption.product_name} commercial variant`} className={`${inputClass} font-medium`} value={selectedVariant?.sku_mapping_id ?? ""} onChange={(event) => replaceVariant(environmentIndex, phaseIndex, selectedOption, event.target.value)}>{selectedOption.variants.map((variant) => <option key={variant.sku_mapping_id} value={variant.sku_mapping_id}>{variant.label}</option>)}</select></label> : null}
                              <label className="text-xs text-[var(--color-text-muted)]">Start month<input type="number" min={1} max={contractMonths} disabled={phase.interpolation === "monthly"} className={`${inputClass} disabled:opacity-55`} value={phase.start_month} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, start_month: Number(event.target.value) })} /></label>
                              <label className="text-xs text-[var(--color-text-muted)]">End month<input type="number" min={1} max={contractMonths} disabled={phase.interpolation === "monthly"} className={`${inputClass} disabled:opacity-55`} value={phase.end_month} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, end_month: Number(event.target.value) })} /></label>
                              <label className="text-xs text-[var(--color-text-muted)]">Initial quantity<input aria-label={`${environment.name} ${selectedOption?.metric_label ?? phase.metric_key} initial quantity`} type="number" min={0} step={policy?.quantity_increment ?? "any"} disabled={phase.interpolation === "monthly"} className={`${inputClass} disabled:opacity-55`} value={phase.start_quantity ?? 0} onChange={(event) => { const value = Number(event.target.value); patchPhase(environmentIndex, phaseIndex, { ...phase, start_quantity: value, end_quantity: phase.interpolation === "step" ? value : phase.end_quantity }); }} /></label>
                              <label className="text-xs text-[var(--color-text-muted)]">Final quantity<input type="number" min={0} step={policy?.quantity_increment ?? "any"} disabled={phase.interpolation !== "linear"} className={`${inputClass} disabled:opacity-55`} value={phase.end_quantity ?? 0} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, end_quantity: Number(event.target.value) })} /></label>
                              <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Schedule<select className={inputClass} value={phase.interpolation} onChange={(event) => setSchedule(environmentIndex, phaseIndex, event.target.value as DeploymentRampPhaseInput["interpolation"])}><option value="step">Constant</option><option value="linear">Linear ramp</option><option value="monthly">Monthly steps</option></select></label>
                              <div className="flex items-center justify-between gap-3 xl:col-span-2"><p className="text-xs leading-5 text-[var(--color-text-muted)]"><span className="font-semibold text-[var(--color-text-secondary)]">{phase.quantity_unit ?? policy?.quantity_unit ?? "Unit"}</span> · {quantityRule(policy)}</p><button type="button" className="app-icon-button shrink-0" title="Remove product metric" onClick={() => removeMetric(environmentIndex, phaseIndex)}><Trash2 className="h-4 w-4" /></button></div>
                              {policy ? <div className="border-l-2 border-[var(--color-accent)] pl-3 text-xs leading-5 text-[var(--color-text-secondary)] md:col-span-2 xl:col-span-4"><div className="flex flex-wrap items-center gap-2"><span className="inline-flex items-center gap-1 font-semibold text-[var(--color-text-primary)]">{policy.usage_basis === "provisioned_runtime" ? <Clock3 className="h-3.5 w-3.5" /> : <PackageCheck className="h-3.5 w-3.5" />}{basisLabel(policy.usage_basis)}</span><span>·</span><span>{policy.entry_guidance}</span></div><p className="mt-1 text-[var(--color-text-muted)]">{policyLabel(policy.aggregation_window)} · {policyLabel(policy.proration_policy)}{policy.free_tier_scope !== "none" ? ` · Free tier: ${policyLabel(policy.free_tier_scope)}` : ""}</p>{quotedQuantity !== sourceQuantity ? <p className="mt-1 font-semibold text-[var(--color-text-primary)]">Measured demand {sourceQuantity.toLocaleString()} → billable quantity {quotedQuantity.toLocaleString()} {phase.quantity_unit}</p> : null}{envelopeQuantity !== null && envelopeQuantity !== quotedQuantity ? <p className="mt-1 font-semibold text-[var(--color-text-primary)]">Optional planning reserve: {envelopeQuantity.toLocaleString()} {phase.quantity_unit}. This does not change the Oracle-metered quantity.</p> : null}</div> : null}
                              {presets.length > 0 ? <div className="flex flex-wrap items-center gap-2 md:col-span-2 xl:col-span-4"><span className="text-xs font-semibold text-[var(--color-text-secondary)]">Runtime shortcuts</span>{presets.map((preset) => <button key={preset.label} type="button" title={preset.description} className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${sourceQuantity === preset.quantity ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]" : "border-[var(--color-border)] text-[var(--color-text-secondary)]"}`} onClick={() => applyPreset(environmentIndex, phaseIndex, preset.quantity)}>{preset.label} · {preset.quantity}h</button>)}</div> : null}
                              {selectedOption?.requires_explicit_quantity && sourceQuantity === 0 ? <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 md:col-span-2 xl:col-span-4">Quantity required: this value cannot be inferred safely from integration traffic.</p> : null}
                              {selectedOption?.metric_key === "di_workspace_hours" && sourceQuantity === 744 ? <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 md:col-span-2 xl:col-span-4">Always-on assumption: confirm that this workspace will remain running for the full month.</p> : null}
                            </div>
                          );
                        })}</div> : null}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-3 overflow-x-auto border-y border-[var(--color-border)]">
                  <table className="min-w-max text-left text-xs">
                    <thead className="bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"><tr><th className="sticky left-0 z-10 min-w-72 bg-[var(--color-surface-2)] px-3 py-2.5">Product metric</th>{Array.from({ length: contractMonths }, (_, index) => <th key={index} className="min-w-24 px-2 py-2.5 text-center">M{index + 1}</th>)}</tr></thead>
                    <tbody>{groups.map((group) => <Fragment key={`matrix-group-${environmentIndex}-${group.serviceId}`}><tr className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)]"><th colSpan={contractMonths + 1} className="px-3 py-2"><span className="inline-flex items-center gap-2 font-semibold text-[var(--color-text-primary)]"><span className={`h-2.5 w-2.5 rounded-full ${productDot(group.serviceId)}`} />{group.name}</span></th></tr>{group.phases.map(({ phase, phaseIndex }) => { const option = metricOptions.find((candidate) => candidate.service_id === phase.service_id && candidate.metric_key === phase.metric_key); const variant = option?.variants.find((candidate) => candidate.sku_mapping_id === phase.sku_mapping_id); return <tr key={`matrix-${environmentIndex}-${phaseIndex}`} className="border-t border-[var(--color-border)]"><th className="sticky left-0 z-10 bg-[var(--color-surface)] px-3 py-3"><span className="block text-sm font-semibold text-[var(--color-text-primary)]">{option?.metric_label ?? phase.metric_key}</span><span className="mt-1 block font-normal text-[var(--color-text-muted)]">{variant?.label ?? "Commercial variant pending"}</span><span className="mt-1 block font-normal text-[var(--color-text-muted)]">{phase.quantity_unit}</span></th>{phaseMonthlyQuantities(phase, contractMonths).map((quantity, monthIndex) => <td key={monthIndex} className="px-1.5 py-2"><input aria-label={`${environment.name} ${option?.metric_label ?? phase.metric_key} month ${monthIndex + 1}`} type="number" min={0} step={variant?.quantity_increment ?? option?.quantity_increment ?? "any"} className="w-20 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-2 text-right font-mono text-xs" value={quantity} onChange={(event) => patchPhase(environmentIndex, phaseIndex, withMonthlyQuantity(phase, contractMonths, monthIndex + 1, Number(event.target.value)))} /></td>)}</tr>; })}</Fragment>)}</tbody>
                  </table>
                </div>
              )}
            </section>
          );
        })}
      </div>

      <p className={`mt-3 text-sm font-semibold ${readiness.ready ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}`}>
        {readiness.environments} environment{readiness.environments === 1 ? "" : "s"} · {readiness.plannedMetrics} planned product metric{readiness.plannedMetrics === 1 ? "" : "s"}{readiness.ready ? " · ready to save" : " · add at least one quantity plan"}
      </p>
    </div>
  );
}
