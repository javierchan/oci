"use client";

/* Edits one normalized real-unit consumption plan in standard and monthly views. */

import { LayoutList, Plus, Table2, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

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
} from "@/lib/types";

type ConsumptionEditorProps = {
  contractMonths: number;
  environments: DeploymentEnvironmentInput[];
  metricOptions: ScenarioMetricOption[];
  onChange: (_environments: DeploymentEnvironmentInput[]) => void;
};

function optionKey(option: Pick<ScenarioMetricOption, "service_id" | "metric_key">): string {
  return `${option.service_id}:${option.metric_key}`;
}

function quantityRule(option: Pick<ScenarioMetricOption, "quantity_behavior" | "quantity_increment" | "minimum_quantity"> | undefined): string {
  if (!option) return "Governed rule unavailable";
  const behavior = option.quantity_behavior.replaceAll("_", " ");
  const increment = option.quantity_increment === 1 ? "whole units" : `${option.quantity_increment} increments`;
  return `${behavior} · ${increment}${option.minimum_quantity > 0 ? ` · minimum ${option.minimum_quantity}` : ""}`;
}

export function BomConsumptionEditor({
  contractMonths,
  environments,
  metricOptions,
  onChange,
}: ConsumptionEditorProps): JSX.Element {
  const [mode, setMode] = useState<"standard" | "monthly">("standard");
  const readiness = useMemo(() => explicitPlanReadiness(environments), [environments]);
  const products = useMemo(
    () => [...new Map(metricOptions.map((option) => [option.service_id, option.product_name])).entries()],
    [metricOptions],
  );

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

  function addMetric(environmentIndex: number): void {
    const existing = new Set(environments[environmentIndex].phases.map((phase) => `${phase.service_id}:${phase.metric_key}`));
    const option = metricOptions.find((candidate) => !existing.has(optionKey(candidate))) ?? metricOptions[0];
    if (!option) return;
    patchEnvironment(environmentIndex, {
      phases: [...environments[environmentIndex].phases, explicitQuantityPhase(option, contractMonths)],
    });
  }

  function removeMetric(environmentIndex: number, phaseIndex: number): void {
    patchEnvironment(environmentIndex, {
      phases: environments[environmentIndex].phases.filter((_, current) => current !== phaseIndex),
    });
  }

  function replaceMetric(
    environmentIndex: number,
    phaseIndex: number,
    option: ScenarioMetricOption | undefined,
  ): void {
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

  return (
    <div className="mt-5 border-t border-[var(--color-border)] pt-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="app-label">Environment Consumption</p>
          <h3 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">Plan in the units Oracle actually bills</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Choose an environment, exact commercial variant, billing metric, active months, and real quantity. Edition, license model, SKU, rounding, and minimums remain attached to the estimate.
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
        <p><span className="font-semibold text-[var(--color-text-primary)]">1. Where</span><br />Name DEV, QA, PROD, or DR and set its runtime posture.</p>
        <p><span className="font-semibold text-[var(--color-text-primary)]">2. What</span><br />Select the product, edition or license variant, SKU metric, and billing-unit quantity.</p>
        <p><span className="font-semibold text-[var(--color-text-primary)]">3. When</span><br />Use a constant, linear, or exact month-by-month activation schedule.</p>
      </div>

      <div className="mt-2 divide-y divide-[var(--color-border)]">
        {environments.map((environment, environmentIndex) => (
          <section key={`environment-${environmentIndex}`} className="py-5" aria-label={`${environment.name || `Environment ${environmentIndex + 1}`} consumption plan`}>
            <div className="relative grid gap-3 pr-11 md:grid-cols-2 md:items-end">
              <label className="text-xs font-semibold text-[var(--color-text-secondary)] md:col-span-2">Environment<input aria-label={`Environment ${environmentIndex + 1} name`} className="mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm text-[var(--color-text-primary)]" value={environment.name} onChange={(event) => patchEnvironment(environmentIndex, { name: event.target.value })} /></label>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)]">Hours / month<input type="number" min={0} max={744} className="mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={environment.active_hours_month} onChange={(event) => patchEnvironment(environmentIndex, { active_hours_month: Number(event.target.value) })} /></label>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)]">HA multiplier<input type="number" min={1} max={10} step={0.1} className="mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={environment.ha_multiplier} onChange={(event) => patchEnvironment(environmentIndex, { ha_multiplier: Number(event.target.value) })} /></label>
              <label className="text-xs font-semibold text-[var(--color-text-secondary)]">DR role<select className="mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={environment.dr_role} onChange={(event) => patchEnvironment(environmentIndex, { dr_role: event.target.value as DeploymentEnvironmentInput["dr_role"] })}><option value="primary">Primary</option><option value="standby">Standby</option><option value="none">None</option></select></label>
              <button type="button" className="app-icon-button absolute right-0 top-0" title="Remove environment" disabled={environments.length === 1} onClick={() => removeEnvironment(environmentIndex)}><Trash2 className="h-4 w-4" /></button>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div><p className="app-label">Product Metrics</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Months without a quantity remain inactive at zero.</p></div>
              <button type="button" className="app-button-secondary h-9 gap-2 px-3" disabled={metricOptions.length === 0} onClick={() => addMetric(environmentIndex)}><Plus className="h-3.5 w-3.5" />Add product metric</button>
            </div>

            {environment.phases.length === 0 ? <p className="mt-3 border-l-2 border-[var(--color-border)] py-2 pl-3 text-sm text-[var(--color-text-muted)]">No consumption is planned for this environment yet.</p> : null}

            {mode === "standard" ? (
              <div className="mt-3 space-y-3">
                {environment.phases.map((phase, phaseIndex) => {
                  const selectedOption = metricOptions.find((option) => option.service_id === phase.service_id && option.metric_key === phase.metric_key);
                  const selectedVariant = selectedOption?.variants.find((variant) => variant.sku_mapping_id === phase.sku_mapping_id)
                    ?? selectedOption?.variants.find((variant) => variant.sku_mapping_id === selectedOption.default_sku_mapping_id)
                    ?? selectedOption?.variants[0];
                  const serviceOptions = metricOptions.filter((option) => option.service_id === phase.service_id);
                  return (
                    <div key={`phase-${environmentIndex}-${phaseIndex}`} className="relative grid gap-3 border-t border-[var(--color-border)] pt-3 pr-11 md:grid-cols-2 xl:grid-cols-4 xl:items-end">
                      <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Product<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm" value={phase.service_id ?? ""} onChange={(event) => replaceMetric(environmentIndex, phaseIndex, metricOptions.find((option) => option.service_id === event.target.value))}>{products.map(([serviceId, productName]) => <option key={serviceId} value={serviceId}>{productName}</option>)}</select></label>
                      <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Billing metric<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm" value={phase.metric_key ?? ""} onChange={(event) => replaceMetric(environmentIndex, phaseIndex, serviceOptions.find((option) => option.metric_key === event.target.value))}>{serviceOptions.map((option) => <option key={option.metric_key} value={option.metric_key}>{option.metric_label}</option>)}</select></label>
                      {selectedOption ? <label className="text-xs text-[var(--color-text-muted)] xl:col-span-4">Commercial variant<select aria-label={`${environment.name} ${selectedOption.product_name} commercial variant`} className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm font-medium text-[var(--color-text-primary)]" value={selectedVariant?.sku_mapping_id ?? ""} onChange={(event) => replaceVariant(environmentIndex, phaseIndex, selectedOption, event.target.value)}>{selectedOption.variants.map((variant) => <option key={variant.sku_mapping_id} value={variant.sku_mapping_id}>{variant.label}</option>)}</select><span className="mt-1.5 block text-xs leading-5 text-[var(--color-text-muted)]">This selection applies only to {environment.name}. Other environments may use a different approved edition, license, or SKU.</span></label> : null}
                      <label className="text-xs text-[var(--color-text-muted)]">Start month<input type="number" min={1} max={contractMonths} disabled={phase.interpolation === "monthly"} className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm disabled:opacity-55" value={phase.start_month} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, start_month: Number(event.target.value) })} /></label>
                      <label className="text-xs text-[var(--color-text-muted)]">End month<input type="number" min={1} max={contractMonths} disabled={phase.interpolation === "monthly"} className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm disabled:opacity-55" value={phase.end_month} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, end_month: Number(event.target.value) })} /></label>
                      <label className="text-xs text-[var(--color-text-muted)]">Initial quantity<input type="number" min={0} step="any" disabled={phase.interpolation === "monthly"} className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm disabled:opacity-55" value={phase.start_quantity ?? 0} onChange={(event) => { const value = Number(event.target.value); patchPhase(environmentIndex, phaseIndex, { ...phase, start_quantity: value, end_quantity: phase.interpolation === "step" ? value : phase.end_quantity }); }} /></label>
                      <label className="text-xs text-[var(--color-text-muted)]">Final quantity<input type="number" min={0} step="any" disabled={phase.interpolation !== "linear"} className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm disabled:opacity-55" value={phase.end_quantity ?? 0} onChange={(event) => patchPhase(environmentIndex, phaseIndex, { ...phase, end_quantity: Number(event.target.value) })} /></label>
                      <label className="text-xs text-[var(--color-text-muted)] xl:col-span-2">Schedule<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-sm" value={phase.interpolation} onChange={(event) => setSchedule(environmentIndex, phaseIndex, event.target.value as DeploymentRampPhaseInput["interpolation"])}><option value="step">Constant</option><option value="linear">Linear ramp</option><option value="monthly">Monthly steps</option></select></label>
                      <button type="button" className="app-icon-button absolute right-0 top-3" title="Remove product metric" onClick={() => removeMetric(environmentIndex, phaseIndex)}><Trash2 className="h-4 w-4" /></button>
                      <p className="self-end text-xs leading-5 text-[var(--color-text-muted)] md:col-span-2 xl:col-span-2"><span className="font-semibold text-[var(--color-text-secondary)]">{phase.quantity_unit ?? selectedVariant?.quantity_unit ?? selectedOption?.quantity_unit ?? "Unit"}</span> · {quantityRule(selectedVariant ?? selectedOption)}</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 overflow-x-auto border-y border-[var(--color-border)]">
                <table className="min-w-max text-left text-xs">
                  <thead className="bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"><tr><th className="sticky left-0 z-10 min-w-64 bg-[var(--color-surface-2)] px-3 py-2.5">Product metric</th>{Array.from({ length: contractMonths }, (_, index) => <th key={index} className="min-w-24 px-2 py-2.5 text-center">M{index + 1}</th>)}</tr></thead>
                  <tbody className="divide-y divide-[var(--color-border)]">{environment.phases.map((phase, phaseIndex) => {
                    const option = metricOptions.find((candidate) => candidate.service_id === phase.service_id && candidate.metric_key === phase.metric_key);
                    const variant = option?.variants.find((candidate) => candidate.sku_mapping_id === phase.sku_mapping_id);
                    return <tr key={`matrix-${environmentIndex}-${phaseIndex}`}><th className="sticky left-0 z-10 bg-[var(--color-surface)] px-3 py-3"><span className="block text-sm font-semibold text-[var(--color-text-primary)]">{option?.product_name ?? phase.service_id}</span><span className="mt-1 block font-normal text-[var(--color-text-muted)]">{variant?.label ?? "Commercial variant pending"}</span><span className="mt-1 block font-normal text-[var(--color-text-muted)]">{option?.metric_label ?? phase.metric_key} · {phase.quantity_unit}</span></th>{phaseMonthlyQuantities(phase, contractMonths).map((quantity, monthIndex) => <td key={monthIndex} className="px-1.5 py-2"><input aria-label={`${environment.name} ${option?.metric_label ?? phase.metric_key} month ${monthIndex + 1}`} type="number" min={0} step="any" className="w-20 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-2 text-right font-mono text-xs" value={quantity} onChange={(event) => patchPhase(environmentIndex, phaseIndex, withMonthlyQuantity(phase, contractMonths, monthIndex + 1, Number(event.target.value)))} /></td>)}</tr>;
                  })}</tbody>
                </table>
              </div>
            )}
          </section>
        ))}
      </div>

      <p className={`mt-3 text-sm font-semibold ${readiness.ready ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300"}`}>
        {readiness.environments} environment{readiness.environments === 1 ? "" : "s"} · {readiness.plannedMetrics} planned product metric{readiness.plannedMetrics === 1 ? "" : "s"}{readiness.ready ? " · ready to save" : " · add at least one quantity plan"}
      </p>
    </div>
  );
}
