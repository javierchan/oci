"use client";

/* SVG-based integration flow canvas with governed tool semantics and pattern suggestions. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { Move, RotateCcw, Trash2, ZoomIn } from "lucide-react";

import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { api } from "@/lib/api";
import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  deriveCanvasSemantics,
  parseCanvasState,
  serializeCanvasState,
  type CanvasEdge,
  type CanvasNode,
} from "@/lib/canvas-governance";
import type {
  CanvasCombination,
  DictionaryOption,
  OICEstimateResponse,
  PatternDefinition,
} from "@/lib/types";

type PatternCategory = "SÍNCRONO" | "ASÍNCRONO" | "SÍNCRONO + ASÍNCRONO";
type HandlePosition = "top" | "right" | "bottom" | "left";
type SelectedElement =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | null;

const MIN_CANVAS_WIDTH = 960;
const CANVAS_HEIGHT = 560;
const MIN_SCALE = 0.5;
const MAX_SCALE = 2;
const TOOL_NODE_WIDTH = 188;
const TOOL_NODE_HEIGHT = 96;
const SYSTEM_NODE_WIDTH = 260;
const SYSTEM_NODE_HEIGHT = 110;
const HANDLE_RADIUS = 7;

type FixedNodeMeta = {
  subtitle: string | null;
  fixed: boolean;
};

type FlowNode = CanvasNode & FixedNodeMeta;

type ToolDefinition = {
  abbreviation: string;
  accent: string;
  surface: string;
};

type IntegrationCanvasProps = {
  projectId: string;
  sourceSystem: string;
  sourceTechnology: string | null;
  destinationSystem: string | null;
  destinationTechnology: string | null;
  selectedPattern: string | null;
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
};

const EMPTY_ESTIMATE: OICEstimateResponse = {
  billing_msgs_per_execution: null,
  billing_msgs_per_month: null,
  peak_packs_per_hour: null,
  executions_per_day: null,
  computable: false,
};

function toolDefinition(toolKey: string): ToolDefinition {
  const cleaned = toolKey
    .replace(/OCI/gi, "")
    .replace(/Oracle/gi, "")
    .trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  const abbreviation =
    words
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
    abbreviation,
    accent: colors.accent,
    surface: colors.surface,
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
    x: x ?? 240 + column * 220,
    y: y ?? 80 + row * 140,
  };
}

function fixedNodes(
  sourceSystem: string,
  sourceTechnology: string | null,
  destinationSystem: string | null,
  destinationTechnology: string | null,
  canvasWidth: number,
): Record<string, FlowNode> {
  return {
    [SOURCE_NODE_ID]: {
      instanceId: SOURCE_NODE_ID,
      toolKey: SOURCE_NODE_ID,
      label: sourceSystem,
      payloadNote: "",
      x: 40,
      y: CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
      subtitle: sourceTechnology,
      fixed: true,
    },
    [DESTINATION_NODE_ID]: {
      instanceId: DESTINATION_NODE_ID,
      toolKey: DESTINATION_NODE_ID,
      label: destinationSystem ?? "Unknown Destination",
      payloadNote: "",
      x: canvasWidth - SYSTEM_NODE_WIDTH - 40,
      y: CANVAS_HEIGHT / 2 - SYSTEM_NODE_HEIGHT / 2,
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
): Record<string, FlowNode> {
  return {
    ...fixedNodes(
      sourceSystem,
      sourceTechnology,
      destinationSystem,
      destinationTechnology,
      canvasWidth,
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
    return node.label.length > 20 ? 13 : 14;
  }
  return node.label.length > 18 ? 14 : 15;
}

function renderedLabel(node: FlowNode): string {
  return truncateLabel(node.label, node.fixed ? 22 : 20);
}

function renderedSubtitle(node: FlowNode): string {
  const value = node.fixed ? node.subtitle ?? "System endpoint" : node.toolKey;
  return truncateLabel(value, node.fixed ? 26 : 24);
}

function renderedPayload(node: FlowNode): string {
  if (node.fixed) {
    return "";
  }
  return truncateLabel(node.payloadNote || "Double-click to add payload note", 30);
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
}: IntegrationCanvasProps): JSX.Element {
  const overlayToolKeys = useMemo(
    () => overlayOptions.map((option) => option.value),
    [overlayOptions],
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
  const [canvasWidth, setCanvasWidth] = useState<number>(MIN_CANVAS_WIDTH);
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedElement, setSelectedElement] = useState<SelectedElement>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingPayloadId, setEditingPayloadId] = useState<string | null>(null);
  const [editingEdgeId, setEditingEdgeId] = useState<string | null>(null);
  const [oicEstimate, setOicEstimate] = useState<OICEstimateResponse>(EMPTY_ESTIMATE);
  const [draftValue, setDraftValue] = useState<string>("");
  const [draggingNode, setDraggingNode] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [panning, setPanning] = useState<{ x: number; y: number; viewportX: number; viewportY: number } | null>(null);
  const [connecting, setConnecting] = useState<{
    sourceInstanceId: string;
    startHandle: HandlePosition;
    currentPoint: { x: number; y: number };
  } | null>(null);
  const lastSerializedRef = useRef<string>(
    serializeCanvasState(initialStateRef.current.nodes, initialStateRef.current.edges, initialSemantics),
  );

  useEffect(() => {
    const shell = canvasShellRef.current;
    if (!shell) {
      return;
    }

    const updateCanvasWidth = (): void => {
      const nextWidth = Math.max(MIN_CANVAS_WIDTH, Math.floor(shell.clientWidth) - 24);
      setCanvasWidth((current) => (current === nextWidth ? current : nextWidth));
    };

    updateCanvasWidth();
    const observer = new ResizeObserver(() => {
      updateCanvasWidth();
    });
    observer.observe(shell);
    return () => observer.disconnect();
  }, []);

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
    lastSerializedRef.current = serializeCanvasState(parsed.nodes, parsed.edges, nextSemantics);
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

  useEffect(() => {
    const nextSerialized = serializeCanvasState(nodes, edges, semantics);
    lastSerializedRef.current = nextSerialized;
    if (nextSerialized !== (value ?? "")) {
      onChange(nextSerialized);
    }
    onToolsChange?.(semantics.coreToolKeys);
    onConnectionValidityChange?.(semantics.hasConnectedRoute);
  }, [edges, nodes, onChange, onConnectionValidityChange, onToolsChange, semantics, value]);

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
        x: clamp(node.x, 20, canvasWidth - TOOL_NODE_WIDTH - 20),
        y: clamp(node.y, 20, CANVAS_HEIGHT - TOOL_NODE_HEIGHT - 20),
      })),
    );
  }, [canvasWidth]);

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
        canvasWidth,
        nodes,
      ),
    [canvasWidth, destinationSystem, destinationTechnology, nodes, sourceSystem, sourceTechnology],
  );
  const connectingSource = connecting ? flowNodes[connecting.sourceInstanceId] : null;
  const monthlyBilling = oicEstimate.billing_msgs_per_month;
  const canvasCursor = panning ? "grabbing" : "grab";
  const processingToolKeys = semantics.coreToolKeys;
  const activeOverlayKeys = semantics.overlayKeys;
  const includesOicGen3 = processingToolKeys.some((toolKey) => toolKey.toLowerCase() === "oic gen3");
  const suggestedPatterns = semantics.suggestedPatternIds
    .map((patternId) => patternMap.get(patternId))
    .filter((pattern): pattern is PatternDefinition => Boolean(pattern));
  const selectedPatternDefinition = selectedPattern ? patternMap.get(selectedPattern) ?? null : null;
  const patternMismatch =
    Boolean(selectedPatternDefinition) &&
    semantics.matchedCombinations.length > 0 &&
    !semantics.suggestedPatternIds.includes(selectedPattern ?? "");

  function addNode(toolKey: string, point?: { x: number; y: number }): void {
    const nextNode = createNode(toolKey, nodes.length);
    setNodes((current) => {
      const nextPoint = point
        ? {
            x: clamp(point.x - TOOL_NODE_WIDTH / 2, 20, canvasWidth - TOOL_NODE_WIDTH - 20),
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
    setNodes(defaults.nodes);
    setEdges(defaults.edges);
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
                x: clamp(worldPoint.x - draggingNode.dx, 20, canvasWidth - TOOL_NODE_WIDTH - 20),
                y: clamp(worldPoint.y - draggingNode.dy, 20, CANVAS_HEIGHT - TOOL_NODE_HEIGHT - 20),
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
    setViewport({
      scale: nextScale,
      x: canvasPoint.x - worldBefore.x * nextScale,
      y: canvasPoint.y - worldBefore.y * nextScale,
    });
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
          className="inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold text-white"
          style={{ backgroundColor: definition.accent }}
        >
          {definition.abbreviation}
        </span>
        {option.value}
      </button>
    );
  }

  return (
    <div className="space-y-5">
      <div className="space-y-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
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

        <div className="flex flex-wrap gap-3">{toolOptions.map((option) => renderPaletteButton(option, false))}</div>

        <div className="border-t border-[var(--color-border)] pt-3">
          <p className="app-label">Architectural Overlays</p>
          <p className="mt-2 text-xs text-[var(--color-text-muted)]">
            Overlays document edge protection and runtime context. They do not satisfy the core-tools QA gate by themselves.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            {overlayOptions.map((option) => renderPaletteButton(option, true))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--color-text-muted)]">
          <span>Drag or click to add a node. Drag from connection handles to create the flow.</span>
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
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
              {semantics.disconnectedNodeIds.length} disconnected node
              {semantics.disconnectedNodeIds.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div ref={canvasShellRef} className="relative">
          <div className="pointer-events-none absolute left-5 top-5 z-10 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
            <Move className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            Drag empty canvas to pan
            <span className="text-[var(--color-text-muted)]">•</span>
            <ZoomIn className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            Wheel to zoom
          </div>
          <div className="pointer-events-none absolute right-5 top-5 z-10 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
            Zoom {Math.round(viewport.scale * 100)}%
          </div>
          <div
            className="rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleCanvasDrop}
          >
            <svg
              ref={svgRef}
              width={canvasWidth}
              height={CANVAS_HEIGHT}
              viewBox={`0 0 ${canvasWidth} ${CANVAS_HEIGHT}`}
              className="block w-full"
              style={{ touchAction: "none", cursor: canvasCursor }}
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleCanvasMouseMove}
              onMouseUp={handleCanvasMouseUp}
              onMouseLeave={handleCanvasMouseUp}
              onWheel={handleWheel}
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
                <marker id="canvas-arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                  <path d="M0,0 L0,8 L8,4 z" fill="var(--color-accent)" />
                </marker>
              </defs>

              <rect
                data-role="canvas-background"
                x={0}
                y={0}
                width={canvasWidth}
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
                        strokeWidth={selected ? 3.5 : 2.3}
                        markerEnd="url(#canvas-arrowhead)"
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
                      ) : (
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

                  return (
                    <g
                      key={node.instanceId}
                      transform={`translate(${node.x}, ${node.y})`}
                      onMouseEnter={() => setHoveredNodeId(node.instanceId)}
                      onMouseLeave={() => setHoveredNodeId((current) => (current === node.instanceId ? null : current))}
                      onMouseDown={(event) => {
                        if (node.fixed || event.button !== 0 || !svgRef.current) {
                          return;
                        }
                        event.stopPropagation();
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
                      <rect
                        width={width}
                        height={height}
                        rx={24}
                        fill={definition.surface}
                        stroke={selected ? "var(--color-accent)" : definition.accent}
                        strokeWidth={selected ? 3.5 : 2}
                        strokeDasharray={isOverlayNode ? "10 6" : undefined}
                      />
                      <rect x={16} y={14} width={34} height={34} rx={17} fill={definition.accent} />
                      <text x={33} y={36} textAnchor="middle" fontSize={12} fontWeight="700" fill="white">
                        {definition.abbreviation}
                      </text>

                      {editingNodeId === node.instanceId ? (
                        <foreignObject x={58} y={16} width={width - 72} height={30}>
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
                          y={35}
                          fontSize={labelFontSize(node)}
                          fontWeight="700"
                          fill="var(--color-text-primary)"
                          onDoubleClick={(event) => {
                            event.stopPropagation();
                            if (!node.fixed) {
                              beginTextEdit("node", node.instanceId, node.label);
                            }
                          }}
                        >
                          {renderedLabel(node)}
                        </text>
                      )}

                      <text x={58} y={58} fontSize={node.fixed ? 10.5 : 11} fill="var(--color-text-secondary)">
                        {subtitleText}
                      </text>

                      {!node.fixed && editingPayloadId === node.instanceId ? (
                        <foreignObject x={16} y={66} width={width - 32} height={26}>
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
                      ) : !node.fixed ? (
                        <text
                          x={16}
                          y={84}
                          fontSize={10.5}
                          fill={node.payloadNote ? "var(--color-text-secondary)" : "var(--color-text-muted)"}
                          onDoubleClick={(event) => {
                            event.stopPropagation();
                            beginTextEdit("payload", node.instanceId, node.payloadNote);
                          }}
                        >
                          {renderedPayload(node)}
                        </text>
                      ) : null}

                      {!node.fixed ? (
                        <foreignObject x={16} y={104} width={width - 32} height={28}>
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

        <aside className="space-y-4">
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
            <span className="font-medium text-[var(--color-text-primary)]">Combination suggestions</span>
            <div className="mt-3 space-y-3">
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
                  Add and connect governed tools to receive workbook-backed combination hints.
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
          <p className="text-[var(--color-text-secondary)]">{frequency ?? "unknown frequency"}</p>
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
    </div>
  );
}
