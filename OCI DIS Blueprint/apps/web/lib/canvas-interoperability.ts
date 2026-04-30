"use client";

/* Oracle-backed interoperability validation for the integration design canvas. */

import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  type CanvasEdge,
  type CanvasNode,
} from "./canvas-governance";
import type { ServiceCapabilityProfile } from "./types";

export type CanvasFindingSeverity = "blocker" | "warning" | "advisory";

export type CanvasInteroperabilityFinding = {
  id: string;
  severity: CanvasFindingSeverity;
  title: string;
  detail: string;
  serviceIds: string[];
};

export type CanvasInteroperabilityRoute = {
  nodeIds: string[];
  toolKeys: string[];
  serviceIds: string[];
};

export type CanvasInteroperabilityReport = {
  blockers: CanvasInteroperabilityFinding[];
  warnings: CanvasInteroperabilityFinding[];
  advisories: CanvasInteroperabilityFinding[];
  routes: CanvasInteroperabilityRoute[];
};

export type CanvasInteroperabilityArgs = {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  overlayToolKeys: string[];
  serviceProfilesById: Map<string, ServiceCapabilityProfile>;
  payloadKb: number | null;
  triggerType: string | null;
  isRealTime: boolean | null;
  sourceTechnology: string | null;
  destinationTechnology: string | null;
  integrationType: string | null;
};

export const TOOL_TO_SERVICE_ID: Record<string, string> = {
  "OIC Gen3": "OIC3",
  "OCI API Gateway": "API_GATEWAY",
  "OCI Streaming": "STREAMING",
  "OCI Queue": "QUEUE",
  "OCI Functions": "FUNCTIONS",
  "Oracle Functions": "FUNCTIONS",
  "OCI Data Integration": "DATA_INTEGRATION",
  "Oracle ORDS": "ORDS",
  "Oracle DB": "ORDS",
  "OCI APM": "OBSERVABILITY",
  "Oracle GoldenGate": "GOLDENGATE",
  "OCI Connector Hub": "CONNECTOR_HUB",
  "OCI IAM": "IAM",
  "OCI Object Storage": "OBJECT_STORAGE",
  SFTP: "OBJECT_STORAGE",
};

const CONNECTOR_HUB_ALLOWED_SOURCES = new Set<string>(["QUEUE", "STREAMING"]);
const CONNECTOR_HUB_ALLOWED_TARGETS = new Set<string>([
  "FUNCTIONS",
  "STREAMING",
  "OBJECT_STORAGE",
]);
const API_GATEWAY_ALLOWED_BACKENDS = new Set<string>(["FUNCTIONS", "OIC3", "ORDS"]);

function normalizeText(value: string | null | undefined): string {
  return value?.trim().toUpperCase() ?? "";
}

function includesAny(value: string | null | undefined, keywords: string[]): boolean {
  const normalized = normalizeText(value);
  return keywords.some((keyword) => normalized.includes(keyword));
}

function routeKey(route: CanvasInteroperabilityRoute): string {
  return route.nodeIds.join("->");
}

