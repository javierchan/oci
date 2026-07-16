/* Regression coverage for governed BOM rollout presentation helpers. */

import { describe, expect, it } from "vitest";

import {
  activeComparisonCategories,
  buildBomChartData,
  buildComparisonPeriodData,
  buildRolloutSignals,
  explicitPlanReadiness,
  explicitQuantityPhase,
  governedRampServiceIds,
  linePeriodMonthlyQuantities,
  phaseMonthlyQuantities,
  resizeConsumptionPlan,
  serviceProductLabel,
  topContractDrivers,
  withMonthlyQuantity,
} from "./bom-ramp";
import type { BomRampSnapshot } from "./bom-ramp";
import type { BomSnapshot } from "./types";

const snapshot: BomRampSnapshot = {
  currency: "USD",
  monthly_series: [
    { period_index: 1, period_start: "2026-01-01", total: 20, cumulative_total: 20, by_environment: { QA: 20 }, by_service: { OIC3: 20 } },
    { period_index: 2, period_start: "2026-02-01", total: 70, cumulative_total: 90, by_environment: { Production: 50, QA: 20 }, by_service: { OIC3: 60, STREAMING: 10 } },
  ],
  line_items: [
    { service_id: "OIC3", environment: "Production", contract_amount: 80, periods: [] },
    { service_id: "STREAMING", environment: "Production", contract_amount: 10, periods: [] },
    { service_id: "OIC3", environment: "QA", contract_amount: 15, periods: [] },
  ],
};

