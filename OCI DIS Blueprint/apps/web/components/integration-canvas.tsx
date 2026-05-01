"use client";

/* SVG-based integration flow canvas with governed tool semantics and pattern suggestions. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeftRight,
  Building2,
  Code2,
  Database,
  Maximize2,
  Move,
  Package,
  RotateCcw,
  Settings2,
  Trash2,
  Zap,
  ZoomIn,
} from "lucide-react";

import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { api } from "@/lib/api";
import { displayUiValue } from "@/lib/format";
import {
  evaluateCanvasInteroperability,
  resolveCanvasServiceId,
  type CanvasFindingSeverity,
  type CanvasInteroperabilityFinding,
} from "@/lib/canvas-interoperability";
import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  deriveCanvasSemantics,
  parseCanvasState,
  serializeCanvasState,
  type CanvasEndpointId,
  type CanvasEndpointPositions,
  type CanvasEdge,
  type CanvasNode,
} from "@/lib/canvas-governance";
import type {
  CanvasCombination,
  DictionaryOption,
  OICEstimateResponse,
  PatternDefinition,
  ServiceCapabilityProfile,
} from "@/lib/types";

type PatternCategory = string;
type HandlePosition = "top" | "right" | "bottom" | "left";
type SelectedElement =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | null;

const MIN_CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 560;
const MIN_SCALE = 0.5;
const MIN_READABLE_AUTO_SCALE = 0.68;
const MAX_SCALE = 2;
const ROUTE_NODE_GAP = 42;
const TOOL_NODE_WIDTH = 190;
const TOOL_NODE_HEIGHT = 142;
const SYSTEM_NODE_WIDTH = 236;
const SYSTEM_NODE_HEIGHT = 104;
const HANDLE_RADIUS = 6;

type FixedNodeMeta = {
  subtitle: string | null;
  fixed: boolean;
};

type CanvasViewport = {
  x: number;
  y: number;
  scale: number;
};

type CanvasBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type FlowNode = CanvasNode & FixedNodeMeta;

type ToolDefinition = {
  accent: string;
  surface: string;
  icon: ReactNode;
};

type ToolKind = "oic" | "gateway" | "streaming" | "functions" | "storage" | "db";

type IntegrationCanvasProps = {
  projectId: string;
  sourceSystem: string;
  sourceTechnology: string | null;
  destinationSystem: string | null;
  destinationTechnology: string | null;
  selectedPattern: string | null;
  patternDetail: PatternDefinition | null;
  serviceProfiles: ServiceCapabilityProfile[];
  coreTools: string[];
  toolOptions: DictionaryOption[];
  overlayOptions: DictionaryOption[];
  combinations: CanvasCombination[];
  patterns: PatternDefinition[];
  payloadKb: number | null;
  frequency: string | null;
  patternCategory: PatternCategory | null;
  value: string | null;
  onChange: (_nextValue: string) => void;
  onToolsChange?: (_toolKeys: string[]) => void;
  onConnectionValidityChange?: (_isValid: boolean) => void;
  onBlockingIssuesChange?: (_hasBlockingIssues: boolean) => void;
  triggerType?: string | null;
  isRealTime?: boolean | null;
  integrationType?: string | null;
};

const TOOL_KINDS: Record<string, ToolKind> = {
  "OIC Gen3": "oic",
  "OCI API Gateway": "gateway",
  "OCI Streaming": "streaming",
  "OCI Queue": "streaming",
  "OCI Functions": "functions",
  "OCI Data Integration": "oic",
  "Oracle Functions": "functions",
  "Data Integrator": "oic",
  "Oracle GoldenGate": "db",
  "Oracle ORDS": "db",
  ATP: "db",
  "Oracle DB": "db",
  SFTP: "storage",
  "OCI Object Storage": "storage",
  "OCI APM": "oic",
};

const TOOL_KIND_STYLES: Record<ToolKind, ToolDefinition> = {
  oic: {
    accent: "var(--canvas-oic-border)",
    surface: "var(--canvas-oic-bg)",
    icon: <Settings2 className="h-5 w-5" />,
  },
  gateway: {
    accent: "var(--canvas-gw-border)",
    surface: "var(--canvas-gw-bg)",
    icon: <ArrowLeftRight className="h-5 w-5" />,
  },
  streaming: {
    accent: "var(--canvas-stream-border)",
    surface: "var(--canvas-stream-bg)",
    icon: <Zap className="h-5 w-5" />,
  },
  functions: {
    accent: "var(--canvas-fn-border)",
    surface: "var(--canvas-fn-bg)",
    icon: <Code2 className="h-5 w-5" />,
  },
  storage: {
    accent: "var(--canvas-storage-border)",
    surface: "var(--canvas-storage-bg)",
    icon: <Package className="h-5 w-5" />,
  },
  db: {
    accent: "var(--canvas-db-border)",
    surface: "var(--canvas-db-bg)",
    icon: <Database className="h-5 w-5" />,
  },
};

function parsePatternBullets(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("-"))
    .map((line) => line.replace(/^-+\s*/, ""));
}

function parsePatternSteps(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^\d+\./.test(line))
    .map((line) => line.replace(/^\d+\.\s*/, ""));
}

