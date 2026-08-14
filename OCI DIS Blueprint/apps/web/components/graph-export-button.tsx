"use client";

/* Observable, style-safe PNG export control for the system dependency graph SVG. */

import { Check, ImageDown, LoaderCircle, TriangleAlert } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useState } from "react";
import type { RefObject } from "react";

type GraphExportButtonProps = {
  projectId: string;
  svgRef: RefObject<SVGSVGElement>;
  disabled?: boolean;
};

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const EXPORT_PIXEL_RATIO = 2;

function loadSvgImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Topology SVG could not be rasterized."));
    image.src = url;
  });
}

function canvasToPng(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }
      reject(new Error("Topology PNG could not be encoded."));
    }, "image/png");
  });
}

function exportDimensions(svg: SVGSVGElement): { width: number; height: number } {
  const viewBox = svg.viewBox.baseVal;
  if (viewBox.width > 0 && viewBox.height > 0) {
    return { width: Math.round(viewBox.width), height: Math.round(viewBox.height) };
  }
  const rect = svg.getBoundingClientRect();
  return {
    width: Math.max(Math.round(rect.width), 1),
    height: Math.max(Math.round(rect.height), 1),
  };
}

function resolvedRootVariable(styles: CSSStyleDeclaration, variable: string, fallback: string): string {
  let value = styles.getPropertyValue(variable).trim();
  const visited = new Set<string>([variable]);
  while (value.startsWith("var(")) {
    const match = value.match(/^var\((--[^,\s)]+)(?:,[^)]+)?\)$/);
    if (!match || visited.has(match[1])) {
      return fallback;
    }
    visited.add(match[1]);
    value = styles.getPropertyValue(match[1]).trim();
  }
  return value || fallback;
}

function serializeTopologySvg(svg: SVGSVGElement, width: number, height: number): string {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const rootStyles = window.getComputedStyle(document.documentElement);
  const exportedVariables: Record<string, string> = {
    "--color-surface": "#ffffff",
    "--color-text-primary": "#16140f",
    "--color-text-muted": "#8a8678",
    "--color-border": "#e3e0d6",
  };
  const resolvedVariables = Object.fromEntries(
    Object.entries(exportedVariables).map(([variable, fallback]) => [
      variable,
      resolvedRootVariable(rootStyles, variable, fallback),
    ]),
  );
  const surface = resolvedVariables["--color-surface"];

  clone.setAttribute("xmlns", SVG_NAMESPACE);
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  clone.removeAttribute("class");
  clone.style.removeProperty("touch-action");
  Object.entries(resolvedVariables).forEach(([variable, value]) => {
    clone.style.setProperty(variable, value);
  });

  const background = document.createElementNS(SVG_NAMESPACE, "rect");
  background.setAttribute("x", "0");
  background.setAttribute("y", "0");
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  background.setAttribute("fill", surface);
  clone.insertBefore(background, clone.firstChild);

  return new XMLSerializer().serializeToString(clone);
}

async function exportPNG(svgRef: RefObject<SVGSVGElement>, projectId: string): Promise<void> {
  const svg = svgRef.current;
  if (!svg) {
    throw new Error("Topology SVG is not available.");
  }

  const { width, height } = exportDimensions(svg);
  const serialized = serializeTopologySvg(svg, width, height);
  const svgUrl = URL.createObjectURL(new Blob([serialized], { type: "image/svg+xml;charset=utf-8" }));
  let png: Blob;
  try {
    const image = await loadSvgImage(svgUrl);
    const canvas = document.createElement("canvas");
    canvas.width = width * EXPORT_PIXEL_RATIO;
    canvas.height = height * EXPORT_PIXEL_RATIO;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Topology export canvas is not available.");
    }
    context.scale(EXPORT_PIXEL_RATIO, EXPORT_PIXEL_RATIO);
    context.drawImage(image, 0, 0, width, height);
    png = await canvasToPng(canvas);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }

  const downloadUrl = URL.createObjectURL(png);
  const anchor = document.createElement("a");
  anchor.download = `integration-map-${projectId}-${new Date().toISOString().slice(0, 10)}.png`;
  anchor.href = downloadUrl;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1_000);
}

export function GraphExportButton({ projectId, svgRef, disabled = false }: GraphExportButtonProps): JSX.Element {
  const [status, setStatus] = useState<"idle" | "exporting" | "done" | "error">("idle");

  async function handleExport(): Promise<void> {
    setStatus("exporting");
    try {
      await exportPNG(svgRef, projectId);
      setStatus("done");
      window.setTimeout(() => setStatus("idle"), 2_000);
    } catch (error) {
      console.error("Topology PNG export failed.", error);
      setStatus("error");
    }
  }

  const label = disabled
    ? "Topology PNG unavailable while refreshing"
    : status === "exporting"
    ? "Exporting topology PNG"
    : status === "done"
      ? "Topology PNG exported"
      : status === "error"
        ? "Topology PNG export failed"
        : "Export topology as PNG";

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={disabled || status === "exporting"}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] transition hover:border-[var(--color-line-strong)] hover:text-[var(--color-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)] disabled:cursor-wait"
          aria-label={label}
        >
          {status === "exporting" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
          {status === "done" ? <Check className="h-4 w-4 text-emerald-600" /> : null}
          {status === "error" ? <TriangleAlert className="h-4 w-4 text-rose-600" /> : null}
          {status === "idle" ? <ImageDown className="h-4 w-4" /> : null}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={7}
          className="z-[80] rounded-md bg-[var(--color-text-primary)] px-2.5 py-1.5 text-xs font-semibold text-[var(--color-surface)] shadow-lg"
        >
          {label}
          <Tooltip.Arrow className="fill-[var(--color-text-primary)]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
