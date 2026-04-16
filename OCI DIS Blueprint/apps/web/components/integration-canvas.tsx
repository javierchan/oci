"use client";

/* SVG-based integration flow canvas with draggable tool nodes, connectable edges, pan, and zoom. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import { formatFrequency, formatPatternCategory } from "@/lib/format";

type HandlePosition = "top" | "right" | "bottom" | "left";
type SelectedElement =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | null;

const SOURCE_NODE_ID = "source-system";
const DESTINATION_NODE_ID = "destination-system";
const VIEWPORT_WIDTH = 1200;
const VIEWPORT_HEIGHT = 560;
const MIN_SCALE = 0.5;
const MAX_SCALE = 2;
const NODE_WIDTH = 180;
const NODE_HEIGHT = 96;
const HANDLE_RADIUS = 7;

type CanvasNode = {
  instanceId: string;
  toolKey: string;
  label: string;
  payloadNote: string;
  x: number;
  y: number;
};

type CanvasEdge = {
  edgeId: string;
  sourceInstanceId: string;
  targetInstanceId: string;
  label: string;
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

type FixedNodeMeta = {
  subtitle: string | null;
  fixed: boolean;
};

type FlowNode = CanvasNode & FixedNodeMeta;

type ToolDefinition = {
  toolKey: string;
  abbreviation: string;
  accent: string;
  surface: string;
};

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

type IntegrationCanvasProps = {
  sourceSystem: string;
  sourceTechnology: string | null;
  destinationSystem: string | null;
  destinationTechnology: string | null;
  selectedPattern: string | null;
  coreTools: string[];
  availableTools: string[];
  payloadKb: number | null;
  frequency: string | null;
  patternCategory: string | null;
  value: string | null;
  onChange: (_nextValue: string) => void;
  onToolsChange?: (_toolKeys: string[]) => void;
};

function estimateBillingMsgs(payloadKb: number | null): number | null {
  if (!payloadKb) {
    return null;
  }
  return Math.ceil(payloadKb / 50);
}

function estimateExecutionsPerDay(frequency: string | null): number | null {
  if (!frequency) {
    return null;
  }

  const normalized = frequency.trim().toLowerCase();
  const exactMatches: Record<string, number | null> = {
    "una vez al día": 1,
    "2 veces al día": 2,
    "dos veces al día": 2,
    "4 veces al día": 4,
    "cada hora": 24,
    "cada 30 minutos": 48,
    "cada 15 minutos": 96,
    "cada 5 minutos": 288,
    "cada minuto": 1440,
    "tiempo real": 1440,
    semanal: 1 / 7,
    mensual: 1 / 30,
    "bajo demanda": null,
    "once daily": 1,
    "twice daily": 2,
    "4 times daily": 4,
    hourly: 24,
    "every 30 minutes": 48,
    "every 15 minutes": 96,
    "every 5 minutes": 288,
    "every minute": 1440,
    "real time": 1440,
    weekly: 1 / 7,
    monthly: 1 / 30,
    "on demand": null,
  };

  if (normalized in exactMatches) {
    return exactMatches[normalized] ?? null;
  }

  const hourlyMatch = normalized.match(/cada\s+(\d+)\s+hora/);
  if (hourlyMatch) {
    const hours = Number(hourlyMatch[1]);
    return hours > 0 ? 24 / hours : null;
  }

  const minuteMatch = normalized.match(/cada\s+(\d+)\s+minuto/);
  if (minuteMatch) {
    const minutes = Number(minuteMatch[1]);
    return minutes > 0 ? (24 * 60) / minutes : null;
  }

  const englishHourlyMatch = normalized.match(/every\s+(\d+)\s+hours?/);
  if (englishHourlyMatch) {
    const hours = Number(englishHourlyMatch[1]);
    return hours > 0 ? 24 / hours : null;
  }

  const englishMinuteMatch = normalized.match(/every\s+(\d+)\s+minutes?/);
  if (englishMinuteMatch) {
    const minutes = Number(englishMinuteMatch[1]);
    return minutes > 0 ? (24 * 60) / minutes : null;
  }

  return null;
}

function toolDefinition(toolKey: string): ToolDefinition {
  const cleaned = toolKey
    .replace(/OCI/gi, "")
    .replace(/Oracle/gi, "")
    .trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  const abbreviation = words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 2) || toolKey.slice(0, 2).toUpperCase();

  const palette = [
    { accent: "#2563eb", surface: "#dbeafe" },
    { accent: "#7c3aed", surface: "#ede9fe" },
    { accent: "#ea580c", surface: "#ffedd5" },
    { accent: "#16a34a", surface: "#dcfce7" },
    { accent: "#0891b2", surface: "#cffafe" },
    { accent: "#db2777", surface: "#fce7f3" },
  ];
  const seed = toolKey.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const colors = palette[seed % palette.length];
  return {
    toolKey,
    abbreviation,
    accent: colors.accent,
    surface: colors.surface,
  };
}

function uniqueToolKeys(nodes: CanvasNode[]): string[] {
  return Array.from(new Set(nodes.map((node) => node.toolKey))).sort((left, right) =>
    left.localeCompare(right),
  );
}

function createNode(toolKey: string, index: number, x?: number, y?: number): CanvasNode {
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    instanceId: crypto.randomUUID(),
    toolKey,
    label: toolKey,
    payloadNote: "",
    x: x ?? 240 + column * 210,
    y: y ?? 80 + row * 140,
  };
}

function buildDefaultNodes(coreTools: string[]): CanvasNode[] {
  return coreTools.map((toolKey, index) => createNode(toolKey, index));
}

function buildDefaultEdges(nodes: CanvasNode[]): CanvasEdge[] {
  if (nodes.length === 0) {
    return [
      {
        edgeId: crypto.randomUUID(),
        sourceInstanceId: SOURCE_NODE_ID,
        targetInstanceId: DESTINATION_NODE_ID,
        label: "",
      },
    ];
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
  const sanitizedEdges = edges.filter(
    (edge) =>
      Boolean(edge.edgeId) &&
      edge.sourceInstanceId !== edge.targetInstanceId &&
      validIds.has(edge.sourceInstanceId) &&
      validIds.has(edge.targetInstanceId),
  );

  return {
    nodes: Array.from(uniqueNodes.values()),
    edges: sanitizedEdges,
  };
}

function parseCanvasState(value: string | null, coreTools: string[]): { nodes: CanvasNode[]; edges: CanvasEdge[] } {
  if (!value) {
    const nodes = buildDefaultNodes(coreTools);
    return sanitizeCanvasState(nodes, buildDefaultEdges(nodes));
  }

  try {
    const parsed: unknown = JSON.parse(value);
    if (isStoredCanvasStateV2(parsed)) {
      return sanitizeCanvasState(
        parsed.nodes.map((node) => ({
          instanceId: node.instanceId,
          toolKey: node.toolKey,
          label: node.label,
          payloadNote: node.payloadNote,
          x: node.x,
          y: node.y,
        })),
        parsed.edges.map((edge) => ({
          edgeId: edge.edgeId,
          sourceInstanceId: edge.sourceInstanceId,
          targetInstanceId: edge.targetInstanceId,
          label: edge.label,
        })),
      );
    }

    if (isLegacyCanvasState(parsed)) {
      return sanitizeCanvasState(
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
    }
  } catch {}

  const nodes = buildDefaultNodes(coreTools);
  return sanitizeCanvasState(nodes, buildDefaultEdges(nodes));
}

function serializeCanvasState(nodes: CanvasNode[], edges: CanvasEdge[]): string {
  const payload: StoredCanvasStateV2 = {
    v: 2,
    nodes,
    edges,
  };
  return JSON.stringify(payload);
}

function fixedNodes(
  sourceSystem: string,
  sourceTechnology: string | null,
  destinationSystem: string | null,
  destinationTechnology: string | null,
): Record<string, FlowNode> {
  return {
    [SOURCE_NODE_ID]: {
      instanceId: SOURCE_NODE_ID,
      toolKey: SOURCE_NODE_ID,
      label: sourceSystem,
      payloadNote: "",
      x: 40,
      y: VIEWPORT_HEIGHT / 2 - NODE_HEIGHT / 2,
      subtitle: sourceTechnology,
      fixed: true,
    },
    [DESTINATION_NODE_ID]: {
      instanceId: DESTINATION_NODE_ID,
      toolKey: DESTINATION_NODE_ID,
      label: destinationSystem ?? "Unknown Destination",
      payloadNote: "",
      x: VIEWPORT_WIDTH - NODE_WIDTH - 40,
      y: VIEWPORT_HEIGHT / 2 - NODE_HEIGHT / 2,
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
  nodes: CanvasNode[],
): Record<string, FlowNode> {
  const fixed = fixedNodes(sourceSystem, sourceTechnology, destinationSystem, destinationTechnology);
  return {
    ...fixed,
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

function nodeCenter(node: FlowNode): { x: number; y: number } {
  return { x: node.x + NODE_WIDTH / 2, y: node.y + NODE_HEIGHT / 2 };
}

function handleCoordinates(node: FlowNode, handle: HandlePosition): { x: number; y: number } {
  const center = nodeCenter(node);
  switch (handle) {
    case "top":
      return { x: center.x, y: node.y };
    case "right":
      return { x: node.x + NODE_WIDTH, y: center.y };
    case "bottom":
      return { x: center.x, y: node.y + NODE_HEIGHT };
    case "left":
      return { x: node.x, y: center.y };
  }
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

function eventCanvasPoint(event: { clientX: number; clientY: number }, element: SVGSVGElement): { x: number; y: number } {
  const rect = element.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

export function IntegrationCanvas({
  sourceSystem,
  sourceTechnology,
  destinationSystem,
  destinationTechnology,
  selectedPattern,
  coreTools,
  availableTools,
  payloadKb,
  frequency,
  patternCategory,
  value,
  onChange,
  onToolsChange,
}: IntegrationCanvasProps): JSX.Element {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const initialStateRef = useRef<{ nodes: CanvasNode[]; edges: CanvasEdge[] }>(
    parseCanvasState(value, coreTools),
  );
  const [nodes, setNodes] = useState<CanvasNode[]>(() => initialStateRef.current.nodes);
  const [edges, setEdges] = useState<CanvasEdge[]>(() => initialStateRef.current.edges);
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedElement, setSelectedElement] = useState<SelectedElement>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingPayloadId, setEditingPayloadId] = useState<string | null>(null);
  const [editingEdgeId, setEditingEdgeId] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState<string>("");
  const [draggingNode, setDraggingNode] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [panning, setPanning] = useState<{ x: number; y: number; viewportX: number; viewportY: number } | null>(null);
  const [connecting, setConnecting] = useState<{
    sourceInstanceId: string;
    startHandle: HandlePosition;
    currentPoint: { x: number; y: number };
  } | null>(null);
  const lastSerializedRef = useRef<string>(
    serializeCanvasState(initialStateRef.current.nodes, initialStateRef.current.edges),
  );

  useEffect(() => {
    if ((value ?? "") === lastSerializedRef.current) {
      return;
    }
    const parsed = parseCanvasState(value, coreTools);
    setNodes(parsed.nodes);
    setEdges(parsed.edges);
    lastSerializedRef.current = serializeCanvasState(parsed.nodes, parsed.edges);
  }, [coreTools, value]);

  useEffect(() => {
    const nextSerialized = serializeCanvasState(nodes, edges);
    lastSerializedRef.current = nextSerialized;
    if (nextSerialized !== (value ?? "")) {
      onChange(nextSerialized);
    }
    onToolsChange?.(uniqueToolKeys(nodes));
  }, [edges, nodes, onChange, onToolsChange, value]);

  useEffect(() => {
    const validNodeIds = new Set<string>([SOURCE_NODE_ID, DESTINATION_NODE_ID, ...nodes.map((node) => node.instanceId)]);
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
                edge.sourceInstanceId !== selectedElement.id && edge.targetInstanceId !== selectedElement.id,
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
    () => mergedNodes(sourceSystem, sourceTechnology, destinationSystem, destinationTechnology, nodes),
    [destinationSystem, destinationTechnology, nodes, sourceSystem, sourceTechnology],
  );
  const connectingSource = connecting ? flowNodes[connecting.sourceInstanceId] : null;
  const billingMsgs = estimateBillingMsgs(payloadKb);
  const executionsPerDay = estimateExecutionsPerDay(frequency);
  const monthlyBilling =
    billingMsgs !== null && executionsPerDay !== null ? Math.ceil(billingMsgs * executionsPerDay * 30) : null;
  const formattedFrequency = formatFrequency(frequency);
  const formattedPatternCategory = formatPatternCategory(patternCategory);

  function deleteSelectedElement(): void {
    if (!selectedElement) {
      return;
    }

    if (selectedElement.kind === "node") {
      setNodes((current) => current.filter((node) => node.instanceId !== selectedElement.id));
      setEdges((current) =>
        current.filter(
          (edge) =>
            edge.sourceInstanceId !== selectedElement.id && edge.targetInstanceId !== selectedElement.id,
        ),
      );
    } else {
      setEdges((current) => current.filter((edge) => edge.edgeId !== selectedElement.id));
    }

    setSelectedElement(null);
  }

  function addNode(toolKey: string, point?: { x: number; y: number }): void {
    setNodes((current) => {
      const index = current.length;
      const nextPoint = point
        ? {
            x: clamp(point.x - NODE_WIDTH / 2, 20, VIEWPORT_WIDTH - NODE_WIDTH - 20),
            y: clamp(point.y - NODE_HEIGHT / 2, 20, VIEWPORT_HEIGHT - NODE_HEIGHT - 20),
          }
        : undefined;
      return [...current, createNode(toolKey, index, nextPoint?.x, nextPoint?.y)];
    });
  }

  function resetCanvas(): void {
    const defaults = parseCanvasState(null, coreTools);
    setNodes(defaults.nodes);
    setEdges(defaults.edges);
    setSelectedElement(null);
    setEditingEdgeId(null);
    setEditingNodeId(null);
    setEditingPayloadId(null);
  }

  function createEdge(sourceInstanceId: string, targetInstanceId: string): void {
    if (sourceInstanceId === targetInstanceId) {
      return;
    }
    if (!flowNodes[sourceInstanceId] || !flowNodes[targetInstanceId]) {
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
    const worldPoint = screenToWorld(canvasPoint, viewport);
    addNode(toolKey, worldPoint);
  }

  function handleCanvasMouseDown(event: ReactMouseEvent<SVGSVGElement>): void {
    if ((event.target as SVGElement).dataset.role !== "canvas-background") {
      return;
    }
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
      setNodes((current) =>
        current.map((node) =>
          node.instanceId === draggingNode.id
            ? {
                ...node,
                x: clamp(worldPoint.x - draggingNode.dx, 20, VIEWPORT_WIDTH - NODE_WIDTH - 20),
                y: clamp(worldPoint.y - draggingNode.dy, 20, VIEWPORT_HEIGHT - NODE_HEIGHT - 20),
              }
            : node,
        ),
      );
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

  function handleWheel(event: React.WheelEvent<SVGSVGElement>): void {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) {
      return;
    }

    const canvasPoint = eventCanvasPoint(event, svg);
    const worldBefore = screenToWorld(canvasPoint, viewport);
    const nextScale = clamp(viewport.scale * (event.deltaY > 0 ? 0.92 : 1.08), MIN_SCALE, MAX_SCALE);
    const nextViewport = {
      scale: nextScale,
      x: canvasPoint.x - worldBefore.x * nextScale,
      y: canvasPoint.y - worldBefore.y * nextScale,
    };
    setViewport(nextViewport);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
        {availableTools.map((toolKey) => {
          const definition = toolDefinition(toolKey);
          return (
            <button
              key={toolKey}
              type="button"
              draggable
              onDragStart={(event) => event.dataTransfer.setData("text/tool-key", toolKey)}
              onClick={() => addNode(toolKey)}
              className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm font-medium text-[var(--color-text-primary)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-surface)]"
              title="Drag onto the canvas or click to add a node"
            >
              <span
                className="inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold text-white"
                style={{ backgroundColor: definition.accent }}
              >
                {definition.abbreviation}
              </span>
              {toolKey}
            </button>
          );
        })}
        <button type="button" onClick={resetCanvas} className="app-button-secondary inline-flex items-center gap-2 px-4 py-2">
          <RotateCcw className="h-4 w-4" />
          Reset
        </button>
        {selectedElement?.kind === "edge" ? (
          <button
            type="button"
            onClick={deleteSelectedElement}
            className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100"
          >
            <Trash2 className="h-4 w-4" />
            Remove Selected Path
          </button>
        ) : null}
        <span className="text-xs text-[var(--color-text-muted)]">
          Drag a tool onto the canvas, move it into place, then drag from a connection handle into another node to build the flow.
        </span>
        <span className="text-xs text-[var(--color-text-muted)]">
          Select an existing path to remove outdated routes, such as a prior direct integration that should no longer remain on the topology.
        </span>
      </div>

      <div className="overflow-x-auto">
        <div
          className="rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleCanvasDrop}
        >
          <svg
            ref={svgRef}
            width={VIEWPORT_WIDTH}
            height={VIEWPORT_HEIGHT}
            className="block"
            style={{ touchAction: "none" }}
            onMouseDown={handleCanvasMouseDown}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={handleCanvasMouseUp}
            onMouseLeave={handleCanvasMouseUp}
            onWheel={handleWheel}
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
              <marker id="canvas-arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M0,0 L0,8 L8,4 z" fill="var(--color-accent)" />
              </marker>
            </defs>

            <rect
              data-role="canvas-background"
              x={0}
              y={0}
              width={VIEWPORT_WIDTH}
              height={VIEWPORT_HEIGHT}
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
                      strokeWidth={selected ? 3.5 : 2.3}
                      markerEnd="url(#canvas-arrowhead)"
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedElement({ kind: "edge", id: edge.edgeId });
                      }}
                    />
                    {editingEdgeId === edge.edgeId ? (
                      <foreignObject
                        x={geometry.midpoint.x - 76}
                        y={geometry.midpoint.y - 14}
                        width={152}
                        height={34}
                      >
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
                    ) : (
                      <>
                        <foreignObject
                          x={geometry.midpoint.x - 74}
                          y={geometry.midpoint.y - 14}
                          width={148}
                          height={34}
                        >
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
                        {selected ? (
                          <foreignObject
                            x={geometry.midpoint.x + 80}
                            y={geometry.midpoint.y - 14}
                            width={34}
                            height={34}
                          >
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                deleteSelectedElement();
                              }}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-rose-200 bg-rose-50 text-rose-700 shadow-sm"
                              title="Remove selected path"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </foreignObject>
                        ) : null}
                      </>
                    )}
                  </g>
                );
              })}

              {connecting && connectingSource ? (
                <path
                  d={`M ${handleCoordinates(connectingSource, connecting.startHandle).x} ${handleCoordinates(connectingSource, connecting.startHandle).y} L ${connecting.currentPoint.x} ${connecting.currentPoint.y}`}
                  fill="none"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  strokeDasharray="8 6"
                />
              ) : null}

              {Object.values(flowNodes).map((node) => {
                const definition = node.fixed
                  ? {
                      abbreviation: node.instanceId === SOURCE_NODE_ID ? "IN" : "OUT",
                      accent: "#2563eb",
                      surface: "#dbeafe",
                    }
                  : toolDefinition(node.toolKey);
                const hovered = hoveredNodeId === node.instanceId;
                const selected = isNodeSelected(selectedElement, node.instanceId);
                const showHandles = hovered || selected;
                const handles: HandlePosition[] = ["top", "right", "bottom", "left"];

                return (
                  <g
                    key={node.instanceId}
                    transform={`translate(${node.x}, ${node.y})`}
                    onMouseEnter={() => setHoveredNodeId(node.instanceId)}
                    onMouseLeave={() => setHoveredNodeId((current) => (current === node.instanceId ? null : current))}
                    onMouseDown={(event) => {
                      if (node.fixed) {
                        return;
                      }
                      event.stopPropagation();
                      const canvasPoint = eventCanvasPoint(event, svgRef.current!);
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
                    <rect
                      width={NODE_WIDTH}
                      height={NODE_HEIGHT}
                      rx={24}
                      fill={definition.surface}
                      stroke={selected ? "var(--color-accent)" : definition.accent}
                      strokeWidth={selected ? 3.5 : 2}
                    />
                    <rect
                      x={16}
                      y={14}
                      width={34}
                      height={34}
                      rx={17}
                      fill={definition.accent}
                    />
                    <text x={33} y={36} textAnchor="middle" fontSize={12} fontWeight="700" fill="white">
                      {definition.abbreviation}
                    </text>

                    {editingNodeId === node.instanceId ? (
                      <foreignObject x={58} y={18} width={106} height={30}>
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
                          className="h-7 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-sm text-[var(--color-text-primary)]"
                        />
                      </foreignObject>
                    ) : (
                      <text
                        x={58}
                        y={34}
                        fontSize={15}
                        fontWeight="700"
                        fill="var(--color-text-primary)"
                        onDoubleClick={(event) => {
                          event.stopPropagation();
                          if (!node.fixed) {
                            beginTextEdit("node", node.instanceId, node.label);
                          }
                        }}
                      >
                        {node.label.length > 20 ? `${node.label.slice(0, 20)}…` : node.label}
                      </text>
                    )}

                    <text x={58} y={54} fontSize={11} fill="var(--color-text-secondary)">
                      {node.fixed ? node.subtitle ?? "System endpoint" : node.toolKey}
                    </text>

                    {editingPayloadId === node.instanceId ? (
                      <foreignObject x={16} y={66} width={148} height={26}>
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
                          className="h-6 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-xs text-[var(--color-text-primary)]"
                        />
                      </foreignObject>
                    ) : (
                      <text
                        x={16}
                        y={84}
                        fontSize={11}
                        fill={node.payloadNote ? "var(--color-text-secondary)" : "var(--color-text-muted)"}
                        onDoubleClick={(event) => {
                          event.stopPropagation();
                          if (!node.fixed) {
                            beginTextEdit("payload", node.instanceId, node.payloadNote);
                          }
                        }}
                      >
                        {(node.payloadNote || (node.fixed ? node.subtitle ?? "System endpoint" : "Double-click to add payload note")).slice(0, 30)}
                      </text>
                    )}

                    {!node.fixed ? (
                      <foreignObject x={16} y={104} width={148} height={28}>
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

                    {showHandles
                      ? handles.map((handle) => {
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
                        })
                      : null}
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Payload ingress</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">{payloadKb ?? "?"} KB / execution</p>
          <p className="text-[var(--color-text-secondary)]">{formattedFrequency}</p>
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Processing</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">
            {billingMsgs ?? "?"} billing msg{billingMsgs === 1 ? "" : "s"} / execution
          </p>
          <p className="text-[var(--color-text-secondary)]">Pattern: {selectedPattern ?? "unassigned"}</p>
          <p className="text-[var(--color-text-secondary)]">
            Estimated OIC msgs/month: {monthlyBilling ?? "unknown"}
          </p>
        </div>
        <div className="app-card-muted p-4 text-sm">
          <span className="font-medium text-[var(--color-text-primary)]">Outcome</span>
          <p className="mt-2 text-[var(--color-text-secondary)]">→ {destinationSystem ?? "unknown"}</p>
          <p className="text-[var(--color-text-secondary)]">{destinationTechnology ?? ""}</p>
          <p className="text-[var(--color-text-secondary)]">{formattedPatternCategory}</p>
        </div>
      </div>
    </div>
  );
}
