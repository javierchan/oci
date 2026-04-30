"use client";

/* Shared parsing and governance helpers for the integration design canvas. */

import type { CanvasCombination } from "@/lib/types";

export const SOURCE_NODE_ID = "source-system";
export const DESTINATION_NODE_ID = "destination-system";
export type CanvasEndpointId = typeof SOURCE_NODE_ID | typeof DESTINATION_NODE_ID;

export type CanvasPoint = {
  x: number;
  y: number;
};

export type CanvasEndpointPositions = Partial<Record<CanvasEndpointId, CanvasPoint>>;

export type CanvasNode = {
  instanceId: string;
  toolKey: string;
  label: string;
  payloadNote: string;
  x: number;
  y: number;
};

export type CanvasEdge = {
  edgeId: string;
  sourceInstanceId: string;
  targetInstanceId: string;
  label: string;
};

type StoredCanvasStateV3 = {
  v: 3;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  coreToolKeys: string[];
  overlayKeys: string[];
};

type StoredCanvasStateV4 = {
  v: 4;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  coreToolKeys: string[];
  overlayKeys: string[];
  endpointPositions?: CanvasEndpointPositions;
};

type StoredCanvasStateV2 = {
  v: 2;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
};

type LegacyCanvasState = {
  v: 1;
  n: Array<{ i: string; t: string; l: string; p: string; x: number; y: number }>;
  e: Array<{ s: string; t: string; l: string }>;
};

export type CanvasParsedState = {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  coreToolKeys: string[];
  overlayKeys: string[];
  endpointPositions: CanvasEndpointPositions;
};

export type CanvasCombinationMatch = {
  combination: CanvasCombination;
  matchType: "exact" | "superset" | "partial";
  score: number;
  reason: string;
};

export type CanvasDerivedSemantics = {
  hasDirectedRoute: boolean;
  hasConnectedRoute: boolean;
  activeNodeIds: string[];
  activeEdgeIds: string[];
  disconnectedNodeIds: string[];
  coreToolKeys: string[];
  overlayKeys: string[];
  processingRouteLabels: string[];
  routeLabels: string[];
  processingSummary: string;
  overlaySummary: string;
  matchedCombinations: CanvasCombinationMatch[];
  suggestedPatternIds: string[];
};

function isStoredCanvasStateV3(value: unknown): value is StoredCanvasStateV3 {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<StoredCanvasStateV3>;
  return (
    candidate.v === 3 &&
    Array.isArray(candidate.nodes) &&
    Array.isArray(candidate.edges) &&
    Array.isArray(candidate.coreToolKeys) &&
    Array.isArray(candidate.overlayKeys)
  );
}

function isStoredCanvasStateV4(value: unknown): value is StoredCanvasStateV4 {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<StoredCanvasStateV4>;
  return (
    candidate.v === 4 &&
    Array.isArray(candidate.nodes) &&
    Array.isArray(candidate.edges) &&
    Array.isArray(candidate.coreToolKeys) &&
    Array.isArray(candidate.overlayKeys)
  );
}

function isStoredCanvasStateV2(value: unknown): value is StoredCanvasStateV2 {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<StoredCanvasStateV2>;
  return candidate.v === 2 && Array.isArray(candidate.nodes) && Array.isArray(candidate.edges);
}

function isLegacyCanvasState(value: unknown): value is LegacyCanvasState {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<LegacyCanvasState>;
  return candidate.v === 1 && Array.isArray(candidate.n) && Array.isArray(candidate.e);
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

export function uniqueToolKeys(nodes: CanvasNode[]): string[] {
  return uniqueSorted(nodes.map((node) => node.toolKey));
}

function createNode(toolKey: string, index: number): CanvasNode {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    instanceId: crypto.randomUUID(),
    toolKey,
    label: toolKey,
    payloadNote: "",
    x: 240 + column * 220,
    y: 80 + row * 140,
  };
}