function serviceLimitNumber(limits: Record<string, unknown>, key: string): number | null {
  const value = limits[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function formatCanvasLimit(valueKb: number): string {
  if (valueKb >= 1024 && valueKb % 1024 === 0) {
    return `${valueKb / 1024} MB`;
  }
  if (valueKb >= 1024) {
    return `${(valueKb / 1024).toFixed(1)} MB`;
  }
  return `${valueKb} KB`;
}

export function resolveCanvasServiceId(toolKey: string): string | null {
  return TOOL_TO_SERVICE_ID[toolKey] ?? null;
}

function buildRoutes(nodes: CanvasNode[], edges: CanvasEdge[]): CanvasInteroperabilityRoute[] {
  const nodeById = new Map<string, CanvasNode>(nodes.map((node) => [node.instanceId, node]));
  const adjacency = new Map<string, string[]>();

  for (const edge of edges) {
    const next = adjacency.get(edge.sourceInstanceId) ?? [];
    next.push(edge.targetInstanceId);
    adjacency.set(edge.sourceInstanceId, next);
  }

  const rawRoutes: string[][] = [];
  const maxDepth = nodes.length + 2;

  function walk(currentId: string, path: string[]): void {
    if (path.length > maxDepth) {
      return;
    }
    if (currentId === DESTINATION_NODE_ID) {
      rawRoutes.push(path);
      return;
    }

    for (const nextId of adjacency.get(currentId) ?? []) {
      if (path.includes(nextId)) {
        continue;
      }
      walk(nextId, [...path, nextId]);
    }
  }

  walk(SOURCE_NODE_ID, [SOURCE_NODE_ID]);

  const deduped = new Map<string, CanvasInteroperabilityRoute>();
  for (const path of rawRoutes) {
    const toolNodes = path
      .slice(1, -1)
      .map((nodeId) => nodeById.get(nodeId))
      .filter((node): node is CanvasNode => Boolean(node));
    const route: CanvasInteroperabilityRoute = {
      nodeIds: path,
      toolKeys: toolNodes.map((node) => node.toolKey),
      serviceIds: toolNodes
        .map((node) => resolveCanvasServiceId(node.toolKey))
        .filter((serviceId): serviceId is string => Boolean(serviceId)),
    };
    deduped.set(routeKey(route), route);
  }

  return Array.from(deduped.values());
}

function pushUniqueFinding(
  target: CanvasInteroperabilityFinding[],
  finding: CanvasInteroperabilityFinding,
): void {
  if (!target.some((entry) => entry.id === finding.id)) {
    target.push(finding);
  }
}

function collectPayloadBlockers(
  payloadKb: number | null,
  toolKeys: Set<string>,
  serviceProfilesById: Map<string, ServiceCapabilityProfile>,
): CanvasInteroperabilityFinding[] {
  if (payloadKb === null || payloadKb === undefined) {
    return [];
  }

  const blockers: CanvasInteroperabilityFinding[] = [];
  const checks = [
    {
      findingId: "oic-payload-limit",
      toolKeys: ["OIC Gen3"],
      serviceId: "OIC3",
      limitKey: "max_message_size_kb",
      title: "OIC payload exceeds the documented message limit",
      detail: "Route the payload through object storage or reduce the synchronous message size before using OIC Gen3 on the active path.",
    },
    {
      findingId: "functions-payload-limit",
      toolKeys: ["OCI Functions", "Oracle Functions"],
      serviceId: "FUNCTIONS",
      limitKey: "max_invoke_body_kb",
      title: "Functions payload exceeds the documented invoke limit",
      detail: "Oracle Functions cannot accept this payload body size on the active path. Use OIC or externalize the payload before invocation.",
    },
    {
      findingId: "gateway-payload-limit",
      toolKeys: ["OCI API Gateway"],
      serviceId: "API_GATEWAY",
      limitKey: "max_request_body_kb",
      title: "API Gateway payload exceeds the documented request-body limit",
      detail: "The gateway edge cannot carry this request size. Reduce the body or move the payload off-band before API Gateway.",
    },
    {
      findingId: "queue-payload-limit",
      toolKeys: ["OCI Queue"],
      serviceId: "QUEUE",
      limitKey: "max_message_size_kb",
      title: "Queue payload exceeds the documented message limit",
      detail: "OCI Queue should carry a lightweight reference, not the full payload. Externalize the document and enqueue a token or pointer.",
    },
    {
      findingId: "streaming-payload-limit",
      toolKeys: ["OCI Streaming"],
      serviceId: "STREAMING",
      limitKey: "max_message_size_kb",
      title: "Streaming payload exceeds the documented message limit",
      detail: "OCI Streaming enforces a 1 MB message ceiling. Store the large document elsewhere and publish only the event reference.",
    },
  ];

  for (const check of checks) {
    const profile = serviceProfilesById.get(check.serviceId);
    const limitKb = profile ? serviceLimitNumber(profile.limits, check.limitKey) : null;
    if (limitKb === null || !check.toolKeys.some((toolKey) => toolKeys.has(toolKey)) || payloadKb <= limitKb) {
      continue;
    }

    blockers.push({
      id: check.findingId,
      severity: "blocker",
      title: check.title,
      detail: `${check.detail} Payload ${formatCanvasLimit(payloadKb)} exceeds ${formatCanvasLimit(limitKb)}.`,
      serviceIds: [check.serviceId],
    });
  }

  return blockers;
}

function activeNodeIdSet(routes: CanvasInteroperabilityRoute[]): Set<string> {
  return new Set(routes.flatMap((route) => route.nodeIds));
}

function collectConnectorHubBlockers(
  routes: CanvasInteroperabilityRoute[],
  edges: CanvasEdge[],
  overlayToolKeys: Set<string>,
): CanvasInteroperabilityFinding[] {
  const blockers: CanvasInteroperabilityFinding[] = [];
  const activeNodeIds = activeNodeIdSet(routes);

  for (const [routeIndex, route] of routes.entries()) {
    const routeToolKeys = route.toolKeys;
    const routeServiceIds = routeToolKeys
      .map((toolKey) => resolveCanvasServiceId(toolKey))
      .filter((serviceId): serviceId is string => Boolean(serviceId));

    for (let index = 0; index < routeServiceIds.length; index += 1) {
      const serviceId = routeServiceIds[index];
      if (serviceId !== "CONNECTOR_HUB") {
        continue;
      }

      const connectorNodeId = route.nodeIds[index + 1];
      const previousToolKey = routeToolKeys[index - 1] ?? null;
      const nextToolKey = routeToolKeys[index + 1] ?? null;
      const previousServiceId = previousToolKey ? resolveCanvasServiceId(previousToolKey) : null;
      const nextServiceId = nextToolKey ? resolveCanvasServiceId(nextToolKey) : null;

      if (!previousServiceId || !CONNECTOR_HUB_ALLOWED_SOURCES.has(previousServiceId)) {
        pushUniqueFinding(blockers, {
          id: `connector-hub-source-${routeIndex}`,
          severity: "blocker",
          title: "Connector Hub source is not Oracle-supported for this route",
          detail:
            "OCI Connector Hub is documented for OCI-native service sources such as Queue or Streaming. Model an OCI event source before Connector Hub instead of connecting it directly to the external system or an unsupported service.",
          serviceIds: ["CONNECTOR_HUB", ...(previousServiceId ? [previousServiceId] : [])],
        });
      }

      if (!nextServiceId || !CONNECTOR_HUB_ALLOWED_TARGETS.has(nextServiceId)) {
        pushUniqueFinding(blockers, {
          id: `connector-hub-target-${routeIndex}`,
          severity: "blocker",
          title: "Connector Hub target is not Oracle-supported for this route",
          detail:
            "Connector Hub is documented as a source -> optional task -> target flow. On the modeled palette it should hand off to OCI Functions, OCI Streaming, or OCI Object Storage.",
          serviceIds: ["CONNECTOR_HUB", ...(nextServiceId ? [nextServiceId] : [])],
        });
      }

      const inboundCount = edges.filter(
        (edge) =>
          edge.targetInstanceId === connectorNodeId &&
          activeNodeIds.has(edge.sourceInstanceId) &&
          activeNodeIds.has(edge.targetInstanceId),
      ).length;
      const outboundCount = edges.filter(
        (edge) =>
          edge.sourceInstanceId === connectorNodeId &&
          activeNodeIds.has(edge.sourceInstanceId) &&
          activeNodeIds.has(edge.targetInstanceId),
      ).length;

      if (inboundCount > 1 || outboundCount > 1) {
        pushUniqueFinding(blockers, {
          id: `connector-hub-parallel-${routeIndex}`,
          severity: "blocker",
          title: "Connector Hub is modeled as a parallel fan-out",
          detail:
            "Oracle documents Connector Hub as a sequential source -> optional task -> target service. Parallel branches from the same Connector Hub node should be modeled with another service pattern.",
          serviceIds: ["CONNECTOR_HUB"],
        });
      }

      if (overlayToolKeys.has(previousToolKey ?? "") || overlayToolKeys.has(nextToolKey ?? "")) {
        pushUniqueFinding(blockers, {
          id: `connector-hub-overlay-${routeIndex}`,
          severity: "blocker",
          title: "Connector Hub is chained directly to an overlay-only node",
          detail:
            "Connector Hub should participate in the core data path, not chain directly through overlay-only controls. Add a supported core service before or after the connector.",
          serviceIds: ["CONNECTOR_HUB"],
        });
      }
    }
  }

  return blockers;
}

function collectGatewayRules(
  routes: CanvasInteroperabilityRoute[],
  triggerType: string | null,
): CanvasInteroperabilityFinding[] {
  const findings: CanvasInteroperabilityFinding[] = [];
  const isSoapTrigger = includesAny(triggerType, ["SOAP"]);

  for (const [routeIndex, route] of routes.entries()) {
    const routeServiceIds = route.toolKeys.map((toolKey) => resolveCanvasServiceId(toolKey));
    for (let index = 0; index < routeServiceIds.length; index += 1) {
      const serviceId = routeServiceIds[index];
      if (serviceId !== "API_GATEWAY") {
        continue;
      }

      const nextServiceId = routeServiceIds[index + 1] ?? null;

      if (isSoapTrigger) {
        pushUniqueFinding(findings, {
          id: `gateway-soap-${routeIndex}`,
          severity: "blocker",
          title: "API Gateway is modeled on a SOAP-triggered route",
          detail:
            "The Oracle Integration API Gateway front-door is documented for REST-triggered integrations. Keep SOAP routes off this gateway pattern or remodel the entry path as REST.",
          serviceIds: ["API_GATEWAY", "OIC3"],
        });
      }

      if (nextServiceId && !API_GATEWAY_ALLOWED_BACKENDS.has(nextServiceId)) {
        pushUniqueFinding(findings, {
          id: `gateway-backend-${routeIndex}`,
          severity: "blocker",
          title: "API Gateway points to a backend that is not supported by this modeled route",
          detail:
            "For the modeled OCI stack, API Gateway should front OIC, ORDS, or Functions. Routeing gateway traffic directly into Queue, Streaming, or batch services is not a supported edge pattern.",
          serviceIds: ["API_GATEWAY", nextServiceId],
        });
      }
    }
  }

  return findings;
}

function collectOperationalWarnings(
  routes: CanvasInteroperabilityRoute[],
  args: Pick<
    CanvasInteroperabilityArgs,
    "triggerType" | "isRealTime" | "sourceTechnology" | "destinationTechnology" | "integrationType"
  >,
): CanvasInteroperabilityFinding[] {
  const warnings: CanvasInteroperabilityFinding[] = [];
  const isRestLike =
    includesAny(args.triggerType, ["REST"]) ||
    includesAny(args.integrationType, ["REST"]) ||
    includesAny(args.sourceTechnology, ["REST"]) ||
    includesAny(args.destinationTechnology, ["REST"]);
  const isEventLike =
    includesAny(args.triggerType, ["EVENT"]) ||
    includesAny(args.integrationType, ["EVENT", "KAFKA", "STREAM"]);
  const isSyncLike = Boolean(args.isRealTime) || isRestLike || includesAny(args.triggerType, ["SOAP"]);

  for (const route of routes) {
    const routeServices = new Set(route.serviceIds);

    if (
      routeServices.has("DATA_INTEGRATION") &&
      (Boolean(args.isRealTime) || isRestLike || isEventLike)
    ) {
      pushUniqueFinding(warnings, {
        id: "data-integration-low-latency-warning",
        severity: "warning",
        title: "Data Integration is on a low-latency path",
        detail:
          "OCI Data Integration is a batch or micro-batch service and Oracle documents that pipelines are not designed for low-latency operational mediation. Keep it on scheduled data movement instead of the synchronous or event critical path.",
        serviceIds: ["DATA_INTEGRATION"],
      });
    }

    if (routeServices.has("FUNCTIONS") && isSyncLike) {
      pushUniqueFinding(warnings, {
        id: "functions-sync-warning",
        severity: "warning",
        title: "Functions is on a synchronous critical path",
        detail:
          "Oracle Functions works well for lightweight compute, but this route behaves like a synchronous user or API path. Review cold-start, error handling, and the lower service SLA before treating it as the primary critical-path hop.",
        serviceIds: ["FUNCTIONS"],
      });
    }

    if (routeServices.has("OIC3") && routeServices.has("STREAMING") && isEventLike) {
      pushUniqueFinding(warnings, {
        id: "oic-streaming-connectivity-warning",
        severity: "warning",
        title: "OIC + Streaming route still needs deployment-context validation",
        detail:
          "Oracle supports Streaming with OIC through the Streaming or Kafka adapter, but the exact inbound or outbound pattern depends on connectivity mode and deployment context. Validate connectivity-agent or private-endpoint details during design review.",
        serviceIds: ["OIC3", "STREAMING"],
      });
    }
  }

  return warnings;
}

function collectAdvisories(
  routes: CanvasInteroperabilityRoute[],
  args: Pick<
    CanvasInteroperabilityArgs,
    "triggerType" | "isRealTime" | "sourceTechnology" | "destinationTechnology" | "integrationType"
  >,
): CanvasInteroperabilityFinding[] {
  const advisories: CanvasInteroperabilityFinding[] = [];
  const isRestLike =
    includesAny(args.triggerType, ["REST"]) ||
    includesAny(args.integrationType, ["REST"]) ||
    includesAny(args.sourceTechnology, ["REST"]) ||
    includesAny(args.destinationTechnology, ["REST"]);
  const routeServices = new Set(routes.flatMap((route) => route.serviceIds));

  if (isRestLike && routeServices.has("ORDS") && !routeServices.has("API_GATEWAY")) {
    advisories.push({
      id: "ords-gateway-advisory",
      severity: "advisory",
      title: "Consider fronting ORDS with API Gateway",
      detail:
        "ORDS is a solid database REST facade, but Oracle architecture guidance is stronger when public REST traffic is fronted by API Gateway for rate limiting, token validation, and edge policy control.",
      serviceIds: ["ORDS", "API_GATEWAY"],
    });
  }

  if (
    isRestLike &&
    !routeServices.has("API_GATEWAY") &&
    (routeServices.has("OIC3") || routeServices.has("FUNCTIONS") || routeServices.has("ORDS"))
  ) {
    advisories.push({
      id: "rest-route-gateway-advisory",
      severity: "advisory",
      title: "Public REST edge is missing API Gateway",
      detail:
        "If this route is exposed beyond the tenancy boundary, consider API Gateway for JWT or OIDC validation, mTLS, throttling, and centralized edge observability.",
      serviceIds: ["API_GATEWAY"],
    });
  }

  return advisories;
}

export function evaluateCanvasInteroperability(
  args: CanvasInteroperabilityArgs,
): CanvasInteroperabilityReport {
  const overlayToolSet = new Set(args.overlayToolKeys);
  const routes = buildRoutes(args.nodes, args.edges);
  const activeToolKeys = new Set(routes.flatMap((route) => route.toolKeys));

  const blockers = [
    ...collectPayloadBlockers(args.payloadKb, activeToolKeys, args.serviceProfilesById),
    ...collectConnectorHubBlockers(routes, args.edges, overlayToolSet),
    ...collectGatewayRules(routes, args.triggerType).filter(
      (finding): finding is CanvasInteroperabilityFinding => finding.severity === "blocker",
    ),
  ];
  const warnings = [
    ...collectGatewayRules(routes, args.triggerType).filter(
      (finding): finding is CanvasInteroperabilityFinding => finding.severity === "warning",
    ),
    ...collectOperationalWarnings(routes, args),
  ];
  const advisories = collectAdvisories(routes, args);

  return {
    blockers,
    warnings,
    advisories,
    routes,
  };
}
