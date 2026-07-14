/* Pure presentation helpers for governed BOM rollout charts, signals, and product labels. */

import type {
  BomComparison,
  BomSnapshot,
  DeploymentEnvironmentInput,
  DeploymentRampPhaseInput,
  ScenarioMetricOption,
} from "./types";

export type BomCompositionMode = "environment" | "service";
export type BomRolloutActivation = {
  environment: string;
  period: number;
};
export type BomRolloutSignals = {
  firstEnvironment: BomRolloutActivation | null;
  productionStart: BomRolloutActivation | null;
  stabilizationPeriod: number | null;
  timingEffect: number;
};
export type BomRampSnapshot = {
  currency: BomSnapshot["currency"];
  monthly_series: BomSnapshot["monthly_series"];
  line_items: Array<Pick<BomSnapshot["line_items"][number], "service_id" | "contract_amount">>;
};

const SERVICE_PRODUCT_LABELS: Record<string, string> = {
  API_GATEWAY: "OCI API Gateway",
  DATA_INTEGRATION: "OCI Data Integration",
  EVENTS: "OCI Events",
  FUNCTIONS: "OCI Functions",
  GOLDENGATE: "Oracle GoldenGate",
  OIC3: "Oracle Integration 3",
  PROCESS_AUTOMATION: "OCI Process Automation",
  QUEUE: "OCI Queue",
  STREAMING: "OCI Streaming",
};

