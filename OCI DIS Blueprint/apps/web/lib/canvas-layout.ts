import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  type CanvasEdge,
  type CanvasNode,
} from "./canvas-governance";

export const CANVAS_HEIGHT = 560;
export const ROUTE_NODE_GAP = 64;
export const TOOL_NODE_WIDTH = 184;
export const TOOL_NODE_HEIGHT = 126;
export const SYSTEM_NODE_WIDTH = 218;
export const SYSTEM_NODE_HEIGHT = 96;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function primaryRouteNodeIds(nodes: CanvasNode[], edges: CanvasEdge[]): string[] {
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

export function arrangeCanvasNodes(
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  canvasWidth: number,
): CanvasNode[] {
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
  const sideStartX = routeStartX;
  const sideColumnCount = Math.max(
    1,
    Math.floor((canvasWidth - sideStartX - 40) / routeStep),
  );
  sideNodes.forEach((instanceId, index) => {
    const column = index % sideColumnCount;
    const row = Math.floor(index / sideColumnCount);
    positions.set(instanceId, {
      x: sideStartX + column * routeStep,
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