function buildDefaultNodes(coreToolKeys: string[]): CanvasNode[] {
  return coreToolKeys.map((toolKey, index) => createNode(toolKey, index));
}

function buildDefaultEdges(nodes: CanvasNode[]): CanvasEdge[] {
  if (nodes.length === 0) {
    return [];
  }

  const edges: CanvasEdge[] = [];
  let previousId = SOURCE_NODE_ID;
  for (const node of nodes) {
    edges.push({
      edgeId: crypto.randomUUID(),
      sourceInstanceId: previousId,
      targetInstanceId: node.instanceId,
      label: "",
    });
    previousId = node.instanceId;
  }
  edges.push({
    edgeId: crypto.randomUUID(),
    sourceInstanceId: previousId,
    targetInstanceId: DESTINATION_NODE_ID,
    label: "",
  });
  return edges;
}

export function isDirectSourceDestinationEdge(edge: CanvasEdge): boolean {
  return edge.sourceInstanceId === SOURCE_NODE_ID && edge.targetInstanceId === DESTINATION_NODE_ID;
}

export function hasDirectedPath(edges: CanvasEdge[], sourceId: string, targetId: string): boolean {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const next = adjacency.get(edge.sourceInstanceId) ?? [];
    next.push(edge.targetInstanceId);
    adjacency.set(edge.sourceInstanceId, next);
  }

  const visited = new Set<string>();
  const queue: string[] = [sourceId];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current)) {
      continue;
    }
    if (current === targetId) {
      return true;
    }
    visited.add(current);
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!visited.has(neighbor)) {
        queue.push(neighbor);
      }
    }
  }

  return false;
}

function sanitizeCanvasState(nodes: CanvasNode[], edges: CanvasEdge[]): { nodes: CanvasNode[]; edges: CanvasEdge[] } {
  const uniqueNodes = new Map<string, CanvasNode>();
  for (const node of nodes) {
    if (!node.instanceId || !node.toolKey) {
      continue;
    }
    uniqueNodes.set(node.instanceId, {
      instanceId: node.instanceId,
      toolKey: node.toolKey,
      label: node.label || node.toolKey,
      payloadNote: node.payloadNote ?? "",
      x: Number.isFinite(node.x) ? node.x : 240,
      y: Number.isFinite(node.y) ? node.y : 80,
    });
  }

  const validIds = new Set<string>([SOURCE_NODE_ID, DESTINATION_NODE_ID, ...uniqueNodes.keys()]);
  const seenPairs = new Set<string>();
  const sanitizedEdges = edges.filter((edge) => {
    if (
      !edge.edgeId ||
      edge.sourceInstanceId === edge.targetInstanceId ||
      !validIds.has(edge.sourceInstanceId) ||
      !validIds.has(edge.targetInstanceId) ||
      isDirectSourceDestinationEdge(edge)
    ) {
      return false;
    }
    const pair = `${edge.sourceInstanceId}::${edge.targetInstanceId}`;
    if (seenPairs.has(pair)) {
      return false;
    }
    seenPairs.add(pair);
    return true;
  });

  return {
    nodes: Array.from(uniqueNodes.values()),
    edges: sanitizedEdges,
  };
}

function isEndpointId(value: string): value is CanvasEndpointId {
  return value === SOURCE_NODE_ID || value === DESTINATION_NODE_ID;
}

function sanitizeEndpointPositions(value: unknown): CanvasEndpointPositions {
  if (!value || typeof value !== "object") {
    return {};
  }

  const candidate = value as Partial<Record<string, Partial<CanvasPoint>>>;
  return Object.fromEntries(
    Object.entries(candidate)
      .filter(([key, point]) => isEndpointId(key) && Number.isFinite(point?.x) && Number.isFinite(point?.y))
      .map(([key, point]) => [key, { x: Number(point?.x), y: Number(point?.y) }]),
  ) as CanvasEndpointPositions;
}