export function serviceProductLabel(serviceId: string): string {
  return SERVICE_PRODUCT_LABELS[serviceId]
    ?? serviceId
      .split("_")
      .filter(Boolean)
      .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1).toLowerCase()}`)
      .join(" ");
}

export function governedRampServiceIds(
  detectedServices: string[],
  environments: Array<{ phases: Array<{ service_id: string | null }> }>,
): string[] {
  return [...new Set([
    ...detectedServices,
    ...environments.flatMap((environment) => environment.phases.flatMap((phase) => phase.service_id ? [phase.service_id] : [])),
  ])].sort((left, right) => serviceProductLabel(left).localeCompare(serviceProductLabel(right)));
}

export function explicitQuantityPhase(
  option: ScenarioMetricOption,
  contractMonths: number,
): DeploymentRampPhaseInput {
  return {
    service_id: option.service_id,
    metric_key: option.metric_key,
    sku_mapping_id: option.default_sku_mapping_id,
    start_month: 1,
    end_month: contractMonths,
    start_multiplier: 1,
    end_multiplier: 1,
    interpolation: "step",
    start_quantity: option.baseline_quantity,
    end_quantity: option.baseline_quantity,
    quantity_unit: option.quantity_unit,
    monthly_quantities: [],
    rationale: "Governed baseline quantity in the commercial metric unit.",
  };
}

export function phaseMonthlyQuantities(
  phase: DeploymentRampPhaseInput,
  contractMonths: number,
): number[] {
  const values = Array.from({ length: contractMonths }, () => 0);
  if (phase.interpolation === "monthly") {
    for (const item of phase.monthly_quantities) {
      if (item.period_index >= 1 && item.period_index <= contractMonths) {
        values[item.period_index - 1] = item.quantity;
      }
    }
    return values;
  }
  const start = Math.max(1, phase.start_month);
  const end = Math.min(contractMonths, phase.end_month);
  const startQuantity = phase.start_quantity ?? 0;
  const endQuantity = phase.end_quantity ?? startQuantity;
  for (let month = start; month <= end; month += 1) {
    const progress = end === start ? 0 : (month - start) / (end - start);
    values[month - 1] = phase.interpolation === "linear"
      ? startQuantity + ((endQuantity - startQuantity) * progress)
      : startQuantity;
  }
  return values;
}

export function withMonthlyQuantity(
  phase: DeploymentRampPhaseInput,
  contractMonths: number,
  periodIndex: number,
  quantity: number,
): DeploymentRampPhaseInput {
  const values = phaseMonthlyQuantities(phase, contractMonths);
  values[periodIndex - 1] = Math.max(quantity, 0);
  return {
    ...phase,
    start_month: 1,
    end_month: contractMonths,
    interpolation: "monthly",
    start_quantity: null,
    end_quantity: null,
    monthly_quantities: values.map((value, index) => ({ period_index: index + 1, quantity: value })),
  };
}

export function resizeConsumptionPlan(
  environments: DeploymentEnvironmentInput[],
  contractMonths: number,
): DeploymentEnvironmentInput[] {
  const boundedMonths = Math.min(Math.max(Math.trunc(contractMonths), 1), 120);
  return environments.map((environment) => ({
    ...environment,
    phases: environment.phases.map((phase) => {
      if (phase.interpolation === "monthly") {
        const quantities = phaseMonthlyQuantities(phase, boundedMonths);
        return {
          ...phase,
          start_month: 1,
          end_month: boundedMonths,
          monthly_quantities: quantities.map((quantity, index) => ({
            period_index: index + 1,
            quantity,
          })),
        };
      }
      const startMonth = Math.min(Math.max(phase.start_month, 1), boundedMonths);
      return {
        ...phase,
        start_month: startMonth,
        end_month: Math.min(Math.max(phase.end_month, startMonth), boundedMonths),
      };
    }),
  }));
}

export function explicitPlanReadiness(
  environments: DeploymentEnvironmentInput[],
): { ready: boolean; environments: number; plannedMetrics: number } {
  const validEnvironments = environments.filter((environment) => environment.name.trim().length > 0);
  const plannedMetrics = validEnvironments.reduce(
    (total, environment) => total + environment.phases.filter((phase) => (
      Boolean(phase.service_id)
      && Boolean(phase.metric_key)
      && Boolean(phase.quantity_unit)
      && (phase.start_quantity !== null || phase.monthly_quantities.length > 0)
    )).length,
    0,
  );
  return {
    ready: validEnvironments.length === environments.length && plannedMetrics > 0,
    environments: validEnvironments.length,
    plannedMetrics,
  };
}

export function buildBomChartData(
  snapshot: BomRampSnapshot,
  mode: BomCompositionMode,
): { keys: string[]; rows: Array<Record<string, number | string>> } {
  const source = mode === "environment" ? "by_environment" : "by_service";
  const keys = Array.from(
    new Set(snapshot.monthly_series.flatMap((period) => Object.keys(period[source]))),
  ).sort();
  const formatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  });
  return {
    keys,
    rows: snapshot.monthly_series.map((period) => ({
      month: formatter.format(new Date(`${period.period_start}T00:00:00Z`)),
      cumulative: period.cumulative_total,
      ...(mode === "environment" ? period.by_environment : period.by_service),
    })),
  };
}

export function topContractDrivers(snapshot: BomRampSnapshot, limit = 6): Array<[string, number]> {
  const totals = new Map<string, number>();
  for (const line of snapshot.line_items) {
    totals.set(line.service_id, (totals.get(line.service_id) ?? 0) + line.contract_amount);
  }
  return [...totals.entries()].sort((left, right) => right[1] - left[1]).slice(0, limit);
}

function looksLikeProduction(environment: string): boolean {
  const normalized = environment.trim().toLowerCase();
  return normalized === "prod"
    || normalized === "production"
    || normalized.startsWith("prod-")
    || normalized.startsWith("prd-");
}

export function firstEnvironmentActivation(
  snapshot: Pick<BomSnapshot, "monthly_series">,
  predicate: (_environment: string) => boolean = () => true,
): BomRolloutActivation | null {
  for (const period of [...snapshot.monthly_series].sort((left, right) => left.period_index - right.period_index)) {
    const environment = Object.entries(period.by_environment)
      .filter(([name, amount]) => predicate(name) && amount > 0)
      .sort(([left], [right]) => left.localeCompare(right))[0]?.[0];
    if (environment) {
      return { environment, period: period.period_index };
    }
  }
  return null;
}

export function buildRolloutSignals(
  snapshot: Pick<BomSnapshot, "monthly_series" | "steady_state_period" | "ramp_deferred_amount">,
  environments: DeploymentEnvironmentInput[] = [],
): BomRolloutSignals {
  const activation = environments
    .flatMap((environment) => environment.phases.flatMap((phase) => {
      const firstMonthlyPeriod = phase.interpolation === "monthly"
        ? phase.monthly_quantities.find((period) => period.quantity > 0)?.period_index
        : null;
      const isActive = (
        (firstMonthlyPeriod !== undefined && firstMonthlyPeriod !== null)
        || (phase.start_quantity ?? 0) > 0
        || phase.start_multiplier > 0
      );
      return isActive ? [{ environment: environment.name, period: firstMonthlyPeriod ?? phase.start_month }] : [];
    }))
    .sort((left, right) => left.period - right.period || left.environment.localeCompare(right.environment));
  return {
    firstEnvironment: activation[0] ?? firstEnvironmentActivation(snapshot),
    productionStart: activation.find((item) => looksLikeProduction(item.environment))
      ?? firstEnvironmentActivation(snapshot, looksLikeProduction),
    stabilizationPeriod: snapshot.steady_state_period,
    timingEffect: snapshot.ramp_deferred_amount,
  };
}

export function buildComparisonPeriodData(
  comparison: Pick<BomComparison, "period_deltas">,
): Array<{ period: string; delta: number }> {
  return Object.entries(comparison.period_deltas)
    .map(([period, delta]) => ({ period: `M${period}`, delta }))
    .sort((left, right) => Number(left.period.slice(1)) - Number(right.period.slice(1)));
}

export function activeComparisonCategories(
  comparison: Pick<BomComparison, "driver_categories">,
): string[] {
  return Object.entries(comparison.driver_categories)
    .filter(([, active]) => active)
    .map(([category]) => category.replaceAll("_", " "));
}
