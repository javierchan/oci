/* Presentation helpers for readable, evidence-backed Integration Canvas node metrics. */

import type { CanvasServiceProfile, ServiceLimit } from "./types";

export type CanvasNodeMetrics = {
  payload: string;
  cadence: string;
  sla: string;
  constraint: string;
};

function numericLimit(
  profile: CanvasServiceProfile,
  key: string,
): (ServiceLimit & { value: number }) | null {
  const definition = profile.limit_definitions[key];
  return definition && typeof definition.value === "number"
    ? (definition as ServiceLimit & { value: number })
    : null;
}

function formatQuantity(value: number, unit: string | null): string {
  if (unit?.toUpperCase() === "KB" && value >= 1024) {
    const megabytes = value / 1024;
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: megabytes >= 10 ? 0 : 1,
    }).format(megabytes)} MB`;
  }
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)}${unit ? ` ${unit}` : ""}`;
}

function formattedLimit(
  profile: CanvasServiceProfile,
  key: string,
  fallback: string,
): string {
  const definition = numericLimit(profile, key);
  return definition ? formatQuantity(definition.value as number, definition.unit) : fallback;
}

export function canvasServiceConstraint(profile: CanvasServiceProfile): string {
  switch (profile.service_id) {
    case "OIC3":
      return `${formattedLimit(profile, "billing_threshold_kb", "50 KB")} billing message`;
    case "API_GATEWAY": {
      const request = formattedLimit(profile, "max_request_body_kb", "20 MB");
      const functions = formattedLimit(profile, "max_function_backend_body_kb", "6 MB");
      return `${request} request · ${functions} Functions`;
    }
    case "STREAMING":
      return `${formattedLimit(profile, "max_message_size_kb", "1 MB")} message`;
    case "QUEUE":
      return `${formattedLimit(profile, "max_message_size_kb", "256 KB")} message`;
    case "FUNCTIONS":
      return `${formattedLimit(profile, "max_request_body_kb", "6 MB")} body`;
    default:
      return profile.pricing_model?.trim() || "Open service profile";
  }
}

export function canvasNodeConstraint(
  profile: CanvasServiceProfile,
  payloadKb: number | null,
): string {
  if (profile.service_id === "OIC3" && payloadKb !== null && Number.isFinite(payloadKb)) {
    const billingThreshold = numericLimit(profile, "billing_threshold_kb");
    if (billingThreshold && billingThreshold.value > 0) {
      const billingUnits = Math.max(1, Math.ceil(payloadKb / billingThreshold.value));
      return `${billingUnits} × ${formatQuantity(
        billingThreshold.value,
        billingThreshold.unit,
      )} billing units`;
    }
  }
  return canvasServiceConstraint(profile);
}

export function formatCanvasPayload(payloadKb: number | null): string {
  if (payloadKb === null || !Number.isFinite(payloadKb)) {
    return "Not captured";
  }
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: payloadKb >= 100 ? 0 : 1,
  }).format(payloadKb)} KB`;
}

export function formatCanvasSla(
  profile: CanvasServiceProfile | null,
  targetLatencySla: string | null,
): string {
  if (targetLatencySla?.trim()) {
    return targetLatencySla.trim();
  }
  if (profile?.sla_uptime_pct === null || profile?.sla_uptime_pct === undefined) {
    return "Not published";
  }
  return `${profile.sla_uptime_pct.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}% uptime`;
}

export function canvasNodeMetrics(
  profile: CanvasServiceProfile | null,
  payloadKb: number | null,
  cadence: string | null,
  targetLatencySla: string | null,
): CanvasNodeMetrics {
  return {
    payload: formatCanvasPayload(payloadKb),
    cadence: cadence?.trim() || "Not captured",
    sla: formatCanvasSla(profile, targetLatencySla),
    constraint: profile ? canvasNodeConstraint(profile, payloadKb) : "Open service profile",
  };
}