export function parseCanvasState(value: string | null, coreToolKeys: string[]): CanvasParsedState {
  if (!value) {
    const nodes = buildDefaultNodes(coreToolKeys);
    return {
      nodes,
      edges: buildDefaultEdges(nodes),
      coreToolKeys: uniqueSorted(coreToolKeys),
      overlayKeys: [],
      endpointPositions: {},
    };
  }

  try {
    const parsed: unknown = JSON.parse(value);
    if (isStoredCanvasStateV4(parsed)) {
      const sanitized = sanitizeCanvasState(parsed.nodes, parsed.edges);
      return {
        ...sanitized,
        coreToolKeys: uniqueSorted(parsed.coreToolKeys),
        overlayKeys: uniqueSorted(parsed.overlayKeys),
        endpointPositions: sanitizeEndpointPositions(parsed.endpointPositions),
      };
    }

    if (isStoredCanvasStateV3(parsed)) {
      const sanitized = sanitizeCanvasState(parsed.nodes, parsed.edges);
      return {
        ...sanitized,
        coreToolKeys: uniqueSorted(parsed.coreToolKeys),
        overlayKeys: uniqueSorted(parsed.overlayKeys),
        endpointPositions: {},
      };
    }

    if (isStoredCanvasStateV2(parsed)) {
      const sanitized = sanitizeCanvasState(parsed.nodes, parsed.edges);
      return {
        ...sanitized,
        coreToolKeys: uniqueSorted(coreToolKeys),
        overlayKeys: [],
        endpointPositions: {},
      };
    }

    if (isLegacyCanvasState(parsed)) {
      const sanitized = sanitizeCanvasState(
        parsed.n.map((node) => ({
          instanceId: node.i,
          toolKey: node.t,
          label: node.l ?? node.t,
          payloadNote: node.p ?? "",
          x: node.x,
          y: node.y,
        })),
        parsed.e.map((edge) => ({
          edgeId: crypto.randomUUID(),
          sourceInstanceId: edge.s,
          targetInstanceId: edge.t,
          label: edge.l ?? "",
        })),
      );
      return {
        ...sanitized,
        coreToolKeys: uniqueSorted(coreToolKeys),
        overlayKeys: [],
        endpointPositions: {},
      };
    }
  } catch {}

  const nodes = buildDefaultNodes(coreToolKeys);
  return {
    nodes,
    edges: buildDefaultEdges(nodes),
    coreToolKeys: uniqueSorted(coreToolKeys),
    overlayKeys: [],
    endpointPositions: {},
  };
}

export function serializeCanvasState(
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  semantics: Pick<CanvasDerivedSemantics, "coreToolKeys" | "overlayKeys">,
  endpointPositions: CanvasEndpointPositions = {},
): string {
  const sanitized = sanitizeCanvasState(nodes, edges);
  const payload: StoredCanvasStateV4 = {
    v: 4,
    nodes: sanitized.nodes,
    edges: sanitized.edges,
    coreToolKeys: uniqueSorted(semantics.coreToolKeys),
    overlayKeys: uniqueSorted(semantics.overlayKeys),
    endpointPositions: sanitizeEndpointPositions(endpointPositions),
  };
  return JSON.stringify(payload);
}

function reachableNodeIds(edges: CanvasEdge[], startId: string): Set<string> {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const next = adjacency.get(edge.sourceInstanceId) ?? [];
    next.push(edge.targetInstanceId);
    adjacency.set(edge.sourceInstanceId, next);
  }

  const visited = new Set<string>();
  const queue: string[] = [startId];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current)) {
      continue;
    }
    visited.add(current);
    for (const neighbor of adjacency.get(current) ?? []) {
      if (!visited.has(neighbor)) {
        queue.push(neighbor);
      }
    }
  }
  return visited;
}

function reverseReachableNodeIds(edges: CanvasEdge[], targetId: string): Set<string> {
  const reversed = edges.map((edge) => ({
    edgeId: edge.edgeId,
    sourceInstanceId: edge.targetInstanceId,
    targetInstanceId: edge.sourceInstanceId,
    label: edge.label,
  }));
  return reachableNodeIds(reversed, targetId);
}