function parsePatternComponents(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split("|")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function resolveServiceProfile(
  toolKey: string,
  serviceProfilesById: Map<string, ServiceCapabilityProfile>,
): ServiceCapabilityProfile | null {
  const serviceId = resolveCanvasServiceId(toolKey);
  return serviceId ? serviceProfilesById.get(serviceId) ?? null : null;
}

function topConstraintLabel(profile: ServiceCapabilityProfile): string {
  switch (profile.service_id) {
    case "OIC3":
      return "Max msg: 10 MB";
    case "API_GATEWAY":
      return "Body: 20 MB / Fn: 6 MB";
    case "STREAMING":
      return "1 MB msg | 1 MB/s/partition";
    case "QUEUE":
      return "256 KB msg | 10 queues/region";
    case "FUNCTIONS":
      return "6 MB body";
    default:
      return truncateLabel(profile.pricing_model ?? "See service profile", 40);
  }
}

function findingCardClasses(severity: CanvasFindingSeverity): string {
  switch (severity) {
    case "blocker":
      return "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200";
    case "warning":
      return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200";
    case "advisory":
      return "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-200";
  }
}

function findingBadgeClasses(severity: CanvasFindingSeverity): string {
  switch (severity) {
    case "blocker":
      return "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-200";
    case "warning":
      return "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-200";
    case "advisory":
      return "bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-200";
  }
}

function severityLabel(severity: CanvasFindingSeverity): string {
  switch (severity) {
    case "blocker":
      return "Blocker";
    case "warning":
      return "Warning";
    case "advisory":
      return "Advisory";
  }
}

function ValidationFindingGroup({
  title,
  findings,
  severity,
}: {
  title: string;
  findings: CanvasInteroperabilityFinding[];
  severity: CanvasFindingSeverity;
}): JSX.Element | null {
  if (findings.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
        {title}
      </p>
      {findings.map((finding) => (
        <article
          key={finding.id}
          className={`rounded-2xl border p-3 text-xs leading-5 ${findingCardClasses(severity)}`}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="font-semibold">{finding.title}</p>
            <span
              className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${findingBadgeClasses(severity)}`}
            >
              {severityLabel(severity)}
            </span>
          </div>
          <p className="mt-2">{finding.detail}</p>
        </article>
      ))}
    </div>
  );
}

function PatternDetailPanel({ patternDetail }: { patternDetail: PatternDefinition }): JSX.Element {
  const components = parsePatternComponents(patternDetail.oci_components);
  const whenToUse = parsePatternBullets(patternDetail.when_to_use);
  const technicalFlow = parsePatternSteps(patternDetail.technical_flow);

  return (
    <section className="app-card p-6">
      <p className="app-kicker">Pattern Guidance</p>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-2xl font-semibold text-[var(--color-text-primary)]">
            {patternDetail.pattern_id} · {patternDetail.name}
          </h3>
          {patternDetail.description ? (
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">
              {patternDetail.description}
            </p>
          ) : null}
        </div>
        <span className="app-theme-chip">{patternDetail.category}</span>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="app-card-muted p-4">
          <p className="app-label">When to Use</p>
          {whenToUse.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm text-[var(--color-text-secondary)]">
              {whenToUse.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-emerald-600">✅</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">No usage guidance documented.</p>
          )}
        </div>

        <div className="rounded-[1.75rem] border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
          <p className="app-label text-amber-800 dark:text-amber-300">
            Anti-Pattern Guidance
          </p>
          <p className="mt-3 text-sm leading-6">
            <span className="mr-2">⚠</span>
            {patternDetail.when_not_to_use ?? "No anti-pattern guidance documented."}
          </p>
        </div>
      </div>

      <div className="mt-6">
        <p className="app-label">OCI Components</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {components.length > 0 ? (
            components.map((component) => (
              <span key={component} className="app-theme-chip">
                {component}
              </span>
            ))
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">No OCI components documented.</p>
          )}
        </div>
      </div>

      <div className="mt-6">
        <p className="app-label">Technical Flow</p>
        {technicalFlow.length > 0 ? (
          <ol className="mt-3 space-y-2 text-sm text-[var(--color-text-secondary)]">
            {technicalFlow.map((step, index) => (
              <li key={step} className="flex gap-3">
                <span className="font-semibold text-[var(--color-text-primary)]">{index + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-sm text-[var(--color-text-muted)]">No technical flow documented.</p>
        )}
      </div>

      <div className="mt-6">
        <p className="app-label">Business Value</p>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
          {patternDetail.business_value ?? "No business value documented."}
        </p>
      </div>
    </section>
  );
}

const EMPTY_ESTIMATE: OICEstimateResponse = {
  billing_msgs_per_execution: null,
  billing_msgs_per_month: null,
  peak_packs_per_hour: null,
  executions_per_day: null,
  computable: false,
};

function toolDefinition(toolKey: string): ToolDefinition {
  const mappedKind = TOOL_KINDS[toolKey];
  if (mappedKind) {
    return TOOL_KIND_STYLES[mappedKind];
  }

  const palette = [
    { accent: "var(--canvas-system-border)", surface: "var(--canvas-system-bg)", icon: <Building2 className="h-4 w-4" /> },
    { accent: "var(--canvas-oic-border)", surface: "var(--canvas-oic-bg)", icon: <Settings2 className="h-4 w-4" /> },
    { accent: "var(--canvas-stream-border)", surface: "var(--canvas-stream-bg)", icon: <Zap className="h-4 w-4" /> },
    { accent: "var(--canvas-fn-border)", surface: "var(--canvas-fn-bg)", icon: <Code2 className="h-4 w-4" /> },
    { accent: "var(--canvas-gw-border)", surface: "var(--canvas-gw-bg)", icon: <ArrowLeftRight className="h-4 w-4" /> },
    { accent: "var(--canvas-db-border)", surface: "var(--canvas-db-bg)", icon: <Database className="h-4 w-4" /> },
  ];
  const seed = toolKey.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const colors = palette[seed % palette.length];
  return {
    accent: colors.accent,
    surface: colors.surface,
    icon: colors.icon,
  };
}

function createNode(toolKey: string, index: number, x?: number, y?: number): CanvasNode {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    instanceId: crypto.randomUUID(),
    toolKey,
    label: toolKey,
    payloadNote: "",
    x: x ?? 240 + column * (TOOL_NODE_WIDTH + ROUTE_NODE_GAP),
    y: y ?? 72 + row * (TOOL_NODE_HEIGHT + 52),
  };
}

function minimumCanvasWidthForNodeCount(nodeCount: number): number {
  if (nodeCount === 0) {
    return MIN_CANVAS_WIDTH;
  }
  return Math.max(
    MIN_CANVAS_WIDTH,
    SYSTEM_NODE_WIDTH * 2 + TOOL_NODE_WIDTH * nodeCount + ROUTE_NODE_GAP * (nodeCount + 1) + 96,
  );
}

function primaryRouteNodeIds(nodes: CanvasNode[], edges: CanvasEdge[]): string[] {
  const nodeIds = new Set(nodes.map((node) => node.instanceId));
  const ordered: string[] = [];
  const visited = new Set<string>([SOURCE_NODE_ID]);
  let currentId = SOURCE_NODE_ID;

  while (currentId !== DESTINATION_NODE_ID) {
    const nextEdge = edges.find(
      (edge) =>
        edge.sourceInstanceId === currentId &&
        !visited.has(edge.targetInstanceId) &&
        (edge.targetInstanceId === DESTINATION_NODE_ID || nodeIds.has(edge.targetInstanceId)),
    );
    if (!nextEdge) {
      break;
    }
    currentId = nextEdge.targetInstanceId;
    visited.add(currentId);
    if (currentId !== DESTINATION_NODE_ID) {
      ordered.push(currentId);
    }
  }

  return ordered;
}

function arrangeCanvasNodes(nodes: CanvasNode[], edges: CanvasEdge[], canvasWidth: number): CanvasNode[] {
  const routeIds = primaryRouteNodeIds(nodes, edges);
  const routeIdSet = new Set(routeIds);
  const orderedIds = [
    ...routeIds,
    ...nodes
      .filter((node) => !routeIdSet.has(node.instanceId))
      .sort((left, right) => left.x - right.x || left.y - right.y)
      .map((node) => node.instanceId),
  ];
  const positions = new Map<string, { x: number; y: number }>();
  const routeStartX = SYSTEM_NODE_WIDTH + 40 + ROUTE_NODE_GAP;
  const routeStep = TOOL_NODE_WIDTH + ROUTE_NODE_GAP;
  const routeY = CANVAS_HEIGHT / 2 - TOOL_NODE_HEIGHT / 2;

  routeIds.forEach((instanceId, index) => {
    positions.set(instanceId, {
      x: routeStartX + index * routeStep,
      y: routeY,
    });
  });

  const sideNodes = orderedIds.filter((instanceId) => !routeIdSet.has(instanceId));
  sideNodes.forEach((instanceId, index) => {
    const column = index % Math.max(1, Math.floor((canvasWidth - 120) / (TOOL_NODE_WIDTH + ROUTE_NODE_GAP)));
    const row = Math.floor(index / Math.max(1, Math.floor((canvasWidth - 120) / (TOOL_NODE_WIDTH + ROUTE_NODE_GAP))));
    positions.set(instanceId, {
      x: 60 + column * (TOOL_NODE_WIDTH + ROUTE_NODE_GAP),
      y: 28 + row * (TOOL_NODE_HEIGHT + 44),
    });
  });

  return nodes.map((node) => {
    const position = positions.get(node.instanceId);
    if (!position) {
      return node;
    }
    return {
      ...node,
      x: clamp(position.x, 20, canvasWidth - TOOL_NODE_WIDTH - 20),
      y: clamp(position.y, 20, CANVAS_HEIGHT - TOOL_NODE_HEIGHT - 20),
    };
  });
}

function defaultEndpointPositions(canvasWidth: number, routeNodes: CanvasNode[] = []): CanvasEndpointPositions {
  if (routeNodes.length > 0) {
    const routeLeft = Math.min(...routeNodes.map((node) => node.x));
    const routeRight = Math.max(...routeNodes.map((node) => node.x + TOOL_NODE_WIDTH));
    const routeCenterY =
      routeNodes.reduce((sum, node) => sum + node.y + TOOL_NODE_HEIGHT / 2, 0) / routeNodes.length;
    const endpointY = clamp(routeCenterY - SYSTEM_NODE_HEIGHT / 2, 20, CANVAS_HEIGHT - SYSTEM_NODE_HEIGHT - 20);
    return {
      [SOURCE_NODE_ID]: {
        x: clamp(routeLeft - SYSTEM_NODE_WIDTH - ROUTE_NODE_GAP, 40, canvasWidth - SYSTEM_NODE_WIDTH - 40),
        y: endpointY,
      },
      [DESTINATION_NODE_ID]: {
        x: clamp(routeRight + ROUTE_NODE_GAP, 40, canvasWidth - SYSTEM_NODE_WIDTH - 40),
        y: endpointY,
      },
    };
  }

  return {
    [SOURCE_NODE_ID]: {
      x: 40,
      y: CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
    },
    [DESTINATION_NODE_ID]: {
      x: canvasWidth - SYSTEM_NODE_WIDTH - 40,
      y: CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
    },
  };
}

function hasCongestedLayout(
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  canvasWidth: number,
  endpointPositions: CanvasEndpointPositions = {},
): boolean {
  if (nodes.length === 0) {
    return false;
  }
  const routeIds = primaryRouteNodeIds(nodes, edges);
  if (routeIds.length === 0) {
    return false;
  }
  const routeIdSet = new Set(routeIds);
  const routeNodes = nodes.filter((node) => routeIdSet.has(node.instanceId));
  const positions = endpointPositions ?? {};
  const defaultEndpoints = defaultEndpointPositions(canvasWidth, routeNodes);
  const sourceEndpoint = positions[SOURCE_NODE_ID] ?? defaultEndpoints[SOURCE_NODE_ID];
  const destinationEndpoint = positions[DESTINATION_NODE_ID] ?? defaultEndpoints[DESTINATION_NODE_ID];
  const boxes = [
    {
      id: SOURCE_NODE_ID,
      x: sourceEndpoint?.x ?? 40,
      y: sourceEndpoint?.y ?? CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
      width: SYSTEM_NODE_WIDTH,
      height: SYSTEM_NODE_HEIGHT,
    },
    {
      id: DESTINATION_NODE_ID,
      x: destinationEndpoint?.x ?? canvasWidth - SYSTEM_NODE_WIDTH - 40,
      y: destinationEndpoint?.y ?? CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
      width: SYSTEM_NODE_WIDTH,
      height: SYSTEM_NODE_HEIGHT,
    },
    ...nodes
      .filter((node) => routeIdSet.has(node.instanceId))
      .map((node) => ({
        id: node.instanceId,
        x: node.x,
        y: node.y,
        width: TOOL_NODE_WIDTH,
        height: TOOL_NODE_HEIGHT + 38,
      })),
  ];

  return boxes.some((left, leftIndex) =>
    boxes.slice(leftIndex + 1).some((right) => {
      const horizontalGap = Math.max(left.x, right.x) - Math.min(left.x + left.width, right.x + right.width);
      const verticalGap = Math.max(left.y, right.y) - Math.min(left.y + left.height, right.y + right.height);
      return horizontalGap < 24 && verticalGap < 18;
    }),
  );
}

function fixedNodes(
  sourceSystem: string,
  sourceTechnology: string | null,
  destinationSystem: string | null,
  destinationTechnology: string | null,
  canvasWidth: number,
  routeNodes: CanvasNode[] = [],
  endpointPositions: CanvasEndpointPositions = {},
): Record<string, FlowNode> {
  const positions = endpointPositions ?? {};
  const defaultPositions = defaultEndpointPositions(canvasWidth, routeNodes);
  const defaultSourcePosition = defaultPositions[SOURCE_NODE_ID];
  const defaultDestinationPosition = defaultPositions[DESTINATION_NODE_ID];
  return {
    [SOURCE_NODE_ID]: {
      instanceId: SOURCE_NODE_ID,
      toolKey: SOURCE_NODE_ID,
      label: sourceSystem,
      payloadNote: "",
      x: positions[SOURCE_NODE_ID]?.x ?? defaultSourcePosition?.x ?? 40,
      y: positions[SOURCE_NODE_ID]?.y ?? defaultSourcePosition?.y ?? CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
      subtitle: sourceTechnology,
      fixed: true,
    },
    [DESTINATION_NODE_ID]: {
      instanceId: DESTINATION_NODE_ID,
      toolKey: DESTINATION_NODE_ID,
      label: destinationSystem ?? "Unknown Destination",
      payloadNote: "",
      x: positions[DESTINATION_NODE_ID]?.x ?? defaultDestinationPosition?.x ?? canvasWidth - SYSTEM_NODE_WIDTH - 40,
      y: positions[DESTINATION_NODE_ID]?.y ?? defaultDestinationPosition?.y ?? CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
      subtitle: destinationTechnology,
      fixed: true,
    },
  };
}

function mergedNodes(
  sourceSystem: string,
  sourceTechnology: string | null,
  destinationSystem: string | null,
  destinationTechnology: string | null,
  canvasWidth: number,
  nodes: CanvasNode[],
  endpointPositions: CanvasEndpointPositions = {},
): Record<string, FlowNode> {
  return {
    ...fixedNodes(
      sourceSystem,
      sourceTechnology,
      destinationSystem,
      destinationTechnology,
      canvasWidth,
      nodes,
      endpointPositions,
    ),
    ...Object.fromEntries(
      nodes.map((node) => [
        node.instanceId,
        {
          ...node,
          subtitle: node.toolKey,
          fixed: false,
        },
      ]),
    ),
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function screenToWorld(
  point: { x: number; y: number },
  viewport: { x: number; y: number; scale: number },
): { x: number; y: number } {
  return {
    x: (point.x - viewport.x) / viewport.scale,
    y: (point.y - viewport.y) / viewport.scale,
  };
}

function worldToScreen(
  point: { x: number; y: number },
  viewport: { x: number; y: number; scale: number },
): { x: number; y: number } {
  return {
    x: point.x * viewport.scale + viewport.x,
    y: point.y * viewport.scale + viewport.y,
  };
}

function isNodeSelected(selection: SelectedElement, nodeId: string): boolean {
  return selection?.kind === "node" && selection.id === nodeId;
}

function isEdgeSelected(selection: SelectedElement, edgeId: string): boolean {
  return selection?.kind === "edge" && selection.id === edgeId;
}

function nodeWidth(node: FlowNode): number {
  return node.fixed ? SYSTEM_NODE_WIDTH : TOOL_NODE_WIDTH;
}

function nodeHeight(node: FlowNode): number {
  return node.fixed ? SYSTEM_NODE_HEIGHT : TOOL_NODE_HEIGHT;
}

function nodeCenter(node: FlowNode): { x: number; y: number } {
  return { x: node.x + nodeWidth(node) / 2, y: node.y + nodeHeight(node) / 2 };
}

function flowBounds(nodes: FlowNode[]): CanvasBounds | null {
  if (nodes.length === 0) {
    return null;
  }

  const left = Math.min(...nodes.map((node) => node.x));
  const top = Math.min(...nodes.map((node) => node.y));
  const right = Math.max(...nodes.map((node) => node.x + nodeWidth(node)));
  const bottom = Math.max(...nodes.map((node) => node.y + nodeHeight(node)));
  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  };
}

function nodesForViewportFit(
  flowNodes: Record<string, FlowNode>,
  nodes: CanvasNode[],
  edges: CanvasEdge[],
): FlowNode[] {
  const routeIds = primaryRouteNodeIds(nodes, edges);
  const fitIds = new Set<string>([
    SOURCE_NODE_ID,
    DESTINATION_NODE_ID,
    ...(routeIds.length > 0 ? routeIds : nodes.map((node) => node.instanceId)),
  ]);
  return Object.values(flowNodes).filter((node) => fitIds.has(node.instanceId));
}

function isEndpointNodeId(value: string): value is CanvasEndpointId {
  return value === SOURCE_NODE_ID || value === DESTINATION_NODE_ID;
}

function fittedViewport(
  bounds: CanvasBounds,
  visibleWidth: number,
  options: { preferReadableScale?: boolean } = {},
): CanvasViewport {
  const horizontalPadding = 32;
  const verticalPadding = 44;
  const availableWidth = Math.max(320, visibleWidth - horizontalPadding * 2);
  const availableHeight = Math.max(260, CANVAS_HEIGHT - verticalPadding * 2);
  const fitScale = Math.min(1, availableWidth / bounds.width, availableHeight / bounds.height);
  const scale = clamp(
    fitScale,
    options.preferReadableScale ? MIN_READABLE_AUTO_SCALE : MIN_SCALE,
    1,
  );
  const scaledWidth = bounds.width * scale;
  const scaledHeight = bounds.height * scale;
  return {
    x: Math.round(
      scaledWidth > availableWidth
        ? horizontalPadding - bounds.x * scale
        : (visibleWidth - scaledWidth) / 2 - bounds.x * scale,
    ),
    y: Math.round(
      scaledHeight > availableHeight
        ? verticalPadding - bounds.y * scale
        : (CANVAS_HEIGHT - scaledHeight) / 2 - bounds.y * scale,
    ),
    scale,
  };
}

function handleCoordinates(node: FlowNode, handle: HandlePosition): { x: number; y: number } {
  const center = nodeCenter(node);
  switch (handle) {
    case "top":
      return { x: center.x, y: node.y };
    case "right":
      return { x: node.x + nodeWidth(node), y: center.y };
    case "bottom":
      return { x: center.x, y: node.y + nodeHeight(node) };
    case "left":
      return { x: node.x, y: center.y };
  }
}

function truncateLabel(value: string, maxChars: number): string {
  return value.length > maxChars ? `${value.slice(0, Math.max(0, maxChars - 1))}…` : value;
}

function labelFontSize(node: FlowNode): number {
  if (node.fixed) {
    return node.label.length > 34 ? 14.5 : 16;
  }
  if (node.label.length > 34) {
    return 14.25;
  }
  return node.label.length > 22 ? 15 : 16.5;
}

function wrappedTextLines(value: string, maxChars: number, maxLines = 2): string[] {
  const normalizedValue = value.trim();
  const words = normalizedValue.split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return ["—"];
  }

  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
      continue;
    }
    if (current) {
      lines.push(current);
    }
    current = word;
    if (lines.length >= maxLines) {
      break;
    }
  }
  if (current && lines.length < maxLines) {
    lines.push(current);
  }

  const renderedValue = lines.join(" ");
  if (normalizedValue.length > renderedValue.length && lines.length > 0) {
    const lastIndex = lines.length - 1;
    const lastLine = lines[lastIndex];
    lines[lastIndex] =
      lastLine.length >= maxChars
        ? `${lastLine.slice(0, Math.max(1, maxChars - 1))}…`
        : `${lastLine}…`;
  }
  return lines;
}

function renderedLabelLines(node: FlowNode): string[] {
  return wrappedTextLines(node.label, node.fixed ? 17 : 18, 2);
}

function renderedSubtitle(node: FlowNode): string {
  const value = node.fixed ? node.subtitle ?? "System endpoint" : node.toolKey;
  return truncateLabel(value, node.fixed ? 24 : 26);
}

function renderedPayload(node: FlowNode): string {
  if (node.fixed) {
    return "";
  }
  return truncateLabel(node.payloadNote || "No payload note", 42);
}

function dominantHandle(source: FlowNode, target: FlowNode, outgoing: boolean): HandlePosition {
  const sourceCenter = nodeCenter(source);
  const targetCenter = nodeCenter(target);
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    if (outgoing) {
      return dx >= 0 ? "right" : "left";
    }
    return dx >= 0 ? "left" : "right";
  }
  if (outgoing) {
    return dy >= 0 ? "bottom" : "top";
  }
  return dy >= 0 ? "top" : "bottom";
}

function edgePath(source: FlowNode, target: FlowNode): { path: string; midpoint: { x: number; y: number } } {
  const sourceHandle = dominantHandle(source, target, true);
  const targetHandle = dominantHandle(source, target, false);
  const start = handleCoordinates(source, sourceHandle);
  const end = handleCoordinates(target, targetHandle);
  const horizontal = Math.abs(end.x - start.x);
  const vertical = Math.abs(end.y - start.y);
  const offset = Math.max(40, Math.min(120, Math.max(horizontal, vertical) / 2));
  const c1 =
    sourceHandle === "right"
      ? { x: start.x + offset, y: start.y }
      : sourceHandle === "left"
        ? { x: start.x - offset, y: start.y }
        : sourceHandle === "bottom"
          ? { x: start.x, y: start.y + offset }
          : { x: start.x, y: start.y - offset };
  const c2 =
    targetHandle === "left"
      ? { x: end.x - offset, y: end.y }
      : targetHandle === "right"
        ? { x: end.x + offset, y: end.y }
        : targetHandle === "top"
          ? { x: end.x, y: end.y - offset }
          : { x: end.x, y: end.y + offset };

  return {
    path: `M ${start.x} ${start.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${end.x} ${end.y}`,
    midpoint: {
      x: (start.x + end.x) / 2,
      y: (start.y + end.y) / 2,
    },
  };
}

function eventCanvasPoint(
  event: { clientX: number; clientY: number },
  element: SVGSVGElement,
): { x: number; y: number } {
  const rect = element.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

export function IntegrationCanvas({
  projectId,
  sourceSystem,
  sourceTechnology,
  destinationSystem,
  destinationTechnology,
  selectedPattern,
  patternDetail,
  serviceProfiles,
  coreTools,
  toolOptions,
  overlayOptions,
  combinations,
  patterns,
  payloadKb,
  frequency,
  patternCategory,
  value,
  onChange,
  onToolsChange,
  onConnectionValidityChange,
  onBlockingIssuesChange,
  triggerType = null,
  isRealTime = null,
  integrationType = null,
}: IntegrationCanvasProps): JSX.Element {
  const overlayToolKeys = useMemo(
    () => overlayOptions.map((option) => option.value),
    [overlayOptions],
  );
  const serviceProfilesById = useMemo(
    () => new Map(serviceProfiles.map((profile) => [profile.service_id, profile])),
    [serviceProfiles],
  );
  const overlayToolSet = useMemo(() => new Set(overlayToolKeys), [overlayToolKeys]);
  const patternMap = useMemo(
    () => new Map(patterns.map((pattern) => [pattern.pattern_id, pattern])),
    [patterns],
  );
  const initialParsedState = parseCanvasState(value, coreTools);
  const initialSemantics = deriveCanvasSemantics({
    nodes: initialParsedState.nodes,
    edges: initialParsedState.edges,
    overlayToolKeys,
    combinations,
    selectedPattern,
  });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const canvasShellRef = useRef<HTMLDivElement | null>(null);
  const initialStateRef = useRef<{ nodes: CanvasNode[]; edges: CanvasEdge[] }>({
    nodes: initialParsedState.nodes,
    edges: initialParsedState.edges,
  });
  const [nodes, setNodes] = useState<CanvasNode[]>(() => initialStateRef.current.nodes);
  const [edges, setEdges] = useState<CanvasEdge[]>(() => initialStateRef.current.edges);
  const [endpointPositions, setEndpointPositions] = useState<CanvasEndpointPositions>(
    () => initialParsedState.endpointPositions ?? {},
  );
  const [canvasWidth, setCanvasWidth] = useState<number>(MIN_CANVAS_WIDTH);
  const [canvasViewportWidth, setCanvasViewportWidth] = useState<number>(MIN_CANVAS_WIDTH);
  const [viewport, setViewport] = useState<CanvasViewport>({ x: 0, y: 0, scale: 1 });
  const viewportRef = useRef(viewport);
  const viewportUserAdjustedRef = useRef(false);
  const autoFitSignatureRef = useRef<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedElement, setSelectedElement] = useState<SelectedElement>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingPayloadId, setEditingPayloadId] = useState<string | null>(null);
  const [editingEdgeId, setEditingEdgeId] = useState<string | null>(null);
  const [oicEstimate, setOicEstimate] = useState<OICEstimateResponse>(EMPTY_ESTIMATE);
  const [draftValue, setDraftValue] = useState<string>("");
  const [draggingNode, setDraggingNode] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [panning, setPanning] = useState<{ x: number; y: number; viewportX: number; viewportY: number } | null>(null);
  const autoLayoutSignatureRef = useRef<string | null>(null);
  const [connecting, setConnecting] = useState<{
    sourceInstanceId: string;
    startHandle: HandlePosition;
    currentPoint: { x: number; y: number };
  } | null>(null);
  const lastSerializedRef = useRef<string>(
    serializeCanvasState(
      initialStateRef.current.nodes,
      initialStateRef.current.edges,
      initialSemantics,
      initialParsedState.endpointPositions,
    ),
  );

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const shell = canvasShellRef.current;
    if (!shell) {
      return;
    }

    const updateCanvasWidth = (): void => {
      const measuredWidth = Math.max(320, Math.floor(shell.clientWidth) - 24);
      const nextWidth = Math.max(MIN_CANVAS_WIDTH, measuredWidth);
      setCanvasViewportWidth((current) => (current === measuredWidth ? current : measuredWidth));
      setCanvasWidth((current) => (current === nextWidth ? current : nextWidth));
    };

    updateCanvasWidth();
    const observer = new ResizeObserver(() => {
      updateCanvasWidth();
    });
    observer.observe(shell);
    return () => observer.disconnect();
  }, []);

  const renderCanvasWidth = useMemo(
    () => Math.max(canvasWidth, minimumCanvasWidthForNodeCount(nodes.length)),
    [canvasWidth, nodes.length],
  );

  useEffect(() => {
    if ((value ?? "") === lastSerializedRef.current) {
      return;
    }
    const parsed = parseCanvasState(value, coreTools);
    const nextSemantics = deriveCanvasSemantics({
      nodes: parsed.nodes,
      edges: parsed.edges,
      overlayToolKeys,
      combinations,
      selectedPattern,
    });
    setNodes(parsed.nodes);
    setEdges(parsed.edges);
    setEndpointPositions(parsed.endpointPositions ?? {});
    viewportUserAdjustedRef.current = false;
    autoFitSignatureRef.current = null;
    lastSerializedRef.current = serializeCanvasState(
      parsed.nodes,
      parsed.edges,
      nextSemantics,
      parsed.endpointPositions,
    );
  }, [combinations, coreTools, overlayToolKeys, selectedPattern, value]);

  useEffect(() => {
    const hasInputs = Boolean(frequency) && payloadKb !== null && payloadKb !== undefined;
    if (!hasInputs) {
      setOicEstimate(EMPTY_ESTIMATE);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api
        .estimateOIC(projectId, {
          frequency: frequency ?? undefined,
          payload_per_execution_kb: payloadKb ?? undefined,
          response_kb: 0,
        })
        .then((response) => {
          if (!cancelled) {
            setOicEstimate(response);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setOicEstimate(EMPTY_ESTIMATE);
          }
        });
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [frequency, payloadKb, projectId]);

  const semantics = useMemo(
    () =>
      deriveCanvasSemantics({
        nodes,
        edges,
        overlayToolKeys,
        combinations,
        selectedPattern,
      }),
    [combinations, edges, nodes, overlayToolKeys, selectedPattern],
  );
  const interoperabilityReport = useMemo(
    () =>
      evaluateCanvasInteroperability({
        nodes,
        edges,
        overlayToolKeys,
        serviceProfilesById,
        payloadKb,
        triggerType,
        isRealTime,
        sourceTechnology,
        destinationTechnology,
        integrationType,
      }),
    [
      destinationTechnology,
      edges,
      integrationType,
      isRealTime,
      nodes,
      overlayToolKeys,
      payloadKb,
      serviceProfilesById,
      sourceTechnology,
      triggerType,
    ],
  );

  useEffect(() => {
    const layoutSignature = `${renderCanvasWidth}:${nodes.map((node) => `${node.instanceId}:${Math.round(node.x)}:${Math.round(node.y)}`).join("|")}:${edges.map((edge) => `${edge.sourceInstanceId}>${edge.targetInstanceId}`).join("|")}`;
    if (
      autoLayoutSignatureRef.current !== layoutSignature &&
      hasCongestedLayout(nodes, edges, renderCanvasWidth, endpointPositions)
    ) {
      autoLayoutSignatureRef.current = layoutSignature;
      const arrangedNodes = arrangeCanvasNodes(nodes, edges, renderCanvasWidth);
      setNodes(arrangedNodes);
      setEndpointPositions(defaultEndpointPositions(renderCanvasWidth, arrangedNodes));
      return;
    }

    const nextSerialized = serializeCanvasState(nodes, edges, semantics, endpointPositions);
    lastSerializedRef.current = nextSerialized;
    if (nextSerialized !== (value ?? "")) {
      onChange(nextSerialized);
    }
    onToolsChange?.(semantics.coreToolKeys);
    onConnectionValidityChange?.(semantics.hasConnectedRoute);
    onBlockingIssuesChange?.(interoperabilityReport.blockers.length > 0);
  }, [
    edges,
    endpointPositions,
    interoperabilityReport.blockers.length,
    nodes,
    onBlockingIssuesChange,
    onChange,
    onConnectionValidityChange,
    onToolsChange,
    renderCanvasWidth,
    semantics,
    value,
  ]);

  useEffect(() => {
    const validNodeIds = new Set<string>([
      SOURCE_NODE_ID,
      DESTINATION_NODE_ID,
      ...nodes.map((node) => node.instanceId),
    ]);
    const validEdgeIds = new Set<string>(edges.map((edge) => edge.edgeId));

    setEdges((current) => {
      const filtered = current.filter(
        (edge) =>
          validNodeIds.has(edge.sourceInstanceId) && validNodeIds.has(edge.targetInstanceId),
      );
      return filtered.length === current.length ? current : filtered;
    });

    if (connecting && !validNodeIds.has(connecting.sourceInstanceId)) {
      setConnecting(null);
    }
    if (selectedElement?.kind === "node" && !validNodeIds.has(selectedElement.id)) {
      setSelectedElement(null);
    }
    if (selectedElement?.kind === "edge" && !validEdgeIds.has(selectedElement.id)) {
      setSelectedElement(null);
    }
    if (editingNodeId && !validNodeIds.has(editingNodeId)) {
      setEditingNodeId(null);
    }
    if (editingPayloadId && !validNodeIds.has(editingPayloadId)) {
      setEditingPayloadId(null);
    }
    if (editingEdgeId && !validEdgeIds.has(editingEdgeId)) {
      setEditingEdgeId(null);
    }
  }, [connecting, editingEdgeId, editingNodeId, editingPayloadId, edges, nodes, selectedElement]);

  useEffect(() => {
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        x: clamp(node.x, 20, renderCanvasWidth - TOOL_NODE_WIDTH - 20),
        y: clamp(node.y, 20, CANVAS_HEIGHT - TOOL_NODE_HEIGHT - 20),
      })),
    );
    setEndpointPositions((current = {}) => {
      const nextEntries = Object.entries(current).map(([nodeId, position]) => [
        nodeId,
        {
          x: clamp(position.x, 20, renderCanvasWidth - SYSTEM_NODE_WIDTH - 20),
          y: clamp(position.y, 20, CANVAS_HEIGHT - SYSTEM_NODE_HEIGHT - 20),
        },
      ]);
      return Object.fromEntries(nextEntries) as CanvasEndpointPositions;
    });
  }, [renderCanvasWidth]);

  useEffect(() => {
    const element = svgRef.current;
    if (!element) {
      return;
    }

    function handleNativeWheel(event: WheelEvent): void {
      event.preventDefault();
      viewportUserAdjustedRef.current = true;
      const currentViewport = viewportRef.current;
      const canvasPoint = eventCanvasPoint(event, element!);
      const worldBefore = screenToWorld(canvasPoint, currentViewport);
      const nextScale = clamp(
        currentViewport.scale * (event.deltaY > 0 ? 0.92 : 1.08),
        MIN_SCALE,
        MAX_SCALE,
      );
      setViewport({
        scale: nextScale,
        x: canvasPoint.x - worldBefore.x * nextScale,
        y: canvasPoint.y - worldBefore.y * nextScale,
      });
    }

    element.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      element.removeEventListener("wheel", handleNativeWheel);
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select")) {
        return;
      }

      if ((event.key === "Delete" || event.key === "Backspace") && selectedElement) {
        event.preventDefault();
        if (selectedElement.kind === "node") {
          setNodes((current) => current.filter((node) => node.instanceId !== selectedElement.id));
          setEdges((current) =>
            current.filter(
              (edge) =>
                edge.sourceInstanceId !== selectedElement.id &&
                edge.targetInstanceId !== selectedElement.id,
            ),
          );
        } else {
          setEdges((current) => current.filter((edge) => edge.edgeId !== selectedElement.id));
        }
        setSelectedElement(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedElement]);

  const flowNodes = useMemo(
    () =>
      mergedNodes(
        sourceSystem,
        sourceTechnology,
        destinationSystem,
        destinationTechnology,
        renderCanvasWidth,
        nodes,
        endpointPositions,
      ),
    [
      destinationSystem,
      destinationTechnology,
      endpointPositions,
      nodes,
      renderCanvasWidth,
      sourceSystem,
      sourceTechnology,
    ],
  );
  const fitTargetNodes = useMemo(
    () => nodesForViewportFit(flowNodes, nodes, edges),
    [edges, flowNodes, nodes],
  );

  useEffect(() => {
    const bounds = flowBounds(fitTargetNodes);
    if (!bounds || viewportUserAdjustedRef.current) {
      return;
    }

    const fitSignature = `${canvasViewportWidth}:${fitTargetNodes
      .map((node) => `${node.instanceId}:${Math.round(node.x)}:${Math.round(node.y)}`)
      .join("|")}`;
    if (autoFitSignatureRef.current === fitSignature) {
      return;
    }

    autoFitSignatureRef.current = fitSignature;
    setViewport(fittedViewport(bounds, canvasViewportWidth, { preferReadableScale: true }));
  }, [canvasViewportWidth, fitTargetNodes]);

  const connectingSource = connecting ? flowNodes[connecting.sourceInstanceId] : null;
  const monthlyBilling = oicEstimate.billing_msgs_per_month;
  const canvasCursor = panning ? "grabbing" : "grab";
  const processingToolKeys = semantics.coreToolKeys;
  const activeOverlayKeys = semantics.overlayKeys;
  const includesOicGen3 = processingToolKeys.some((toolKey) => toolKey.toLowerCase() === "oic gen3");
  const suggestedPatterns = semantics.suggestedPatternIds
    .map((patternId) => patternMap.get(patternId))
    .filter((pattern): pattern is PatternDefinition => Boolean(pattern));
  const selectedPatternDefinition =
    patternDetail ?? (selectedPattern ? patternMap.get(selectedPattern) ?? null : null);
  const patternMismatch =
    Boolean(selectedPatternDefinition) &&
    semantics.matchedCombinations.length > 0 &&
    !semantics.suggestedPatternIds.includes(selectedPattern ?? "");
  const compatibilitySignal = useMemo(() => {
    if (!semantics.hasDirectedRoute) {
      return {
        tone: "neutral",
        title: "Route validation pending",
        detail: "Connect source, core tools, and destination before compatibility checks can fully validate the design.",
      };
    }
    if (!semantics.hasConnectedRoute) {
      return {
        tone: "neutral",
        title: "Complete the governed route",
        detail: "The canvas has a path, but it still needs at least one connected core tool before Oracle-backed interoperability checks can approve the route.",
      };
    }
    if (interoperabilityReport.blockers.length > 0) {
      return {
        tone: "danger",
        title: "Oracle-backed blockers detected",
        detail: "Resolve the blocker findings before saving. The current route conflicts with documented OCI service limits or supported handoff patterns.",
      };
    }
    if (interoperabilityReport.warnings.length > 0 && semantics.matchedCombinations.length > 0) {
      return {
        tone: "warning",
        title: "Supported stack with review notes",
        detail: "The governed combination is recognized, but Oracle-backed operational caveats still need architect review before you treat this design as production-ready.",
      };
    }
    if (semantics.matchedCombinations.length > 0) {
      return {
        tone: "success",
        title: "Governed combination matched",
        detail: `The active route aligns with ${semantics.matchedCombinations.map((match) => match.combination.code).join(", ")} and no Oracle-backed blockers are currently open on the active path.`,
      };
    }
    if (interoperabilityReport.warnings.length > 0) {
      return {
        tone: "warning",
        title: "Route connected, but review is still required",
        detail: "The route is technically connected, but the current stack still carries operational caveats that are not fully covered by the governed combination catalog.",
      };
    }
    if (interoperabilityReport.advisories.length > 0) {
      return {
        tone: "neutral",
        title: "Oracle-backed advisories available",
        detail: "No hard blockers were found, but the canvas has design advisories worth considering before you finalize the architecture.",
      };
    }
    if (processingToolKeys.length > 0) {
      return {
        tone: "neutral",
        title: "Compatibility not verified yet",
        detail: "Oracle-backed limit checks passed, but the active route does not yet match a governed OCI combination. Keep reviewing the stack before treating it as a governed standard.",
      };
    }
    return {
      tone: "neutral",
      title: "Add governed tools",
      detail: "Add core tools to start validating service limits, governed combinations, and OCI compatibility guidance.",
    };
  }, [
    interoperabilityReport.advisories.length,
    interoperabilityReport.blockers.length,
    interoperabilityReport.warnings.length,
    processingToolKeys.length,
    semantics.hasConnectedRoute,
    semantics.hasDirectedRoute,
    semantics.matchedCombinations,
  ]);

  function addNode(toolKey: string, point?: { x: number; y: number }): void {
    const nextNode = createNode(toolKey, nodes.length);
    setNodes((current) => {
      const nextPoint = point
        ? {
            x: clamp(point.x - TOOL_NODE_WIDTH / 2, 20, renderCanvasWidth - TOOL_NODE_WIDTH - 20),
            y: clamp(point.y - TOOL_NODE_HEIGHT / 2, 20, CANVAS_HEIGHT - TOOL_NODE_HEIGHT - 20),
          }
        : undefined;
      return [
        ...current,
        {
          ...nextNode,
          x: nextPoint?.x ?? nextNode.x,
          y: nextPoint?.y ?? nextNode.y,
        },
      ];
    });
  }

  function resetCanvas(): void {
    const defaults = parseCanvasState(null, coreTools);
    viewportUserAdjustedRef.current = false;
    autoFitSignatureRef.current = null;
    setNodes(defaults.nodes);
    setEdges(defaults.edges);
    setEndpointPositions(defaults.endpointPositions);
    setSelectedElement(null);
    setEditingEdgeId(null);
    setEditingNodeId(null);
    setEditingPayloadId(null);
  }

  function createEdge(sourceInstanceId: string, targetInstanceId: string): void {
    if (
      sourceInstanceId === targetInstanceId ||
      !flowNodes[sourceInstanceId] ||
      !flowNodes[targetInstanceId] ||
      (sourceInstanceId === SOURCE_NODE_ID && targetInstanceId === DESTINATION_NODE_ID)
    ) {
      return;
    }

    setEdges((current) => {
      const exists = current.some(
        (edge) =>
          edge.sourceInstanceId === sourceInstanceId && edge.targetInstanceId === targetInstanceId,
      );
      if (exists) {
        return current;
      }
      return [
        ...current,
        {
          edgeId: crypto.randomUUID(),
          sourceInstanceId,
          targetInstanceId,
          label: "",
        },
      ];
    });
  }

  function beginTextEdit(kind: "node" | "payload" | "edge", id: string, initialValue: string): void {
    setDraftValue(initialValue);
    setEditingNodeId(kind === "node" ? id : null);
    setEditingPayloadId(kind === "payload" ? id : null);
    setEditingEdgeId(kind === "edge" ? id : null);
  }

  function stopTextEdit(): void {
    setEditingNodeId(null);
    setEditingPayloadId(null);
    setEditingEdgeId(null);
    setDraftValue("");
  }

  function fitRouteToView(): void {
    const bounds = flowBounds(fitTargetNodes);
    if (!bounds) {
      return;
    }
    viewportUserAdjustedRef.current = false;
    autoFitSignatureRef.current = null;
    setViewport(fittedViewport(bounds, canvasViewportWidth));
  }

  function autoArrangeRoute(): void {
    viewportUserAdjustedRef.current = false;
    autoFitSignatureRef.current = null;
    autoLayoutSignatureRef.current = null;
    const arrangedNodes = arrangeCanvasNodes(nodes, edges, renderCanvasWidth);
    setEndpointPositions(defaultEndpointPositions(renderCanvasWidth, arrangedNodes));
    setNodes(arrangedNodes);
  }

  function handleCanvasDrop(event: React.DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const toolKey = event.dataTransfer.getData("text/tool-key");
    if (!toolKey) {
      return;
    }
    const canvasPoint = eventCanvasPoint(event.nativeEvent, svg);
    addNode(toolKey, screenToWorld(canvasPoint, viewport));
  }

  function handleCanvasMouseDown(event: ReactMouseEvent<SVGSVGElement>): void {
    const target = event.target as SVGElement;
    const isBackground = target.dataset.role === "canvas-background";
    const isMiddleMouse = event.button === 1;
    if (!isBackground && !isMiddleMouse) {
      return;
    }
    event.preventDefault();
    viewportUserAdjustedRef.current = true;
    setSelectedElement(null);
    setPanning({
      x: event.clientX,
      y: event.clientY,
      viewportX: viewport.x,
      viewportY: viewport.y,
    });
  }

  function handleCanvasMouseMove(event: ReactMouseEvent<SVGSVGElement>): void {
    const svg = svgRef.current;
    if (!svg) {
      return;
    }

    const canvasPoint = eventCanvasPoint(event, svg);
    const worldPoint = screenToWorld(canvasPoint, viewport);

    if (draggingNode) {
      const movingNode = flowNodes[draggingNode.id];
      if (movingNode) {
        const nextPosition = {
          x: clamp(worldPoint.x - draggingNode.dx, 20, renderCanvasWidth - nodeWidth(movingNode) - 20),
          y: clamp(worldPoint.y - draggingNode.dy, 20, CANVAS_HEIGHT - nodeHeight(movingNode) - 20),
        };
        if (movingNode.fixed && isEndpointNodeId(movingNode.instanceId)) {
          setEndpointPositions((current) => ({
            ...current,
            [movingNode.instanceId]: nextPosition,
          }));
        } else {
          setNodes((current) =>
            current.map((node) =>
              node.instanceId === draggingNode.id
                ? {
                    ...node,
                    ...nextPosition,
                  }
                : node,
            ),
          );
        }
      }
    }

    if (connecting) {
      setConnecting({
        ...connecting,
        currentPoint: worldPoint,
      });
    }

    if (panning) {
      setViewport((current) => ({
        ...current,
        x: panning.viewportX + (event.clientX - panning.x),
        y: panning.viewportY + (event.clientY - panning.y),
      }));
    }
  }

  function handleCanvasMouseUp(): void {
    setDraggingNode(null);
    setPanning(null);
    setConnecting(null);
  }

  function renderPaletteButton(option: DictionaryOption, isOverlay: boolean): JSX.Element {
    const definition = toolDefinition(option.value);
    return (
      <button
        key={option.value}
        type="button"
        draggable
        onDragStart={(event) => event.dataTransfer.setData("text/tool-key", option.value)}
        onClick={() => addNode(option.value)}
        className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-[var(--color-text-primary)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-surface)] ${
          isOverlay
            ? "border border-dashed border-[var(--color-border)] bg-[var(--color-surface-2)]"
            : "border border-[var(--color-border)] bg-[var(--color-surface-2)]"
        }`}
        title={option.description ?? "Drag onto the canvas or click to add a node"}
      >
        <span
          className="inline-flex h-6 w-6 items-center justify-center rounded-full"
          style={{ backgroundColor: definition.accent, color: "white" }}
        >
          {definition.icon}
        </span>
        {option.value}
      </button>
    );
  }

  return (
    <div className="min-w-0 space-y-5">
      <div className="min-w-0 space-y-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="app-label">Core Tools</p>
            <p className="mt-2 text-xs text-[var(--color-text-muted)]">
              Drag governed volumetric tools into the route, then connect them from source to destination.
            </p>
          </div>
          <button
            type="button"
            onClick={resetCanvas}
            className="app-button-secondary inline-flex items-center gap-2 px-4 py-2"
          >
            <RotateCcw className="h-4 w-4" />
            Reset
          </button>
        </div>

        <div className="flex min-w-0 gap-3 overflow-x-auto pb-1">{toolOptions.map((option) => renderPaletteButton(option, false))}</div>

        <div className="border-t border-[var(--color-border)] pt-3">
          <p className="app-label">Architectural Overlays</p>
          <p className="mt-2 text-xs text-[var(--color-text-muted)]">
            Overlays document edge protection and runtime context. They do not satisfy the core-tools QA gate by themselves.
          </p>
          <div className="mt-3 flex min-w-0 gap-3 overflow-x-auto pb-1">
            {overlayOptions.map((option) => renderPaletteButton(option, true))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--color-text-muted)]">
          <span>Drag or click to add a node. Endpoints and tools are movable; connect handles to create the flow.</span>
          <span
            className={`rounded-full px-3 py-1 font-semibold ${
              semantics.hasConnectedRoute
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            {semantics.hasConnectedRoute
              ? "Source and destination connected"
              : "Connect source to destination through at least one core tool"}
          </span>
          {semantics.disconnectedNodeIds.length > 0 ? (
            <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-[var(--color-text-secondary)]">
              {semantics.disconnectedNodeIds.length} disconnected node
              {semantics.disconnectedNodeIds.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
      </div>

      {interoperabilityReport.blockers.length > 0 ? (
        <section className="rounded-[1.75rem] border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200">
          <p className="font-semibold">Resolve Oracle-backed blockers before saving</p>
          <p className="mt-2 text-sm">
            The active route conflicts with documented OCI service limits or supported handoff rules.
            Adjust the path until the blocker list is empty.
          </p>
        </section>
      ) : null}

      <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <div ref={canvasShellRef} className="relative min-w-0">
          <div className="absolute left-5 top-5 z-10 flex flex-wrap items-center gap-2">
            <div className="pointer-events-none inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
              <Move className="h-3.5 w-3.5 text-[var(--color-accent)]" />
              Drag empty canvas to pan
              <span className="text-[var(--color-text-muted)]">•</span>
              <ZoomIn className="h-3.5 w-3.5 text-[var(--color-accent)]" />
              Wheel to zoom
            </div>
            <button
              type="button"
              onClick={fitRouteToView}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-semibold text-[var(--color-text-primary)] shadow-sm backdrop-blur transition hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Fit route
            </button>
            <button
              type="button"
              onClick={autoArrangeRoute}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-semibold text-[var(--color-text-primary)] shadow-sm backdrop-blur transition hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" />
              Auto arrange
            </button>
          </div>
          <div className="pointer-events-none absolute right-5 top-5 z-10 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
            Zoom {Math.round(viewport.scale * 100)}%
          </div>
          <div
            className="max-w-full overflow-x-auto rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleCanvasDrop}
          >
            <svg
              ref={svgRef}
              width={renderCanvasWidth}
              height={CANVAS_HEIGHT}
              viewBox={`0 0 ${renderCanvasWidth} ${CANVAS_HEIGHT}`}
              className="block min-w-[960px]"
              style={{ touchAction: "none", cursor: canvasCursor }}
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleCanvasMouseMove}
              onMouseUp={handleCanvasMouseUp}
              onMouseLeave={handleCanvasMouseUp}
              onContextMenu={(event) => event.preventDefault()}
            >
              <defs>
                <pattern id="canvas-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                  <path
                    d="M 32 0 L 0 0 0 32"
                    fill="none"
                    stroke="var(--color-border)"
                    strokeWidth="0.7"
                    opacity="0.55"
                  />
                </pattern>
                <marker id="canvas-arrowhead" markerWidth="16" markerHeight="16" refX="15" refY="8" orient="auto">
                  <path
                    d="M0,0 L0,16 L16,8 z"
                    fill="var(--color-accent)"
                    stroke="var(--color-surface)"
                    strokeWidth="1"
                  />
                </marker>
              </defs>

              <rect
                data-role="canvas-background"
                x={0}
                y={0}
                width={renderCanvasWidth}
                height={CANVAS_HEIGHT}
                fill="url(#canvas-grid)"
                rx={24}
              />

              <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.scale})`}>
                {edges.map((edge) => {
                  const source = flowNodes[edge.sourceInstanceId];
                  const target = flowNodes[edge.targetInstanceId];
                  if (!source || !target) {
                    return null;
                  }

                  const geometry = edgePath(source, target);
                  const screenMidpoint = worldToScreen(geometry.midpoint, viewport);
                  const selected = isEdgeSelected(selectedElement, edge.edgeId);
                  return (
                    <g key={edge.edgeId}>
                      <path
                        d={geometry.path}
                        fill="none"
                        stroke="var(--color-accent)"
                        strokeOpacity={selected ? 0.34 : 0.26}
                        strokeWidth={selected ? 10 : 8.5}
                        strokeLinecap="round"
                      />
                      <path
                        d={geometry.path}
                        fill="none"
                        stroke="var(--color-accent)"
                        strokeWidth={selected ? 5.4 : 4.6}
                        markerEnd="url(#canvas-arrowhead)"
                        strokeLinecap="round"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedElement({ kind: "edge", id: edge.edgeId });
                        }}
                      />
                      {editingEdgeId === edge.edgeId ? (
                        <foreignObject x={geometry.midpoint.x - 76} y={geometry.midpoint.y - 14} width={152} height={34}>
                          <input
                            autoFocus
                            value={draftValue}
                            onChange={(event) => setDraftValue(event.target.value)}
                            onBlur={() => {
                              setEdges((current) =>
                                current.map((currentEdge) =>
                                  currentEdge.edgeId === edge.edgeId
                                    ? { ...currentEdge, label: draftValue.trim() }
                                    : currentEdge,
                                ),
                              );
                              stopTextEdit();
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                setEdges((current) =>
                                  current.map((currentEdge) =>
                                    currentEdge.edgeId === edge.edgeId
                                      ? { ...currentEdge, label: draftValue.trim() }
                                      : currentEdge,
                                  ),
                                );
                                stopTextEdit();
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                stopTextEdit();
                              }
                            }}
                            className="h-8 w-full rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs text-[var(--color-text-primary)]"
                          />
                        </foreignObject>
                      ) : selected || edge.label ? (
                        <foreignObject x={geometry.midpoint.x - 74} y={geometry.midpoint.y - 14} width={148} height={34}>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedElement({ kind: "edge", id: edge.edgeId });
                              beginTextEdit("edge", edge.edgeId, edge.label);
                            }}
                            className="h-8 w-full rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-xs text-[var(--color-text-secondary)] shadow-sm"
                            title={`Edit edge label at ${screenMidpoint.x}, ${screenMidpoint.y}`}
                          >
                            {edge.label || "Set edge label"}
                          </button>
                        </foreignObject>
                      ) : null}
                    </g>
                  );
                })}

                {connecting && connectingSource ? (
                <path
                    d={`M ${handleCoordinates(connectingSource, connecting.startHandle).x} ${handleCoordinates(connectingSource, connecting.startHandle).y} L ${connecting.currentPoint.x} ${connecting.currentPoint.y}`}
                    fill="none"
                    stroke="var(--color-accent)"
                    strokeWidth={3.2}
                    strokeDasharray="8 6"
                  />
                ) : null}

                {Object.values(flowNodes).map((node) => {
                  const definition = node.fixed
                    ? {
                        accent: "var(--canvas-system-border)",
                        surface: "var(--canvas-system-bg)",
                        icon: <Building2 className="h-5 w-5" />,
                      }
                    : toolDefinition(node.toolKey);
                  const serviceProfile = node.fixed
                    ? null
                    : resolveServiceProfile(node.toolKey, serviceProfilesById);
                  const isOverlayNode = !node.fixed && overlayToolSet.has(node.toolKey);
                  const hovered = hoveredNodeId === node.instanceId;
                  const selected = isNodeSelected(selectedElement, node.instanceId);
                  const width = nodeWidth(node);
                  const height = nodeHeight(node);
                  const subtitleText = node.fixed
                    ? renderedSubtitle(node)
                    : isOverlayNode
                      ? `${renderedSubtitle(node)} · Overlay`
                      : renderedSubtitle(node);
                  const labelLines = renderedLabelLines(node);
                  const subtitleY = labelLines.length > 1 ? 66 : 60;
                  const payloadY = labelLines.length > 1 ? 86 : 82;
                  const profileY = labelLines.length > 1 ? 100 : 96;

                  return (
                    <g
                      key={node.instanceId}
                      transform={`translate(${node.x}, ${node.y})`}
                      onMouseEnter={() => setHoveredNodeId(node.instanceId)}
                      onMouseLeave={() => setHoveredNodeId((current) => (current === node.instanceId ? null : current))}
                      onMouseDown={(event) => {
                        if (event.button !== 0 || !svgRef.current) {
                          return;
                        }
                        event.stopPropagation();
                        viewportUserAdjustedRef.current = true;
                        const canvasPoint = eventCanvasPoint(event, svgRef.current);
                        const worldPoint = screenToWorld(canvasPoint, viewport);
                        setDraggingNode({
                          id: node.instanceId,
                          dx: worldPoint.x - node.x,
                          dy: worldPoint.y - node.y,
                        });
                      }}
                      onMouseUp={(event) => {
                        if (connecting) {
                          event.stopPropagation();
                          createEdge(connecting.sourceInstanceId, node.instanceId);
                          setConnecting(null);
                          setSelectedElement({ kind: "node", id: node.instanceId });
                        }
                      }}
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedElement({ kind: "node", id: node.instanceId });
                      }}
                    >
                      <title>
                        {[node.label, subtitleText, node.payloadNote].filter(Boolean).join(" · ")}
                      </title>
                      <rect
                        width={width}
                        height={height}
                        rx={24}
                        fill={definition.surface}
                        stroke={selected ? "var(--color-accent)" : definition.accent}
                        strokeWidth={selected ? 3.5 : 2}
                        strokeDasharray={isOverlayNode ? "10 6" : undefined}
                      />
                      <foreignObject x={18} y={16} width={38} height={38}>
                        <div
                          className="flex h-[38px] w-[38px] items-center justify-center rounded-full shadow-sm"
                          style={{ backgroundColor: definition.accent, color: "white" }}
                        >
                          {definition.icon}
                        </div>
                      </foreignObject>

                      {editingNodeId === node.instanceId ? (
                        <foreignObject x={66} y={16} width={width - 82} height={34}>
                          <input
                            autoFocus
                            value={draftValue}
                            onChange={(event) => setDraftValue(event.target.value)}
                            onBlur={() => {
                              setNodes((current) =>
                                current.map((entry) =>
                                  entry.instanceId === node.instanceId
                                    ? { ...entry, label: draftValue.trim() || entry.toolKey }
                                    : entry,
                                ),
                              );
                              stopTextEdit();
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                setNodes((current) =>
                                  current.map((entry) =>
                                    entry.instanceId === node.instanceId
                                      ? { ...entry, label: draftValue.trim() || entry.toolKey }
                                      : entry,
                                  ),
                                );
                                stopTextEdit();
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                stopTextEdit();
                              }
                            }}
                            className="h-8 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text-primary)]"
                          />
                        </foreignObject>
                      ) : (
                        <text
                          x={66}
                          y={labelLines.length > 1 ? 30 : 38}
                          fontSize={labelFontSize(node)}
                          fontWeight="700"
                          fill="var(--canvas-node-label)"
                          letterSpacing="-0.01em"
                          onDoubleClick={(event) => {
                            event.stopPropagation();
                            if (!node.fixed) {
                              beginTextEdit("node", node.instanceId, node.label);
                            }
                          }}
                        >
                          {labelLines.map((line, index) => (
                            <tspan key={`${node.instanceId}-label-${index}`} x={66} dy={index === 0 ? 0 : 17}>
                              {line}
                            </tspan>
                          ))}
                        </text>
                      )}

                      <text
                        x={66}
                        y={subtitleY}
                        fontSize={node.fixed ? 12 : 12.5}
                        fontWeight="600"
                        fill="var(--canvas-node-sub)"
                      >
                        {subtitleText}
                      </text>

                      {!node.fixed && editingPayloadId === node.instanceId ? (
                        <foreignObject x={18} y={payloadY - 17} width={width - 36} height={30}>
                          <input
                            autoFocus
                            value={draftValue}
                            onChange={(event) => setDraftValue(event.target.value)}
                            onBlur={() => {
                              setNodes((current) =>
                                current.map((entry) =>
                                  entry.instanceId === node.instanceId
                                    ? { ...entry, payloadNote: draftValue.trim() }
                                    : entry,
                                ),
                              );
                              stopTextEdit();
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                setNodes((current) =>
                                  current.map((entry) =>
                                    entry.instanceId === node.instanceId
                                      ? { ...entry, payloadNote: draftValue.trim() }
                                      : entry,
                                  ),
                                );
                                stopTextEdit();
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                stopTextEdit();
                              }
                            }}
                            className="h-7 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs text-[var(--color-text-primary)]"
                          />
                        </foreignObject>
                      ) : !node.fixed ? (
                        <text
                          x={18}
                          y={payloadY}
                          fontSize={12}
                          fontWeight={node.payloadNote ? 600 : 500}
                          fill={node.payloadNote ? "var(--canvas-node-sub)" : "var(--color-text-secondary)"}
                          onDoubleClick={(event) => {
                            event.stopPropagation();
                            beginTextEdit("payload", node.instanceId, node.payloadNote);
                          }}
                        >
                          {renderedPayload(node)}
                        </text>
                      ) : null}

                      {!node.fixed && serviceProfile ? (
                        <foreignObject x={18} y={profileY} width={width - 36} height={38}>
                          <div className="h-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]/78 px-3 py-2 text-xs text-[var(--color-text-secondary)] shadow-sm">
                            <div
                              className="font-semibold"
                              style={{
                                color:
                                  (serviceProfile.sla_uptime_pct ?? 0) < 99.9
                                    ? "var(--canvas-stream-border)"
                                    : "var(--canvas-node-label)",
                              }}
                            >
                              SLA{" "}
                              {serviceProfile.sla_uptime_pct !== null
                                ? `${serviceProfile.sla_uptime_pct.toFixed(1).replace(/\.0$/, "")}%`
                                : "n/a"}
                            </div>
                            <div className="mt-0.5 truncate">{topConstraintLabel(serviceProfile)}</div>
                          </div>
                        </foreignObject>
                      ) : null}

                      {!node.fixed && (hovered || selected) ? (
                        <foreignObject x={18} y={height + 10} width={width - 36} height={32}>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                beginTextEdit("node", node.instanceId, node.label);
                              }}
                              className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-secondary)]"
                            >
                              Rename
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                beginTextEdit("payload", node.instanceId, node.payloadNote);
                              }}
                              className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-secondary)]"
                            >
                              Payload
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                setNodes((current) =>
                                  current.filter((entry) => entry.instanceId !== node.instanceId),
                                );
                                setEdges((current) =>
                                  current.filter(
                                    (edge) =>
                                      edge.sourceInstanceId !== node.instanceId &&
                                      edge.targetInstanceId !== node.instanceId,
                                  ),
                                );
                              }}
                              className="rounded-full border border-rose-200 bg-rose-50 p-1 text-rose-700"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </foreignObject>
                      ) : null}

                      {(hovered || selected) &&
                        (["top", "right", "bottom", "left"] as HandlePosition[]).map((handle) => {
                          const point = handleCoordinates(node, handle);
                          return (
                            <circle
                              key={`${node.instanceId}-${handle}`}
                              cx={point.x - node.x}
                              cy={point.y - node.y}
                              r={HANDLE_RADIUS}
                              fill="var(--color-accent)"
                              stroke="white"
                              strokeWidth={2}
                              onMouseDown={(event) => {
                                event.stopPropagation();
                                setSelectedElement({ kind: "node", id: node.instanceId });
                                setConnecting({
                                  sourceInstanceId: node.instanceId,
                                  startHandle: handle,
                                  currentPoint: handleCoordinates(node, handle),
                                });
                              }}
                            />
                          );
                        })}
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        </div>

        <aside className="min-w-0 space-y-4">
          <section className="app-card-muted p-4 text-sm">
            <span className="font-medium text-[var(--color-text-primary)]">Governed route</span>
            <p className="mt-2 text-[var(--color-text-secondary)]">
              {semantics.hasConnectedRoute
                ? `${semantics.routeLabels.length} active route${semantics.routeLabels.length === 1 ? "" : "s"} from source to destination`
                : "The current design is not yet a governed source-to-destination route"}
            </p>
            <div className="mt-3 space-y-2">
              {semantics.routeLabels.length > 0 ? (
                semantics.routeLabels.map((route) => (
                  <p key={route} className="rounded-xl bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
                    {route}
                  </p>
                ))
              ) : (
                <p className="rounded-xl bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
                  Connect handles between source, tools, and destination to define the active route.
                </p>
              )}
            </div>
          </section>

          <section className="app-card-muted p-4 text-sm">
            <span className="font-medium text-[var(--color-text-primary)]">Compatibility & combination checks</span>
            <div className="mt-3 space-y-3">
              <div
                className={[
                  "rounded-2xl border p-3 text-xs leading-5",
                  compatibilitySignal.tone === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200"
                    : compatibilitySignal.tone === "danger"
                      ? "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200"
                    : compatibilitySignal.tone === "warning"
                      ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
                      : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)]",
                ].join(" ")}
              >
                <p className="font-semibold">{compatibilitySignal.title}</p>
                <p className="mt-2">{compatibilitySignal.detail}</p>
              </div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
                Oracle-backed route findings
              </p>
              <ValidationFindingGroup
                title="Blockers"
                findings={interoperabilityReport.blockers}
                severity="blocker"
              />
              <ValidationFindingGroup
                title="Warnings"
                findings={interoperabilityReport.warnings}
                severity="warning"
              />
              <ValidationFindingGroup
                title="Advisories"
                findings={interoperabilityReport.advisories}
                severity="advisory"
              />
              {semantics.matchedCombinations.length > 0 ? (
                semantics.matchedCombinations.map((match) => (
                  <article
                    key={match.combination.code}
                    className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-[var(--color-text-primary)]">
                          {match.combination.code} {match.combination.name}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{match.reason}</p>
                      </div>
                      <span className="rounded-full bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-secondary)]">
                        {match.matchType}
                      </span>
                    </div>
                    <p className="mt-3 text-xs text-[var(--color-text-secondary)]">
                      Guidance: {match.combination.guidance}
                    </p>
                    {match.combination.recommended_overlays.length > 0 ? (
                      <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
                        Suggested overlays: {match.combination.recommended_overlays.join(", ")}
                      </p>
                    ) : null}
                  </article>
                ))
              ) : (
                <p className="rounded-xl bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
                  Add and connect governed tools to receive workbook-backed and Oracle-backed compatibility hints.
                </p>
              )}
            </div>
          </section>

          <section className="app-card-muted p-4 text-sm">
            <span className="font-medium text-[var(--color-text-primary)]">Pattern guidance</span>
            <div className="mt-3 space-y-2">
              {selectedPatternDefinition ? (
                <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <PatternSupportBadge support={selectedPatternDefinition.support} />
                    <p className="font-medium text-[var(--color-text-primary)]">
                      Selected: {selectedPatternDefinition.pattern_id} {selectedPatternDefinition.name}
                    </p>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">
                    {selectedPatternDefinition.support.summary}
                  </p>
                </div>
              ) : null}
              {suggestedPatterns.length > 0 ? (
                suggestedPatterns.map((pattern) => (
                  <p key={pattern.pattern_id} className="rounded-xl bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
                    <span className="font-semibold text-[var(--color-text-primary)]">{pattern.pattern_id}</span>{" "}
                    {pattern.name}
                  </p>
                ))
              ) : (
                <p className="rounded-xl bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
                  No governed pattern suggestions yet. Complete the active route first.
                </p>
              )}
              {patternMismatch && selectedPatternDefinition ? (
                <div className="rounded-2xl border border-amber-300 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                  <p className="font-semibold">Potential anti-pattern</p>
                  <p className="mt-2">
                    The active route aligns with {semantics.suggestedPatternIds.join(", ")}, but the selected pattern is{" "}
                    {selectedPatternDefinition.pattern_id}. Review the designed tool stack before treating this pipeline as parity-ready.
                  </p>
                  {selectedPatternDefinition.when_not_to_use ? (
                    <p className="mt-2">{selectedPatternDefinition.when_not_to_use}</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </section>
        </aside>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Payload ingress</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">{payloadKb ?? "?"} KB / execution</p>
          <p className="text-[var(--color-text-secondary)]">
            {frequency ? displayUiValue(frequency) : "unknown frequency"}
          </p>
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Processing</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">
            {processingToolKeys.length} core tool{processingToolKeys.length === 1 ? "" : "s"} on the active route
          </p>
          <p className="text-[var(--color-text-secondary)]">{semantics.processingSummary}</p>
          <p className="text-[var(--color-text-secondary)]">Overlays: {semantics.overlaySummary}</p>
          <p className="text-[var(--color-text-secondary)]">Pattern: {selectedPattern ?? "unassigned"}</p>
          {selectedPatternDefinition && !selectedPatternDefinition.support.parity_ready ? (
            <p className="text-[var(--color-text-secondary)]">
              Pattern support note: this selection remains reference-only, so technical estimates stay directional.
            </p>
          ) : null}
          {includesOicGen3 ? (
            <p className="text-[var(--color-text-secondary)]">
              Estimated OIC msgs/month: {monthlyBilling ?? "unknown"}
            </p>
          ) : (
            <p className="text-[var(--color-text-secondary)]">OIC billing estimate not applicable to this pipeline</p>
          )}
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Outcome</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">→ {destinationSystem ?? "unknown"}</p>
          <p className="text-[var(--color-text-secondary)]">{destinationTechnology ?? ""}</p>
          <p className="text-[var(--color-text-secondary)]">{patternCategory ?? "No pattern category"}</p>
          {activeOverlayKeys.length > 0 ? (
            <p className="text-[var(--color-text-secondary)]">
              Active overlays: {activeOverlayKeys.join(", ")}
            </p>
          ) : null}
        </div>
      </div>

      {selectedPatternDefinition ? <PatternDetailPanel patternDetail={selectedPatternDefinition} /> : null}
    </div>
  );
}
