import { describe, expect, it } from "vitest";

import {
  canvasNodeConstraint,
  canvasNodeMetrics,
  canvasServiceConstraint,
  formatCanvasPayload,
} from "./canvas-presentation";
import type { CanvasServiceProfile, ServiceLimit } from "./types";

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

    expect(canvasNodeMetrics(gateway, 352, "Real Time", "p95 under 5 seconds")).toEqual({
      payload: "352 KB",
      cadence: "Real Time",
      sla: "p95 under 5 seconds",
      constraint: "20 MB request · 6 MB Functions",
    });
    expect(formatCanvasPayload(null)).toBe("Not captured");
  });
});