function enumeratePaths(edges: CanvasEdge[], maxPaths: number = 8): string[][] {
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const next = adjacency.get(edge.sourceInstanceId) ?? [];
    next.push(edge.targetInstanceId);
    adjacency.set(edge.sourceInstanceId, next);
  }

  const routes: string[][] = [];
  function dfs(currentId: string, path: string[], visited: Set<string>): void {
    if (routes.length >= maxPaths) {
      return;
    }
    if (currentId === DESTINATION_NODE_ID) {
      routes.push(path);
      return;
    }
    for (const nextId of adjacency.get(currentId) ?? []) {
      if (visited.has(nextId)) {
        continue;
      }
      visited.add(nextId);
      dfs(nextId, [...path, nextId], visited);
      visited.delete(nextId);
    }
  }

  dfs(SOURCE_NODE_ID, [SOURCE_NODE_ID], new Set([SOURCE_NODE_ID]));
  return routes;
}

function matchCombinations(
  coreToolKeys: string[],
  overlayKeys: string[],
  combinations: CanvasCombination[],
  selectedPattern: string | null,
): CanvasCombinationMatch[] {
  const activeCoreSet = new Set(coreToolKeys);
  const activeOverlaySet = new Set(overlayKeys);
  const matches: CanvasCombinationMatch[] = [];

  for (const combination of combinations) {
    const sharedTools = combination.supported_tool_keys.filter((toolKey) => activeCoreSet.has(toolKey));
    if (sharedTools.length === 0) {
      continue;
    }

    const missingTools = combination.supported_tool_keys.filter((toolKey) => !activeCoreSet.has(toolKey));
    const extraTools = coreToolKeys.filter((toolKey) => !combination.supported_tool_keys.includes(toolKey));

    let matchType: CanvasCombinationMatch["matchType"] | null = null;
    let score = 0;

    if (missingTools.length === 0 && extraTools.length === 0) {
      matchType = "exact";
      score = 100;
    } else if (missingTools.length === 0) {
      matchType = "superset";
      score = 82 - extraTools.length * 4;
    } else if (sharedTools.length >= Math.min(2, combination.supported_tool_keys.length)) {
      matchType = "partial";
      score = 48 + sharedTools.length * 8 - missingTools.length * 6;
    }

    if (!matchType) {
      continue;
    }

    const overlayMatches = combination.recommended_overlays.filter((overlay) =>
      activeOverlaySet.has(overlay),
    );
    if (overlayMatches.length > 0) {
      score += overlayMatches.length * 5;
    }
    if (selectedPattern && combination.compatible_pattern_ids.includes(selectedPattern)) {
      score += 12;
    }

    let reason =
      matchType === "exact"
        ? `Core tools match ${combination.code} exactly.`
        : matchType === "superset"
          ? `Active route contains the full ${combination.code} stack plus additional tools.`
          : `Active route overlaps ${combination.code} on ${sharedTools.length} governed tools.`;
    if (overlayMatches.length > 0) {
      reason += ` Overlay signal: ${overlayMatches.join(", ")}.`;
    }

    matches.push({
      combination,
      matchType,
      score,
      reason,
    });
  }

  return matches
    .sort((left, right) => right.score - left.score || left.combination.code.localeCompare(right.combination.code))
    .slice(0, 4);
}

