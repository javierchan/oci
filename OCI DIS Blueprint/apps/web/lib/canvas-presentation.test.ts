import { describe, expect, it } from "vitest";

import {
  canvasNodeConstraint,
  canvasNodeMetrics,
  canvasServiceConstraint,
  formatCanvasPayload,
} from "./canvas-presentation";
import type { CanvasServiceProfile, ServiceLimit } from "./types";
import type { TechnicalDemandNode } from "./types";

function limit(limitKey: string, value: number, unit: string): ServiceLimit {
  return {
    id: limitKey,
    limit_key: limitKey,
    label: limitKey,
    scope: "service",
    limit_type: "technical",
    constraint_kind: "maximum",
    enforcement: "documented",
    applicability: {},
    value,
    unit,
    default_value: null,
    can_request_increase: false,
    source_url: "https://docs.oracle.com/",
    source_retrieved_at: "2026-07-23T00:00:00Z",
    confidence: 1,
    notes: null,
    is_active: true,
    updated_at: "2026-07-23T00:00:00Z",
  };
}

function profile(
  serviceId: string,
  definitions: Record<string, ServiceLimit>,
): CanvasServiceProfile {
  return {
    id: serviceId,
    service_id: serviceId,
    name: serviceId,
    category: "integration",
    sla_uptime_pct: 99.9,
    pricing_model: "governed",
    limits: {},
    limit_definitions: definitions,
    summary: null,
    architecture_role: null,
  };
}

describe("canvas presentation", () => {
  it("describes the OIC billing unit without presenting it as a payload ceiling", () => {
    const oic = profile("OIC3", {
      billing_threshold_kb: limit("billing_threshold_kb", 50, "KB"),
    });

    expect(canvasServiceConstraint(oic)).toBe("50 KB billing message");
    expect(canvasServiceConstraint(oic)).not.toContain("Max");
    expect(canvasNodeConstraint(oic, 831.9)).toBe("17 × 50 KB billing units");
  });

  it("combines governed API Gateway request and Functions-backend constraints", () => {
    const gateway = profile("API_GATEWAY", {
      max_request_body_kb: limit("max_request_body_kb", 20 * 1024, "KB"),
      max_function_backend_body_kb: limit(
        "max_function_backend_body_kb",
        6 * 1024,
        "KB",
      ),
    });

    expect(canvasServiceConstraint(gateway)).toBe(
      "20 MB request · 6 MB Functions",
    );
  });

  it("keeps payload, cadence, SLA, and rule as separate readable metrics", () => {
    const gateway = profile("API_GATEWAY", {
      max_request_body_kb: limit("max_request_body_kb", 20 * 1024, "KB"),
      max_function_backend_body_kb: limit(
        "max_function_backend_body_kb",
        6 * 1024,
        "KB",
      ),
    });

    const demand: TechnicalDemandNode = {
      instance_id: "gateway-1",
      service_id: "API_GATEWAY",
      tool_key: "OCI API Gateway",
      label: "API Gateway",
      route_indexes: [0],
      input_payload_kb: 352,
      output_payload_kb: 4,
      logical_payload_kb: 352,
      input_messages_per_execution: 1,
      output_messages_per_execution: 1,
      fragment_count: 1,
      fan_out_targets: 1,
      payload_strategy: "object_storage_pointer",
      offloaded_payload_kb: 352,
      status: "resolved",
      blockers: [],
      source_urls: ["https://docs.oracle.com/"],
      metrics: [
        {
          mapping_id: "mapping-1",
          part_number: "B92072",
          metric_key: "api_gateway_call_millions",
          quantity: 0.72,
          unit: "million API calls",
          status: "resolved",
          adapter: "api_gateway",
          messages_per_month: 720000,
          operations_per_month: { request: 720000 },
          billing_units_per_month: 0.72,
          rule: "Requests / 1,000,000",
          source_url: "https://docs.oracle.com/",
          warnings: [],
          blockers: [],
        },
      ],
    };

    expect(
      canvasNodeMetrics(gateway, "Real Time", "p95 under 5 seconds", demand),
    ).toEqual({
      inputPayload: "352 KB",
      outputPayload: "4 KB",
      messageFlow: "1 / execution",
      monthlyUsage: "0.72 million API calls",
      monthlyUsageDetail: "0.72 million API calls",
      cadence: "Real Time",
      sla: "p95 under 5 seconds",
      constraint: "Requests / 1,000,000",
      status: "resolved",
    });
    expect(formatCanvasPayload(null)).toBe("Not captured");
  });

  it("explains when a draft must be saved before usage can be recalculated", () => {
    expect(
      canvasNodeMetrics(
        null,
        "Every hour",
        null,
        null,
        "Save the route to recalculate governed usage.",
      ),
    ).toEqual({
      inputPayload: "Not calculated",
      outputPayload: "Not calculated",
      messageFlow: "Not calculated",
      monthlyUsage: "Not calculated",
      monthlyUsageDetail: "Save the route to recalculate governed usage.",
      cadence: "Every hour",
      sla: "Not published",
      constraint: "Save the route to recalculate governed usage.",
      status: "not_calculated",
    });
  });
});