describe("BOM ramp presentation", () => {
  it("preserves monthly composition and cumulative totals", () => {
    const result = buildBomChartData(snapshot, "environment");
    expect(result.keys).toEqual(["Production", "QA"]);
    expect(result.rows[1]).toMatchObject({ month: "Feb 26", Production: 50, QA: 20, cumulative: 90 });
  });

  it("rebuilds a missing aggregate chart from immutable line periods", () => {
    const result = buildBomChartData({
      currency: "USD",
      monthly_series: [],
      line_items: [
        {
          service_id: "OIC3",
          environment: "Production",
          contract_amount: 30,
          periods: [
            { period_index: 1, period_start: "2026-01-01", amount: 10 },
            { period_index: 2, period_start: "2026-02-01", amount: 20 },
          ] as BomSnapshot["line_items"][number]["periods"],
        },
      ],
    }, "service");
    expect(result.keys).toEqual(["OIC3"]);
    expect(result.rows).toEqual([
      { month: "Jan 26", cumulative: 10, OIC3: 10 },
      { month: "Feb 26", cumulative: 30, OIC3: 20 },
    ]);
  });

  it("ranks contract drivers without double-counting labels", () => {
    expect(topContractDrivers(snapshot)).toEqual([["OIC3", 95], ["STREAMING", 10]]);
  });

  it("summarizes the first active environment and production start", () => {
    expect(buildRolloutSignals({
      monthly_series: snapshot.monthly_series,
      steady_state_period: 2,
      ramp_deferred_amount: 35,
    })).toEqual({
      firstEnvironment: { environment: "QA", period: 1 },
      productionStart: { environment: "Production", period: 2 },
      stabilizationPeriod: 2,
      timingEffect: 35,
    });
  });

  it("uses capacity activation even when an included product has no cost", () => {
    const environments = [{
      name: "Development",
      active_hours_month: 160,
      demand_share: 1,
      ha_multiplier: 1,
      dr_role: "none" as const,
      phases: [{
        service_id: "EVENTS",
        metric_key: "events",
        start_month: 1,
        end_month: 12,
        start_multiplier: 1,
        end_multiplier: 1,
        interpolation: "step" as const,
        start_quantity: 1,
        end_quantity: 1,
        quantity_unit: "events",
        monthly_quantities: [],
        rationale: null,
      }],
    }];
    expect(buildRolloutSignals({
      monthly_series: snapshot.monthly_series,
      steady_state_period: 2,
      ramp_deferred_amount: 35,
    }, environments).firstEnvironment).toEqual({ environment: "Development", period: 1 });
  });

  it("uses real product units in standard and monthly plans", () => {
    const option = {
      service_id: "OIC3",
      product_name: "Oracle Integration 3",
      metric_key: "oic_messages_10k_packs",
      metric_label: "Messages",
      quantity_unit: "10K message packs",
      source_baseline_quantity: 12,
      baseline_quantity: 12,
      planning_envelope_quantity: null,
      quantity_behavior: "packaged" as const,
      quantity_increment: 1,
      minimum_quantity: 1,
      usage_basis: "allocated_capacity",
      quote_rounding: "whole_commercial_unit",
      aggregation_window: "peak_hour",
      proration_policy: "whole_capacity_pack",
      free_tier_scope: "none",
      planning_envelope_increment: null,
      metering_policy: { message_block_kb: 50 },
      requires_explicit_quantity: false,
      entry_guidance: "Enter message packs.",
      quantity_presets: [],
      default_sku_mapping_id: "mapping-standard",
      default_selected: true,
      variants: [{
        sku_mapping_id: "mapping-standard",
        label: "Standard · PAYG · B89639",
        part_number: "B89639",
        predicates: { edition: "standard", byol: false },
        is_billable: true,
        selection_policy: "required" as const,
        quantity_behavior: "packaged" as const,
        quantity_increment: 1,
        minimum_quantity: 1,
        quantity_unit: "10K message packs",
        usage_basis: "allocated_capacity",
        quote_rounding: "whole_commercial_unit",
        aggregation_window: "peak_hour",
        proration_policy: "whole_capacity_pack",
        free_tier_scope: "none",
        planning_envelope_increment: null,
        metering_policy: { message_block_kb: 50 },
        requires_explicit_quantity: false,
        entry_guidance: "Enter message packs.",
        quantity_presets: [],
      }],
    };
    const standard = explicitQuantityPhase(option, 4);
    expect(standard.sku_mapping_id).toBe("mapping-standard");
    expect(phaseMonthlyQuantities(standard, 4)).toEqual([12, 12, 12, 12]);
    const monthly = withMonthlyQuantity(standard, 4, 2, 7);
    expect(phaseMonthlyQuantities(monthly, 4)).toEqual([12, 7, 12, 12]);
    expect(explicitPlanReadiness([{
      name: "Production",
      active_hours_month: 744,
      demand_share: 1,
      ha_multiplier: 1,
      dr_role: "primary",
      phases: [monthly],
    }])).toEqual({ ready: true, environments: 1, plannedMetrics: 1 });
  });

  it("reconstructs immutable monthly product consumption from BOM line periods", () => {
    expect(linePeriodMonthlyQuantities([
      { period_index: 1, quantity: 5 },
      { period_index: 3, quantity: 8 },
      { period_index: 12, quantity: 13 },
    ], 12)).toEqual([5, 0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 13]);
  });

  it("keeps standard and monthly plans valid when the contract duration changes", () => {
    const baseEnvironment = {
      name: "Production",
      active_hours_month: 744,
      demand_share: 1,
      ha_multiplier: 1,
      dr_role: "primary" as const,
      phases: [{
        service_id: "OIC3",
        metric_key: "oic_messages_10k_packs",
        start_month: 3,
        end_month: 12,
        start_multiplier: 1,
        end_multiplier: 1,
        interpolation: "monthly" as const,
        start_quantity: null,
        end_quantity: null,
        quantity_unit: "10K message packs",
        monthly_quantities: Array.from({ length: 12 }, (_, index) => ({ period_index: index + 1, quantity: index + 1 })),
        rationale: null,
      }],
    };
    const reduced = resizeConsumptionPlan([baseEnvironment], 6);
    expect(reduced[0].phases[0]).toMatchObject({ start_month: 1, end_month: 6 });
    expect(reduced[0].phases[0].monthly_quantities).toHaveLength(6);
    expect(reduced[0].phases[0].monthly_quantities[5]).toEqual({ period_index: 6, quantity: 6 });

    const standard = {
      ...baseEnvironment,
      phases: [{ ...baseEnvironment.phases[0], interpolation: "linear" as const, start_month: 8, end_month: 12, start_quantity: 2, end_quantity: 8, monthly_quantities: [] }],
    };
    expect(resizeConsumptionPlan([standard], 6)[0].phases[0]).toMatchObject({ start_month: 6, end_month: 6 });
  });

  it("orders monthly comparison deltas numerically", () => {
    expect(buildComparisonPeriodData({ period_deltas: { 10: 30, 2: -15, 1: -20 } })).toEqual([
      { period: "M1", delta: -20 },
      { period: "M2", delta: -15 },
      { period: "M10", delta: 30 },
    ]);
  });

  it("exposes only active comparison categories", () => {
    expect(activeComparisonCategories({
      driver_categories: { price_change: false, environment_change: true, ramp_change: true },
    })).toEqual(["environment change", "ramp change"]);
  });

  it("presents governed service identifiers with readable product names", () => {
    expect(serviceProductLabel("OIC3")).toBe("Oracle Integration 3");
    expect(serviceProductLabel("CUSTOM_SERVICE")).toBe("Custom Service");
  });

  it("keeps detected and persisted ramp products unique", () => {
    expect(governedRampServiceIds(
      ["STREAMING", "OIC3"],
      [{ phases: [{ service_id: "OIC3" }, { service_id: "QUEUE" }, { service_id: null }] }],
    )).toEqual(["QUEUE", "STREAMING", "OIC3"]);
  });
});