export function deriveCanvasSemantics(args: {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  overlayToolKeys: string[];
  combinations: CanvasCombination[];
  selectedPattern: string | null;
}): CanvasDerivedSemantics {
  const sanitized = sanitizeCanvasState(args.nodes, args.edges);
  const overlayToolSet = new Set(args.overlayToolKeys);
  const hasDirectedRoute = hasDirectedPath(sanitized.edges, SOURCE_NODE_ID, DESTINATION_NODE_ID);
  const forwardReachable = reachableNodeIds(sanitized.edges, SOURCE_NODE_ID);
  const backwardReachable = reverseReachableNodeIds(sanitized.edges, DESTINATION_NODE_ID);
  const activeNodeIds = sanitized.nodes
    .filter((node) => forwardReachable.has(node.instanceId) && backwardReachable.has(node.instanceId))
    .map((node) => node.instanceId);
  const activeNodeIdSet = new Set(activeNodeIds);

  const activeEdges = sanitized.edges.filter(
    (edge) =>
      (edge.sourceInstanceId === SOURCE_NODE_ID || activeNodeIdSet.has(edge.sourceInstanceId)) &&
      (edge.targetInstanceId === DESTINATION_NODE_ID || activeNodeIdSet.has(edge.targetInstanceId)),
  );

  const activeCoreToolKeys = uniqueSorted(
    sanitized.nodes
      .filter((node) => activeNodeIdSet.has(node.instanceId) && !overlayToolSet.has(node.toolKey))
      .map((node) => node.toolKey),
  );
  const activeOverlayKeys = uniqueSorted(
    sanitized.nodes
      .filter((node) => activeNodeIdSet.has(node.instanceId) && overlayToolSet.has(node.toolKey))
      .map((node) => node.toolKey),
  );
  const hasConnectedRoute = hasDirectedRoute && activeCoreToolKeys.length > 0;

  const nodeLabelEntries: Array<[string, string]> = [
    [SOURCE_NODE_ID, "Source"],
    [DESTINATION_NODE_ID, "Destination"],
    ...sanitized.nodes.map((node): [string, string] => [node.instanceId, node.label || node.toolKey]),
  ];
  const nodeLabelMap = new Map<string, string>(nodeLabelEntries);
  const pathLabels = enumeratePaths(activeEdges).map((path) =>
    path
      .filter((nodeId) => nodeId !== SOURCE_NODE_ID && nodeId !== DESTINATION_NODE_ID)
      .map((nodeId) => nodeLabelMap.get(nodeId) ?? nodeId)
      .join(" -> "),
  );
  const routeLabels = uniqueSorted(pathLabels.filter(Boolean));
  const processingRouteLabels = uniqueSorted(
    enumeratePaths(activeEdges)
      .map((path) =>
        path
          .filter((nodeId) => nodeId !== SOURCE_NODE_ID && nodeId !== DESTINATION_NODE_ID)
          .filter((nodeId) => {
            const node = sanitized.nodes.find((candidate) => candidate.instanceId === nodeId);
            return node ? !overlayToolSet.has(node.toolKey) : false;
          })
          .map((nodeId) => nodeLabelMap.get(nodeId) ?? nodeId)
          .join(" -> "),
      )
      .filter(Boolean),
  );
  const matchedCombinations = matchCombinations(
    activeCoreToolKeys,
    activeOverlayKeys,
    args.combinations,
    args.selectedPattern,
  );
  const suggestedPatternIds = uniqueSorted(
    matchedCombinations.flatMap((match) => match.combination.compatible_pattern_ids),
  );

  return {
    hasDirectedRoute,
    hasConnectedRoute,
    activeNodeIds,
    activeEdgeIds: activeEdges.map((edge) => edge.edgeId),
    disconnectedNodeIds: sanitized.nodes
      .filter((node) => !activeNodeIdSet.has(node.instanceId))
      .map((node) => node.instanceId),
    coreToolKeys: activeCoreToolKeys,
    overlayKeys: activeOverlayKeys,
    processingRouteLabels,
    routeLabels,
    processingSummary:
      processingRouteLabels[0] ??
      (activeCoreToolKeys.length > 0
        ? activeCoreToolKeys.join(" -> ")
        : "No connected core tools on the active route yet"),
    overlaySummary:
      activeOverlayKeys.length > 0
        ? activeOverlayKeys.join(", ")
        : "No overlays attached to the active route",
    matchedCombinations,
    suggestedPatternIds,
  };
}
